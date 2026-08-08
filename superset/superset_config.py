import os
# Superset metadata DB (its own Postgres), passed via DATABASE_URL
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://superset:superset@chess-superset-db/superset"
)
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "change-me")
# loopback demo behind Caddy/tunnel later — allow proxy headers, drop strict HTTPS talisman
ENABLE_PROXY_FIX = True
TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = True
FEATURE_FLAGS = {"DASHBOARD_RBAC": False, "EMBEDDED_SUPERSET": False}
CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
