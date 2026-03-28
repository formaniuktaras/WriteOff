#!/usr/bin/env sh
set -eu

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-writeoff}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
  sleep 1
done

echo "PostgreSQL is ready. Running migrations..."
alembic upgrade head

echo "Initializing storage..."
python scripts/init_storage.py

echo "Starting web server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
