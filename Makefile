# Chess.com analytics platform — one-command targets.
# Prereqs: the chess-wrenai Postgres + WrenAI stack running; .env and superset/.env filled in.
SHELL := /bin/bash
ROOT := $(shell pwd)
VENV := $(ROOT)/.venv/bin
DBT  := $(HOME)/.local/bin/dbt

.PHONY: venv dbt superset-up bootstrap wrenai notebook pipeline up down

venv:            ## create the platform venv
	python3 -m venv .venv && $(VENV)/pip install -q -r requirements.txt

dbt:             ## build + test the marts
	set -a; source .env; set +a; DBT_PROFILES_DIR=$(ROOT)/dbt $(DBT) build --project-dir $(ROOT)/dbt

superset-up:     ## bring up the dedicated Superset stack
	cd superset && docker compose --env-file .env -f docker-compose.superset.yml up -d

bootstrap:       ## warehouse connection + datasets + charts + dashboard
	set -a; source superset/.env; set +a; cd superset && $(VENV)/python bootstrap_superset.py

wrenai:          ## (re)deploy the marts into the WrenAI model
	set -a; source .env; set +a; bash scripts/refresh_wrenai.sh

notebook:        ## execute the warehouse analytics notebook
	set -a; source .env; set +a; $(VENV)/jupyter nbconvert --to notebook --execute --inplace \
	  --ExecutePreprocessor.timeout=120 notebooks/04_warehouse_marts_analytics.ipynb

pipeline:        ## run the full Airflow DAG end-to-end
	set -a; source .env; set +a; \
	AIRFLOW_HOME=$(ROOT)/.airflow_home \
	AIRFLOW__CORE__DAGS_FOLDER=$(ROOT)/airflow/dags \
	AIRFLOW__CORE__LOAD_EXAMPLES=False \
	$(ANALYTICS_VENV)/airflow dags test chess_platform_pipeline $$(date +%F)

up: superset-up dbt bootstrap wrenai  ## stand the whole platform up
	@echo "platform up: Superset http://127.0.0.1:$${SUPERSET_PORT:-8108}  |  WrenAI http://127.0.0.1:8602"

down:            ## stop Superset (warehouse + WrenAI are shared, left running)
	cd superset && docker compose -f docker-compose.superset.yml down
