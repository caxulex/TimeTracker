# Dev Setup — Backend Test Environment (no Docker)

This project's Phase 0 baseline must run the backend test suite against a real
PostgreSQL + Redis, without Docker. Two supported paths:

- **Path A (Hybrid — recommended)**: reuse an existing native Windows
  PostgreSQL on `localhost:5432`, plus Redis running inside **WSL2 Ubuntu**
  (apt `redis-server`). This matches production (Ubuntu on AWS Lightsail)
  for Redis while avoiding a second Postgres install on the workstation.
- **Path B (Windows-native fallback)**: native Windows Postgres + Memurai
  Developer Edition as a Redis drop-in. Use only when WSL2 is not available.

The test connection string is env-driven; see
[.env.example](../.env.example) and `backend/tests/conftest.py`. Default:

```
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker_test
```

---

## Path A — Hybrid (recommended)

### 1. Verify WSL2 + Ubuntu

```powershell
wsl -l -v
# Expect a distro "Ubuntu" with VERSION 2.
```

### 2. Install and start Redis inside WSL

```powershell
wsl -d Ubuntu -- bash -lc "sudo apt update && sudo apt install -y redis-server"
wsl -d Ubuntu -- bash -lc "sudo service redis-server start && redis-cli ping"
# Expected output: PONG
```

WSL2 auto-forwards listening ports, so `localhost:6379` on Windows reaches
the WSL redis.

> To make Redis survive WSL restarts, either run
> `wsl -d Ubuntu -- bash -lc "sudo service redis-server start"` at login,
> or enable systemd in `/etc/wsl.conf` and `systemctl enable redis-server`.

### 3. Verify the existing native Windows Postgres on 5432

```powershell
Get-Service postgresql-x64-* | Format-Table Name, Status
$env:PGPASSWORD = "postgres"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5432 -U postgres -c "SELECT version();"
```

### 4. Create the test database (idempotent)

From the repo root:

```powershell
powershell -File backend\scripts\setup_test_db.ps1
```

Or from WSL:

```bash
bash backend/scripts/setup_test_db.sh
```

### 5. Apply migrations against the test DB

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker_test"
$env:DATABASE_URL      = $env:TEST_DATABASE_URL  # alembic/env.py reads DATABASE_URL
Push-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
```

### 6. Run the test suite

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker_test"
Push-Location backend
..\.venv\Scripts\python.exe -m pytest -x --tb=short
Pop-Location
```

---

## Path B — Windows-native (fallback only)

### 1. Install Memurai Developer Edition

Download from <https://www.memurai.com/get-memurai> (free Developer tier).
Install it and register as a Windows service. Verify:

```powershell
Get-Service Memurai | Format-Table Name, Status
redis-cli ping   # or: & 'C:\Program Files\Memurai\memurai-cli.exe' ping
# Expected: PONG
```

### 2. Postgres + test DB + migrations + pytest

Identical to Path A steps 3 – 6.

---

## Troubleshooting

- `psql: error: connection to server at "localhost" (::1), port 5432 failed`
  — the Windows Postgres service is not started. `Start-Service postgresql-x64-16`.
- `redis-cli: command not found` (WSL) — service never started;
  `sudo service redis-server start`.
- Tests complain about `TEST_DATABASE_URL` — confirm the env var is set in
  the same shell that runs `pytest`. `conftest.py` also honours
  `DATABASE_URL` as a legacy fallback.
