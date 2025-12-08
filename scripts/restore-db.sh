#!/bin/bash
# =============================================
# TIME TRACKER - DATABASE RESTORE SCRIPT
# TASK-063: Create restore scripts
# =============================================

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-time_tracker}"
DB_USER="${DB_USER:-postgres}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_prompt() {
    echo -e "${BLUE}[PROMPT]${NC} $1"
}

# Show usage
usage() {
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Arguments:"
    echo "  backup_file    Path to the backup file (.sql.gz)"
    echo ""
    echo "Environment variables:"
    echo "  DB_HOST        Database host (default: localhost)"
    echo "  DB_PORT        Database port (default: 5432)"
    echo "  DB_NAME        Database name (default: time_tracker)"
    echo "  DB_USER        Database user (default: postgres)"
    echo ""
    echo "Example:"
    echo "  $0 /backups/time_tracker_20240115_120000.sql.gz"
    exit 1
}

# Check arguments
if [ -z "$1" ]; then
    log_error "Backup file not specified!"
    usage
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Verify it's a gzip file
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log_error "Backup file is not a valid gzip file!"
    exit 1
fi

log_info "Restore Configuration:"
log_info "  Database: $DB_NAME @ $DB_HOST:$DB_PORT"
log_info "  Backup file: $BACKUP_FILE"
log_info "  File size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Confirmation prompt
log_warn "This will DROP all existing data in $DB_NAME!"
log_prompt "Are you sure you want to continue? (yes/no)"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Restore cancelled."
    exit 0
fi

# Create backup of current database before restore
CURRENT_BACKUP="${BACKUP_DIR}/pre_restore_${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"
log_info "Creating backup of current database..."
if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-password --format=plain | gzip > "$CURRENT_BACKUP" 2>/dev/null; then
    log_info "Current database backed up to: $CURRENT_BACKUP"
else
    log_warn "Could not backup current database (may be empty)"
fi

# Drop and recreate database
log_info "Dropping existing database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $DB_NAME;" --no-password

log_info "Creating fresh database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "CREATE DATABASE $DB_NAME;" --no-password

# Restore from backup
log_info "Restoring database from backup..."
if gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --no-password --quiet; then
    log_info "Database restored successfully!"
else
    log_error "Restore failed!"
    log_info "You can manually restore the pre-restore backup from: $CURRENT_BACKUP"
    exit 1
fi

# Verify restore
log_info "Verifying restore..."
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" --no-password)
log_info "Tables restored: $(echo $TABLE_COUNT | tr -d ' ')"

log_info "Restore completed successfully!"
