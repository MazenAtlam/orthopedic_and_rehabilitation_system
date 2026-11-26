#!/bin/sh
# Runs before the backend starts: migrations, WHO ICD-10 catalogue, optional demo data, then the server.
set -e

if [ -f alembic.ini ]; then
  echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
  alembic upgrade head
else
  echo "[entrypoint] alembic.ini not found yet - skipping migrations."
fi

if [ "${LOAD_ICD10_ON_START:-true}" = "true" ]; then
  echo "[entrypoint] Ensuring full WHO ICD-10 orthopedic catalogue..."
  python -m scripts.load_icd10 --ensure
fi

if [ "${SEED_ON_START:-}" = "true" ] && [ "${DEMO_MODE:-}" = "1" ] && [ "${APP_ENV:-development}" != "production" ]; then
  echo "[entrypoint] Loading demo data (python -m scripts.seed)..."
  python -m scripts.seed
fi

exec "$@"
