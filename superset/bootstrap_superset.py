#!/usr/bin/env python3
"""Bootstrap the chess Superset: warehouse connection -> datasets on the dbt
marts -> charts -> a dashboard. Idempotent-ish (re-uses objects by name).
Self-verifies every chart via /data and falls back to a table viz if the
intended chart type errors, so the dashboard always ends with working charts.

Env (from superset/.env): SUPERSET_PORT, SUPERSET_USER, SUPERSET_PASSWORD, WAREHOUSE_URI
"""
import json, os, sys, requests

BASE = f"http://127.0.0.1:{os.environ['SUPERSET_PORT']}"
USER = os.environ["SUPERSET_USER"]; PW = os.environ["SUPERSET_PASSWORD"]
WAREHOUSE_URI = os.environ["WAREHOUSE_URI"]
S = requests.Session()

def login():
    r = S.post(f"{BASE}/api/v1/security/login",
               json={"username": USER, "password": PW, "provider": "db", "refresh": True})
    r.raise_for_status()
    tok = r.json()["access_token"]
    S.headers["Authorization"] = f"Bearer {tok}"
    csrf = S.get(f"{BASE}/api/v1/security/csrf_token/").json()["result"]
    S.headers["X-CSRFToken"] = csrf
    S.headers["Referer"] = BASE
    print("logged in")

def find(path, flt):
    q = json.dumps({"filters": flt})
    r = S.get(f"{BASE}/api/v1/{path}/?q={q}")
    if r.ok and r.json().get("count", 0):
        return r.json()["result"][0]["id"]
    return None

def get_or_create_db():
    did = find("database", [{"col": "database_name", "opr": "eq", "value": "chess_warehouse"}])
    if did: print("db exists", did); return did
    r = S.post(f"{BASE}/api/v1/database/", json={
        "database_name": "chess_warehouse", "sqlalchemy_uri": WAREHOUSE_URI,
        "expose_in_sqllab": True})
    r.raise_for_status(); did = r.json()["id"]; print("db created", did); return did

def get_or_create_dataset(db_id, table):
    ds = find("dataset", [{"col": "table_name", "opr": "eq", "value": table}])
    if ds: print("dataset exists", table, ds); return ds
    r = S.post(f"{BASE}/api/v1/dataset/", json={
        "database": db_id, "schema": "marts", "table_name": table})
    if not r.ok:
        print("dataset error", table, r.status_code, r.text[:200]); sys.exit(1)
    ds = r.json()["id"]; print("dataset created", table, ds); return ds

def m_simple(col, agg, label):
    return {"label": label, "expressionType": "SIMPLE",
            "column": {"column_name": col}, "aggregate": agg}

def build(ds_id, viz, xcol=None, metrics=None, groupby=None, raw_cols=None, row_limit=5000):
    form = {"datasource": f"{ds_id}__table", "viz_type": viz, "row_limit": row_limit}
    q = {"row_limit": row_limit, "metrics": metrics or [], "orderby": []}
    if viz in ("echarts_timeseries_line", "echarts_timeseries_bar"):
        xobj = {"columnType": "BASE_AXIS", "sqlExpression": xcol, "label": xcol,
                "expressionType": "SQL", "timeGrain": None}
        form.update({"x_axis": xcol, "metrics": metrics, "groupby": groupby or []})
        q["columns"] = [xobj] + (groupby or [])
        q["series_columns"] = groupby or []
        q["orderby"] = [[xcol, True]]
    elif viz == "pie":
        form.update({"groupby": groupby, "metric": metrics[0]})
        q["columns"] = groupby
    elif viz == "big_number_total":
        form.update({"metric": metrics[0]})
    elif viz == "table":
        if metrics:
            form.update({"query_mode": "aggregate", "groupby": groupby or [], "metrics": metrics})
            q["columns"] = groupby or []
        else:
            form.update({"query_mode": "raw", "all_columns": raw_cols})
            q["columns"] = raw_cols; q.pop("metrics", None)
    qc = {"datasource": {"id": ds_id, "type": "table"}, "force": False,
          "queries": [q], "form_data": form, "result_format": "json", "result_type": "full"}
    return form, qc

