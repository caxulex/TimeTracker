# ============================================
# setup_test_db.ps1 - Windows-native fallback
# Idempotently creates the time_tracker_test database on the configured
# Postgres instance. Does NOT run migrations.
# ============================================
[CmdletBinding()]
param(
    [string]$PgHost = $(if ($env:PGHOST) { $env:PGHOST } else { 'localhost' }),
    [int]   $PgPort = $(if ($env:PGPORT) { [int]$env:PGPORT } else { 5432 }),
    [string]$PgUser = $(if ($env:PGUSER) { $env:PGUSER } else { 'postgres' }),
    [string]$PgPassword = $(if ($env:PGPASSWORD) { $env:PGPASSWORD } else { 'postgres' }),
    [string]$TestDbName = $(if ($env:TEST_DB_NAME) { $env:TEST_DB_NAME } else { 'time_tracker_test' })
)

$ErrorActionPreference = 'Stop'

# Resolve psql (PATH first, then common Windows install locations)
$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $candidates = @(
        'C:\Program Files\PostgreSQL\17\bin\psql.exe',
        'C:\Program Files\PostgreSQL\16\bin\psql.exe',
        'C:\Program Files\PostgreSQL\15\bin\psql.exe'
    )
    $psql = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $psql) {
    Write-Error "psql not found on PATH or in standard Postgres install locations."
    exit 1
}

$env:PGPASSWORD = $PgPassword
Write-Host "[setup_test_db] target: postgresql://${PgUser}:***@${PgHost}:${PgPort}/${TestDbName}"

$existsRaw = & $psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc `
    "SELECT 1 FROM pg_database WHERE datname = '$TestDbName'"
$exists = ($existsRaw | Out-String).Trim()

if ($exists -eq '1') {
    Write-Host "[setup_test_db] database '$TestDbName' already exists - no-op"
}
else {
    & $psql -h $PgHost -p $PgPort -U $PgUser -d postgres `
        -c "CREATE DATABASE $TestDbName OWNER $PgUser;"
    if ($LASTEXITCODE -ne 0) { throw "CREATE DATABASE failed (exit $LASTEXITCODE)" }
    Write-Host "[setup_test_db] created database '$TestDbName'"
}

Write-Host "[setup_test_db] OK - resolved URL: postgresql+asyncpg://${PgUser}:***@${PgHost}:${PgPort}/${TestDbName}"
