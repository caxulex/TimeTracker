#!/usr/bin/env bash
# ============================================
# setup_test_db.sh — WSL/Linux-compatible
# Idempotently creates the time_tracker_test database on the
# configured Postgres instance. Does NOT run migrations.
# ============================================
set -euo pipefail

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-postgres}"
TEST_DB_NAME="${TEST_DB_NAME:-time_tracker_test}"

export PGPASSWORD

echo "[setup_test_db] target: postgresql://${PGUSER}:***@${PGHOST}:${PGPORT}/${TEST_DB_NAME}"

# Fail fast if psql is missing
if ! command -v psql >/dev/null 2>&1; then
  echo "[setup_test_db] ERROR: psql not found on PATH" >&2
  exit 1
fi

# Idempotent create: check first, then create
EXISTS=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '${TEST_DB_NAME}'" || true)

if [ "$EXISTS" = "1" ]; then
  echo "[setup_test_db] database '${TEST_DB_NAME}' already exists — no-op"
else
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres \
    -c "CREATE DATABASE ${TEST_DB_NAME} OWNER ${PGUSER};"
  echo "[setup_test_db] created database '${TEST_DB_NAME}'"
fi

echo "[setup_test_db] OK — resolved URL: postgresql+asyncpg://${PGUSER}:***@${PGHOST}:${PGPORT}/${TEST_DB_NAME}"
