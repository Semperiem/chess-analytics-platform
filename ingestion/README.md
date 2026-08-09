# Ingestion

The ingestion stage pulls real data from the chess.com public API and shapes it
for the warehouse:

- `ingest`: pulls titled players, profiles, and monthly game archives from the
  chess.com public API into `data/raw/*.json`.
- `transform`: reshapes the raw JSON into `data/processed/*.parquet`.

The platform's Airflow DAG runs this as its `ingest_raw` task (opt-in via
`FORCE_INGEST=1`); `build_dimensional` then turns the parquet into the
warehouse's raw dimensional model. By default the DAG reuses an existing pull so
a demo run is fast and doesn't hammer the public API.

To do a fresh pull:
```bash
python -m chess_analytics.ingest --n-cohort 250 --n-deep 30 --deep-months 4
python -m chess_analytics.transform
```
