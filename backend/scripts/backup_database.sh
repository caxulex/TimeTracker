#!/bin/bash
# =============================================================================
# TimeTracker Database Backup Script
# =============================================================================
# This script creates automated PostgreSQL backups for the TimeTracker app.
# 
# SETUP INSTRUCTIONS:
# 1. Copy this script to your production server:
#    scp backup_database.sh ubuntu@your-server:/home/ubuntu/scripts/
#
# 2. Make it executable:
#    chmod +x /home/ubuntu/scripts/backup_database.sh
#
# 3. Add to crontab for daily backups at 2 AM:
#    crontab -e
#    0 2 * * * /home/ubuntu/scripts/backup_database.sh >> /home/ubuntu/backups/cron.log 2>&1
#
# 4. For weekly full backups (Sundays at 3 AM):
#    0 3 * * 0 /home/ubuntu/scripts/backup_database.sh --full >> /home/ubuntu/backups/cron.log 2>&1
#
# =============================================================================

set -e  # Exit on error

# =============================================================================
# CONFIGURATION - Modify these values for your environment
# =============================================================================
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_CONTAINER="${DB_CONTAINER:-timetracker-db-1}"
DB_NAME="${DB_NAME:-time_tracker}"
DB_USER="${DB_USER:-postgres}"

# AWS S3 Configuration (optional - leave empty to skip S3 upload)
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-timetracker/daily}"

# Notification (optional - set webhook URL for Slack/Discord notifications)
WEBHOOK_URL="${WEBHOOK_URL:-}"

# =============================================================================
# DO NOT MODIFY BELOW THIS LINE
# =============================================================================

DATE=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)
BACKUP_TYPE="daily"
LOG_FILE="$BACKUP_DIR/backup.log"

# Parse arguments
if [[ "$1" == "--full" ]]; then
    BACKUP_TYPE="full"
fi

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR/daily"
mkdir -p "$BACKUP_DIR/weekly"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"❌ TimeTracker Backup FAILED: $1\"}" \
            "$WEBHOOK_URL" > /dev/null 2>&1 || true
    fi
    exit 1
}

# Success notification
notify_success() {
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"✅ TimeTracker Backup completed: $1\"}" \
            "$WEBHOOK_URL" > /dev/null 2>&1 || true
    fi
}

log "=========================================="
log "Starting $BACKUP_TYPE backup..."
log "=========================================="

# Check if Docker container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    error_exit "Database container '$DB_CONTAINER' is not running"
fi

# Determine backup location based on type
if [[ "$BACKUP_TYPE" == "full" ]] || [[ "$DAY_OF_WEEK" == "7" ]]; then
    BACKUP_SUBDIR="weekly"
    BACKUP_FILE="$BACKUP_DIR/$BACKUP_SUBDIR/${DB_NAME}_weekly_$DATE.sql.gz"
else
    BACKUP_SUBDIR="daily"
    BACKUP_FILE="$BACKUP_DIR/$BACKUP_SUBDIR/${DB_NAME}_daily_$DATE.sql.gz"
fi

log "Backup file: $BACKUP_FILE"

# Create the backup
log "Creating PostgreSQL dump..."
if ! docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" 2>/dev/null | gzip > "$BACKUP_FILE"; then
    error_exit "Failed to create database dump"
fi

# Verify backup was created and has content
if [[ ! -f "$BACKUP_FILE" ]]; then
    error_exit "Backup file was not created"
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
if [[ $(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null) -lt 1000 ]]; then
    error_exit "Backup file is suspiciously small (< 1KB)"
fi

log "Backup created successfully: $BACKUP_SIZE"

# Upload to S3 if configured
if [[ -n "$S3_BUCKET" ]]; then
    log "Uploading to S3: s3://$S3_BUCKET/$S3_PREFIX/"
    if aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/$S3_PREFIX/" --quiet; then
        log "S3 upload successful"
    else
        log "WARNING: S3 upload failed (backup still saved locally)"
    fi
fi

# Clean up old backups (local)
log "Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=$(find "$BACKUP_DIR/daily" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
log "Deleted $DELETED_COUNT old daily backup(s)"

# Keep weekly backups for 90 days
DELETED_WEEKLY=$(find "$BACKUP_DIR/weekly" -name "*.sql.gz" -mtime +90 -delete -print | wc -l)
log "Deleted $DELETED_WEEKLY old weekly backup(s)"

# Show current backup status
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "*.sql.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "Total backups: $TOTAL_BACKUPS files, $TOTAL_SIZE total size"

log "=========================================="
log "Backup completed successfully!"
log "=========================================="

notify_success "$BACKUP_FILE ($BACKUP_SIZE)"

exit 0
