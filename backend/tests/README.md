# Backend Tests

## Isolation strategy

Tests use **Option B: TRUNCATE-before-test**. An `autouse` async fixture in
[conftest.py](./conftest.py) (`_truncate_tables_around_test`) executes
`TRUNCATE <all public tables except alembic_version> RESTART IDENTITY CASCADE`
before every test. This is required because FastAPI route handlers call
`session.commit()` directly, so a nested-transaction / savepoint rollback
wrapper on `db_session` cannot contain their writes. TRUNCATE guarantees a
clean slate regardless of whatever previous tests or previous pytest runs
committed, and `RESTART IDENTITY` keeps autoincrement IDs deterministic.

The trade-off is runtime: a full suite takes ~16 minutes on a local
Windows dev box (vs. a few minutes with a pure in-memory transactional
strategy). Acceptable for now; revisit if the suite grows materially.

## Canonical local pytest command

From the repo root, with the virtualenv active:

```powershell
& .venv\Scripts\Activate.ps1
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker_test"
$env:TESTING = "1"
pytest -q
```

`TEST_DATABASE_URL` is read by [conftest.py](./conftest.py); if unset it
falls back to `DATABASE_URL`, then to the same localhost URL above.

## DB reset incantation

If the test DB drifts or migrations need to be re-applied from scratch:

```powershell
$env:PATH = "C:\Program Files\PostgreSQL\17\bin;$env:PATH"
$env:PGPASSWORD = "postgres"
psql -U postgres -h localhost -p 5432 -d postgres `
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='time_tracker_test' AND pid<>pg_backend_pid();" `
  -c "DROP DATABASE IF EXISTS time_tracker_test;" `
  -c "CREATE DATABASE time_tracker_test;"

& .venv\Scripts\Activate.ps1
cd backend
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker_test"
alembic upgrade head
```

The truncate fixture then keeps it clean across subsequent test runs.
