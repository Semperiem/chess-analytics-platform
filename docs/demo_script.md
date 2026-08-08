# Demo script

A ~5-minute walkthrough that shows the whole platform working, top to bottom.

## 0. The one-liner
"Real chess.com data flows from the public API into a warehouse, dbt turns it
into tested marts, and three different audiences consume the same marts: a
dashboard, a chatbot, and a notebook — all wired together by one Airflow DAG."

## 1. The pipeline runs as one thing (~60s)
```bash
make pipeline        # airflow dags test chess_platform_pipeline
```
Point out the task chain finishing green: `ingest → build_dimensional →
load_warehouse → dbt_build → dbt_test (gate) → refresh_superset + refresh_wrenai`,
ending `state=success`. Call out that `dbt_test` is a **gate** — bad data can't
reach the dashboards.

## 2. Transform layer — dbt (~45s)
```bash
make dbt
```
`PASS=36` (11 models + 20 tests). Show `dbt/models/marts/mart_retention.sql` —
the cohort math lives in version-controlled SQL, tested, not buried in a BI tool.

## 3. Dashboards — Superset (~90s)
Open `http://127.0.0.1:8108` → dashboard **Chess.com Player Analytics**. Walk the
six charts: total games (KPI), the retention curve, games/day, players by
recency segment, month-6 retention by cohort, and time-control performance.
Note they all read the dbt `marts.*` — the same numbers everywhere.

## 4. BI chatbot — WrenAI (~90s)
Open `http://127.0.0.1:8602`. Ask in plain English:
- *"Which recency segment has the most players, and how many?"*
- *"How does retention change from month 1 to month 6?"*
- *"Which time control has the highest win rate with at least 50 games?"*

Show the generated SQL hitting `marts_mart_*`. The point: a stakeholder answers
their own question without writing SQL or pinging an analyst.

## 5. Notebook — deep analytics (~45s)
Open `notebooks/04_warehouse_marts_analytics.ipynb` (already executed). Same
warehouse, but now full pandas/matplotlib freedom for ad-hoc analysis — the
retention curve and segment breakdown straight off `marts.*`.

## 6. Close
"One warehouse, one tested transform layer, three consumption surfaces, one
orchestration DAG — the raw-API-to-decision path an analytics team actually
runs, end to end."

## Reset / bring-up notes
- Prereqs: the `chess-wrenai-demo` WrenAI stack and `chess-wrenai-postgres` are running.
- `make up` does superset-up → dbt → bootstrap → wrenai in sequence.
- Superset admin credentials are in `superset/.env` (gitignored).
