#!/bin/sh
# Apply migrations, optionally load demo data, then start the API.
set -e

echo "Applying database migrations…"
alembic upgrade head

if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  # Seeds only when the database is empty, so restarts never duplicate data.
  python -m app.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ${UVICORN_EXTRA_ARGS:-}