def create_chart(name, ds_id, spec):
    # spec: dict for build(); try it, verify /data, else fall back to a table
    form, qc = build(ds_id, **spec)
    cid = find("chart", [{"col": "slice_name", "opr": "eq", "value": name}])
    payload = {"slice_name": name, "viz_type": form["viz_type"],
               "datasource_id": ds_id, "datasource_type": "table",
               "params": json.dumps(form), "query_context": json.dumps(qc)}
    if cid:
        S.put(f"{BASE}/api/v1/chart/{cid}", json=payload)
    else:
        r = S.post(f"{BASE}/api/v1/chart/", json=payload); r.raise_for_status(); cid = r.json()["id"]
    # verify (correct endpoint is POST /api/v1/chart/data with the query_context body)
    d = S.post(f"{BASE}/api/v1/chart/data", json=qc)
    if d.status_code == 200:
        rows = d.json()["result"][0].get("rowcount", "?")
        print(f"  chart OK  {name:34} viz={form['viz_type']:26} rows={rows} id={cid}")
        return cid
    # fallback: raw table of the same columns
    print(f"  chart {name} viz={form['viz_type']} failed ({d.status_code}): {d.text[:140]} -> table fallback")
    cols = spec.get("raw_cols") or ([spec.get("xcol")] if spec.get("xcol") else []) or spec.get("groupby") or []
    fform, fqc = build(ds_id, "table", raw_cols=cols or None)
    fpay = {"slice_name": name, "viz_type": "table", "datasource_id": ds_id,
            "datasource_type": "table", "params": json.dumps(fform), "query_context": json.dumps(fqc)}
    S.put(f"{BASE}/api/v1/chart/{cid}", json=fpay)
    d2 = S.post(f"{BASE}/api/v1/chart/data", json=fqc)
    print(f"  fallback {'OK' if d2.status_code==200 else 'FAIL '+str(d2.status_code)} {name} id={cid}")
    return cid

def build_dashboard(title, chart_ids):
    pos = {"DASHBOARD_VERSION_KEY": "v2",
           "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
           "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
           "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID",
                         "meta": {"text": "Chess.com Player Analytics"}}}
    rows = []
    for i in range(0, len(chart_ids), 2):
        rid = f"ROW-{i}"; pos[rid] = {"type": "ROW", "id": rid, "children": [],
            "meta": {"background": "BACKGROUND_TRANSPARENT"}, "parents": ["ROOT_ID", "GRID_ID"]}
        for cid in chart_ids[i:i+2]:
            chid = f"CHART-{cid}"
            pos[chid] = {"type": "CHART", "id": chid, "children": [],
                         "meta": {"chartId": cid, "width": 6, "height": 55, "sliceName": ""},
                         "parents": ["ROOT_ID", "GRID_ID", rid]}
            pos[rid]["children"].append(chid)
        pos["GRID_ID"]["children"].append(rid); rows.append(rid)
    did = find("dashboard", [{"col": "dashboard_title", "opr": "eq", "value": title}])
    body = {"dashboard_title": title, "published": True, "position_json": json.dumps(pos)}
    if did:
        S.put(f"{BASE}/api/v1/dashboard/{did}", json=body)
    else:
        r = S.post(f"{BASE}/api/v1/dashboard/", json=body); r.raise_for_status(); did = r.json()["id"]
    # explicit link (position_json alone does not attach charts)
    for cid in chart_ids:
        S.put(f"{BASE}/api/v1/chart/{cid}", json={"dashboards": [did]})
    print("dashboard", title, "id", did)
    return did

def main():
    login()
    db = get_or_create_db()
    ds = {t: get_or_create_dataset(db, t) for t in [
        "mart_time_class_performance", "mart_retention", "mart_player_segments",
        "mart_daily_games", "mart_growth_funnel"]}
    charts = []
    charts.append(create_chart("Total games (sample)", ds["mart_daily_games"],
        dict(viz="big_number_total", metrics=[m_simple("games_played", "SUM", "games")])))
    charts.append(create_chart("Avg retention curve", ds["mart_retention"],
        dict(viz="echarts_timeseries_line", xcol="months_since_join",
             metrics=[m_simple("retention_rate", "AVG", "avg_retention")])))
    charts.append(create_chart("Games per day", ds["mart_daily_games"],
        dict(viz="echarts_timeseries_line", xcol="game_date",
             metrics=[m_simple("games_played", "SUM", "games")])))
    charts.append(create_chart("Players by recency segment", ds["mart_player_segments"],
        dict(viz="pie", groupby=["recency_segment"],
             metrics=[m_simple("player_key", "COUNT", "players")])))
    charts.append(create_chart("Month-6 retention by cohort", ds["mart_growth_funnel"],
        dict(viz="echarts_timeseries_bar", xcol="cohort_month",
             metrics=[m_simple("pct_retained_month6", "AVG", "pct_month6")])))
    charts.append(create_chart("Time-control performance", ds["mart_time_class_performance"],
        dict(viz="table",
             raw_cols=["time_class", "rules", "games", "win_rate", "avg_player_rating"])))
    dash = build_dashboard("Chess.com Player Analytics", charts)
    print(f"\nDASHBOARD URL: {BASE}/superset/dashboard/{dash}/")

if __name__ == "__main__":
    main()
