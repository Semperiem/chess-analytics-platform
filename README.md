# Chess.com Analytics Platform

An **end-to-end analytics platform** built on real [chess.com public API](https://www.chess.com/news/view/published-data-api)
data: raw API → a warehouse → **three consumption layers** (BI dashboards,
a natural-language BI chatbot, and analytics notebooks), all wired together
by an orchestration DAG.

Everything below has been **stood up and run**:
`dbt build` is green, the Superset dashboard is built and its charts return
real rows, the WrenAI chatbot answers questions against the marts, the
notebook executes against the warehouse, and the full Airflow DAG completes
`state=success`.

## 🎬 90-second intro video

A short narrated walkthrough of the whole platform, the pipeline running, the
dbt tests, the Superset dashboard, the WrenAI chatbot answering in English, and
the notebook:

**▶ [Watch the intro (Google Drive)](https://drive.google.com/file/d/1t4jPEyIkMGl0gm0Grf2ME1F1KOTOaQnD/view?usp=sharing)**

## Architecture

```
                chess.com public API
                        │
             ┌──────────┴───────────┐  ingestion (chess.com API → parquet)
             │  ingest → transform   │
             └──────────┬───────────┘
                        ▼
        Postgres warehouse  ── public.dim_*/fact_*  (raw dimensional model)
                        │
                    dbt build + test         ← transform layer (staging → marts, ~50 tests)
                        ▼
        Postgres warehouse  ── marts.*  (curated, tested)
              │                     │                    │
              ▼                     ▼                    ▼
        Superset               WrenAI                Jupyter
        (dashboards)      (text-to-SQL BI chatbot)  (deep analytics)

        Orchestrated by Airflow:
        ingest → build dim model → load warehouse → dbt build → dbt test (gate)
                → refresh Superset + WrenAI
```

## The four layers (all real)

| Layer | Tool | What it is | Proof |
|---|---|---|---|
| **Transform** | dbt (dbt-postgres) | `staging → marts` models + ~50 data tests (ranges, unique combinations, cross-model reconciliation, business invariants) | `dbt build` → PASS=66, 0 errors |
| **Dashboards** | Apache Superset | 6-chart dashboard on the marts (retention line, games/day, segment pie, cohort bar, KPI, time-control table) | every chart verified via `/api/v1/chart/data` with real rows |
| **BI chatbot** | WrenAI | ask questions in English → generated SQL over the marts | *"Which recency segment has the most players?"* → `DENSE_RANK` SQL on `marts_mart_player_segments` → `active, 145` |
| **Notebooks** | Jupyter | analytics straight off the warehouse marts | `notebooks/04_warehouse_marts_analytics.ipynb` executed, plots inline |
| **Orchestration** | Apache Airflow | one DAG runs the whole chain with a dbt-test quality gate | `airflow dags test chess_platform_pipeline` → `state=success` |

## The warehouse

The warehouse is a `chess_wrenai_demo` Postgres. The raw
dimensional model (`public.dim_*`, `public.fact_*`) is loaded from the real
chess.com pull; **dbt** then builds the curated `marts.*` schema that Superset,
WrenAI, and the notebook all read from, one source of truth.

- `marts.mart_retention`: cohort × months-since-join → retention rate, denominator = full cohort population (254 rows)
- `marts.mart_growth_funnel`: per-cohort activation / month-3 / month-6 retention (133)
- `marts.mart_player_segments`: recency segment, title tier, tenure, engagement quartile (245)
- `marts.mart_time_class_performance`: games / win rate / avg rating by time control (9)
- `marts.mart_daily_games`: daily volume, distinct players, win rate (449)
- `marts.mart_rating_trend`: monthly avg rating per player × time control (216)
- plus conformed `marts.dim_players / dim_time_class / dim_date` and `fct_games / fct_player_monthly_activity`

## Data quality tests

The dbt suite goes well beyond `not_null`/`unique`. It combines four kinds of
checks (run as a gate in the pipeline):

- **Generic range/shape tests** (`dbt_utils`): `accepted_range` on rates
  (`retention_rate`, `win_rate` ∈ [0,1]) and ratings (100-3600),
  `unique_combination_of_columns` for composite grains, `not_null_proportion`.
- **Expression invariants** (`dbt_utils.expression_is_true`): e.g. in the growth
  funnel the month-6 window nests the month-3 window, so
  `active_by_month6 >= active_by_month3` must always hold.
- **A custom generic test** (`not_in_future`): no game/activity date may be after today.
- **Singular cross-model reconciliation tests** (`tests/*.sql`):
  `mart_daily_games` and `mart_time_class_performance` must reconcile exactly to
  the `fct_games` grain; every player has exactly one segment row; `rating_diff`
  must equal `player_rating - opponent_rating`; and active players can never
  exceed cohort size.

These caught a real bug: the original retention denominator (players active in
month 0) let later-month re-activations push retention **above 100%**. The
`accepted_range` test failed on 10 rows; `mart_retention` now uses the full
cohort population as the denominator, and the suite is green.

## Quickstart

```bash
cp .env.example .env                 # fill in the warehouse password
cp superset/.env.example superset/.env   # set a Superset secret + admin password
make venv                            # platform venv (dbt, pandas, jupyter, ...)

make dbt          # build + test the marts
make superset-up  # bring up the dedicated Superset stack (127.0.0.1:8108)
make bootstrap    # warehouse connection + datasets + charts + dashboard
make wrenai       # (re)deploy the marts into the WrenAI model
make notebook     # execute the warehouse analytics notebook
make pipeline     # run the whole thing as one Airflow DAG
```

Then open **Superset** at `http://127.0.0.1:8108` (dashboard *Chess.com Player
Analytics*) and the **WrenAI** chatbot at `http://127.0.0.1:8602`.

## Repo layout

```
dbt/                 staging → marts models + ~50 tests (dbt-postgres)
superset/            dedicated Superset stack + REST bootstrap (dashboard as code)
airflow/dags/        chess_platform_pipeline.py, the end-to-end orchestration DAG
notebooks/           04_warehouse_marts_analytics.ipynb (executed off the marts)
scripts/             refresh_wrenai.sh (redeploy marts into the WrenAI model)
ingestion/           the ingestion stage (chess.com API → parquet)
docs/                architecture.md, demo_script.md
Makefile             one-command targets (make up)
```

## Honest caveats

This is a titled-player sample (GM/IM/FM/etc.), not a random slice of the
player base, so absolute numbers read as directionally useful rather than
typical of a new signup. The data is a fixed real pull, not a rolling feed.
Superset runs as its own instance.

## Tech stack

chess.com API · Postgres (warehouse) · **dbt** (transform + tests) · **Apache
Superset** (dashboards) · **WrenAI** + Ollama `qwen3-coder:30b` (text-to-SQL
BI chatbot) · **Jupyter/pandas** (notebooks) · **Apache Airflow** (orchestration)
· Docker Compose.
