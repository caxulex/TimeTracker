# =============================================
# TIME TRACKER - DATABASE BACKUP SCRIPT (Windows)
# TASK-063: Create backup scripts
# =============================================

param(
    [string]$BackupDir = ".\backups",
    [string]$DbHost = "localhost",
    [int]$DbPort = 5434,
    [string]$DbName = "time_tracker",
    [string]$DbUser = "postgres",
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

# Configuration
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir "${DbName}_${Timestamp}.sql"
$CompressedFile = "${BackupFile}.gz"

function Write-Info($Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err($Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Create backup directory
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

Write-Info "Starting database backup..."
Write-Info "Database: $DbName"
Write-Info "Output: $CompressedFile"

# Check for pg_dump
$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    # Try common PostgreSQL installation paths
    $possiblePaths = @(
        "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\13\bin\pg_dump.exe"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $pgDump = $path
            break
        }
    }
    
    if (-not $pgDump) {
        Write-Err "pg_dump not found! Please install PostgreSQL or add it to PATH."
        exit 1
    }
}

# Perform backup
try {
    $env:PGPASSWORD = $env:DB_PASSWORD
    if (-not $env:PGPASSWORD) {
        Write-Warn "DB_PASSWORD not set. Using 'postgres' as default."
        $env:PGPASSWORD = "postgres"
    }
    
    & $pgDump -h $DbHost -p $DbPort -U $DbUser -d $DbName `
        --no-owner --no-privileges -f $BackupFile
    
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }
    
    Write-Info "Database dump created successfully"
} catch {
    Write-Err "Backup failed: $_"
    Remove-Item $BackupFile -ErrorAction SilentlyContinue
    exit 1
}

# Compress backup
try {
    Write-Info "Compressing backup..."
    $content = Get-Content $BackupFile -Raw
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
    
    $output = [System.IO.File]::Create($CompressedFile)
    $gzip = New-Object System.IO.Compression.GZipStream($output, [System.IO.Compression.CompressionMode]::Compress)
    $gzip.Write($bytes, 0, $bytes.Length)
    $gzip.Close()
    $output.Close()
    
    # Remove uncompressed file
    Remove-Item $BackupFile
    
    $backupSize = (Get-Item $CompressedFile).Length
    $backupSizeMB = [math]::Round($backupSize / 1MB, 2)
    Write-Info "Backup compressed: ${backupSizeMB}MB"
} catch {
    Write-Err "Compression failed: $_"
    exit 1
}

# Clean up old backups
Write-Info "Cleaning up backups older than $RetentionDays days..."
$cutoffDate = (Get-Date).AddDays(-$RetentionDays)
$oldBackups = Get-ChildItem -Path $BackupDir -Filter "${DbName}_*.sql.gz" | 
    Where-Object { $_.LastWriteTime -lt $cutoffDate }

if ($oldBackups) {
    $oldBackups | Remove-Item -Force
    Write-Info "Removed $($oldBackups.Count) old backup(s)"
}

$remainingBackups = (Get-ChildItem -Path $BackupDir -Filter "${DbName}_*.sql.gz").Count
Write-Info "Remaining backups: $remainingBackups"

Write-Info "Backup process completed!"
Write-Host $CompressedFile
