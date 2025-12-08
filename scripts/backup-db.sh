#!/bin/bash
# =============================================
# TIME TRACKER - DATABASE BACKUP SCRIPT
# TASK-063: Create backup scripts
# =============================================

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-time_tracker}"
DB_USER="${DB_USER:-postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log_info "Starting database backup..."
log_info "Database: $DB_NAME"
log_info "Output: $BACKUP_FILE"

# Perform backup
if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-password \
    --format=plain \
    --no-owner \
    --no-privileges \
    | gzip > "$BACKUP_FILE"; then
    
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Backup completed successfully!"
    log_info "Backup size: $BACKUP_SIZE"
else
    log_error "Backup failed!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify backup
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log_info "Backup integrity verified"
else
    log_error "Backup file is corrupted!"
    exit 1
fi

# Clean up old backups
log_info "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
REMAINING_BACKUPS=$(ls -1 "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null | wc -l)
log_info "Remaining backups: $REMAINING_BACKUPS"

# Optional: Upload to S3 if configured
if [ -n "$AWS_S3_BUCKET" ]; then
    log_info "Uploading to S3: s3://$AWS_S3_BUCKET/backups/"
    if aws s3 cp "$BACKUP_FILE" "s3://$AWS_S3_BUCKET/backups/"; then
        log_info "S3 upload completed"
    else
        log_warn "S3 upload failed (backup saved locally)"
    fi
fi

# Optional: Upload to Azure Blob if configured
if [ -n "$AZURE_STORAGE_CONNECTION_STRING" ] && [ -n "$AZURE_CONTAINER_NAME" ]; then
    log_info "Uploading to Azure Blob Storage..."
    if az storage blob upload \
        --file "$BACKUP_FILE" \
        --container-name "$AZURE_CONTAINER_NAME" \
        --name "backups/$(basename $BACKUP_FILE)"; then
        log_info "Azure upload completed"
    else
        log_warn "Azure upload failed (backup saved locally)"
    fi
fi

log_info "Backup process completed!"
echo "$BACKUP_FILE"
