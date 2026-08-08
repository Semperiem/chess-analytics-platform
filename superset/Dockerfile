FROM apache/superset:latest
USER root
# stock image's uv-managed venv has no postgres driver; bake it in
RUN uv pip install --python /app/.venv/bin/python --no-cache psycopg2-binary
USER superset
