"""Full chess.com analytics platform pipeline.

Wires the whole chain end to end:

  ingest (chess.com API)  ->  build dimensional model  ->  load warehouse
      ->  dbt build (marts)  ->  dbt test (gate)  ->  refresh Superset + WrenAI

Safe by default for a shared warehouse: `ingest_raw` reuses the committed real
pull (full re-pull is opt-in via FORCE_INGEST=1) and `load_warehouse` skips the
reload when the warehouse is already populated (FORCE_RELOAD=1 to force). The
dbt + refresh steps always run and are idempotent.
"""
from __future__ import annotations
import json, os, subprocess, time, urllib.request
import pendulum
from airflow.decorators import dag, task

ROOT = "/data/projects/portfolio/chess-analytics-platform"
ANALYTICS = "/data/projects/portfolio/demo-analytics-chess.com"
WRENAI_REPO = "/data/projects/portfolio/chess-wrenai-copilot-demo"
DBT = os.path.expanduser("~/.local/bin/dbt")
VENV_PY = f"{ROOT}/.venv/bin/python"
PG = "chess-wrenai-postgres"
WREN_UI = "http://127.0.0.1:8602/api/graphql"


def _sh(cmd, cwd=None, env=None):
    e = os.environ.copy()
    e.update(env or {})
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    print("STDOUT:\n", r.stdout[-2000:])
    if r.returncode != 0:
        print("STDERR:\n", r.stderr[-2000:])
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(cmd)}")
    return r.stdout


def _dotenv(path, extra=None):
    env = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    env.update(extra or {})
    return env


def _warehouse_count(table):
    out = subprocess.run(
        ["docker", "exec", PG, "psql", "-U", "demo", "-d", "chess_wrenai_demo",
         "-tAc", f"select count(*) from public.{table}"],
        capture_output=True, text=True)
    try:
        return int(out.stdout.strip())
    except ValueError:
        return -1


def _gql(q, v=None):
    body = json.dumps({"query": q, "variables": v or {}}).encode()
    req = urllib.request.Request(WREN_UI, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read().decode())


@dag(dag_id="chess_platform_pipeline", schedule=None,
     start_date=pendulum.datetime(2026, 1, 1, tz="UTC"), catchup=False,
     tags=["chess", "platform", "end-to-end"])
def pipeline():

    @task
    def ingest_raw():
        parquet = f"{ANALYTICS}/data/processed/games_sample.parquet"
        if os.environ.get("FORCE_INGEST") == "1":
            e = {"PYTHONPATH": f"{ANALYTICS}/src"}
            _sh(["python", "-m", "chess_analytics.ingest", "--n-cohort", "40", "--n-deep", "10"],
                cwd=ANALYTICS, env=e)
            _sh(["python", "-m", "chess_analytics.transform"], cwd=ANALYTICS, env=e)
        if not os.path.exists(parquet):
            raise FileNotFoundError("processed parquet missing; run with FORCE_INGEST=1")
        return {"parquet": parquet}

    @task
    def build_dimensional(up):
        _sh([VENV_PY, "scripts/export_dimensional_csvs.py"], cwd=WRENAI_REPO)
        return "dimensional_csvs_built"

    @task
    def load_warehouse(up):
        n = _warehouse_count("fact_games")
        if n > 0 and os.environ.get("FORCE_RELOAD") != "1":
            print(f"warehouse already populated (fact_games={n}); skip reload (protects live demo)")
            return {"loaded": False, "fact_games": n}
        _sh(["bash", "scripts/load_postgres.sh"], cwd=WRENAI_REPO)
        return {"loaded": True, "fact_games": _warehouse_count("fact_games")}

    @task
    def dbt_build(up):
        _sh([DBT, "build", "--project-dir", f"{ROOT}/dbt"],
            env=_dotenv(f"{ROOT}/.env", {"DBT_PROFILES_DIR": f"{ROOT}/dbt"}))
        return "marts_built"

    @task
    def dbt_test(up):
        # quality gate: non-zero exit here fails the run and blocks the refresh
        _sh([DBT, "test", "--project-dir", f"{ROOT}/dbt"],
            env=_dotenv(f"{ROOT}/.env", {"DBT_PROFILES_DIR": f"{ROOT}/dbt"}))
        return "tests_passed"

    @task
    def refresh_superset(up):
        _sh([VENV_PY, "bootstrap_superset.py"], cwd=f"{ROOT}/superset",
            env=_dotenv(f"{ROOT}/superset/.env"))
        return "superset_refreshed"

    @task
    def refresh_wrenai(up):
        tabs = [t["name"] for t in _gql("query{ listDataSourceTables{ name } }")
                ["data"]["listDataSourceTables"]
                if t["name"].startswith(("public.", "marts."))]
        _gql("mutation($data: SaveTablesInput!){ saveTables(data:$data) }",
             {"data": {"tables": tabs}})
        for _ in range(30):
            if "SYNCRONIZED" in json.dumps(_gql("query{ modelSync{ status } }")):
                break
            time.sleep(4)
        return {"wrenai_models": len(tabs)}

    raw = ingest_raw()
    dim = build_dimensional(raw)
    load = load_warehouse(dim)
    built = dbt_build(load)
    tested = dbt_test(built)
    refresh_superset(tested)
    refresh_wrenai(tested)


pipeline()
