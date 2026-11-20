#!/bin/sh
# Runs before the backend starts: migrations, optional demo data, then the server.
set -e

if [ -f alembic.ini ]; then
  echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
  alembic upgrade head
else
  echo "[entrypoint] alembic.ini not found yet - skipping migrations."
fi

if [ "$SEED_ON_START" = "true" ] && [ -s scripts/seed.py ]; then
  echo "[entrypoint] Loading demo data (python -m scripts.seed)..."
  python -m scripts.seed
fi

exec "$@"
