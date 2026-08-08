# Architecture

## Data flow

```
chess.com public API
        │  (ingestion: ingest.py + transform.py)
        ▼
real pull → parquet  (245 titled players, 12,255 games, 10,555 player-months)
        │  (build_dimensional: parquet → dimensional model)
        ▼
Postgres  public.dim_date / dim_players / dim_time_class
          public.fact_games / fact_player_monthly_activity        ← raw dimensional model
        │  (dbt: staging views → marts tables, 20 tests as a gate)
        ▼
Postgres  marts.dim_* / fct_* / mart_retention / mart_growth_funnel /
          mart_player_segments / mart_time_class_performance /
          mart_daily_games / mart_rating_trend                     ← curated, tested
        ├───────────────► Superset      (dashboards, read marts.*)
        ├───────────────► WrenAI        (text-to-SQL BI chatbot over marts_*)
        └───────────────► Jupyter       (pandas analytics off marts.*)
```

## Why one warehouse, reused

The warehouse is the already-running `chess_wrenai_demo` Postgres (port 5437,
on the `wrenai_wren` Docker network). Standing up a fresh database would mean
re-loading identical data and re-wiring WrenAI for no benefit. Instead:

- **raw** lands in `public.*` (loaded from the real pull),
- **dbt** owns `staging.*` (views) and `marts.*` (tables + tests),
- Superset, WrenAI, and notebooks all read the same `marts.*` — one source of truth.

`generate_schema_name` is overridden so models land in clean `staging` / `marts`
schemas (not `marts_staging`).

## Components and how they connect

| Component | Runtime | Connects to warehouse via |
|---|---|---|
| dbt | host (`~/.local/bin/dbt`) | `127.0.0.1:5437` (psycopg2), profile from env vars |
| Superset | Docker (`chess-superset`, `127.0.0.1:8108`) | `chess-wrenai-postgres:5432` on `wrenai_wren` |
| WrenAI | Docker (existing `chess-wrenai-demo` stack, `127.0.0.1:8602`) | `chess-wrenai-postgres:5432` |
| Jupyter | platform venv | `127.0.0.1:5437` (SQLAlchemy) |
| Airflow | Python (TaskFlow) | shells out to the above |

Superset needs the Postgres driver, which the stock `apache/superset` image
does **not** ship in its uv-managed venv — a 3-line `Dockerfile` bakes in
`psycopg2-binary` (the approach Superset's own docs recommend over runtime
installs).

## The orchestration DAG

`airflow/dags/chess_platform_pipeline.py` (TaskFlow):

```
ingest_raw → build_dimensional → load_warehouse → dbt_build → dbt_test → ┬→ refresh_superset
                                                              (gate)     └→ refresh_wrenai
```

Safe for a shared warehouse: `ingest_raw` reuses the committed real pull unless
`FORCE_INGEST=1`; `load_warehouse` skips the reload when data is already present
unless `FORCE_RELOAD=1`. `dbt_test` is the quality gate — a failing test fails
the run and the BI refresh never happens. Verified end-to-end:
`airflow dags test chess_platform_pipeline` → `state=success`.

## Dashboards as code

`superset/bootstrap_superset.py` builds the Superset objects through the REST
API (idempotent by name): warehouse connection → datasets on each mart →
charts → dashboard. Two Superset-API gotchas are handled explicitly: a chart's
`query_context` must be saved for `/api/v1/chart/data` to return rows, and
attaching charts to a dashboard needs an explicit `PUT` (a `position_json`
alone does not link them). Every chart is verified against `/chart/data` after
creation.
