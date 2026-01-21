#!/bin/bash
# =============================================================================
# TimeTracker Database Restore Script
# =============================================================================
# This script restores a PostgreSQL backup for the TimeTracker app.
#
# USAGE:
#   ./restore_database.sh /path/to/backup.sql.gz
#   ./restore_database.sh --latest              # Restore most recent backup
#   ./restore_database.sh --list                # List available backups
#
# WARNING: This will REPLACE all data in the database!
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups}"
DB_CONTAINER="${DB_CONTAINER:-timetracker-db}"
DB_NAME="${DB_NAME:-time_tracker}"
DB_USER="${DB_USER:-postgres}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# FUNCTIONS
# =============================================================================

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

list_backups() {
    echo ""
    echo "Available backups:"
    echo "=================="
    echo ""
    echo "Daily backups:"
    ls -lh "$BACKUP_DIR/daily"/*.sql.gz 2>/dev/null || echo "  (none)"
    echo ""
    echo "Weekly backups:"
    ls -lh "$BACKUP_DIR/weekly"/*.sql.gz 2>/dev/null || echo "  (none)"
    echo ""
}

get_latest_backup() {
    find "$BACKUP_DIR" -name "*.sql.gz" -type f -printf '%T@ %p\n' 2>/dev/null | \
        sort -n | tail -1 | cut -d' ' -f2-
}

# =============================================================================
# MAIN
# =============================================================================

# Handle arguments
case "$1" in
    --list|-l)
        list_backups
        exit 0
        ;;
    --latest)
        BACKUP_FILE=$(get_latest_backup)
        if [[ -z "$BACKUP_FILE" ]]; then
            error "No backups found in $BACKUP_DIR"
        fi
        log "Using latest backup: $BACKUP_FILE"
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS] [BACKUP_FILE]"
        echo ""
        echo "Options:"
        echo "  --latest    Restore the most recent backup"
        echo "  --list      List all available backups"
        echo "  --help      Show this help message"
        echo ""
        echo "Example:"
        echo "  $0 /home/ubuntu/backups/daily/time_tracker_daily_20260121_020000.sql.gz"
        exit 0
        ;;
    "")
        error "Please specify a backup file or use --latest"
        ;;
    *)
        BACKUP_FILE="$1"
        ;;
esac

# Verify backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    error "Backup file not found: $BACKUP_FILE"
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    error "Database container '$DB_CONTAINER' is not running"
fi

# Show backup info
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup file: $BACKUP_FILE"
log "Backup size: $BACKUP_SIZE"

# Confirm with user
echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  WARNING: This will REPLACE ALL DATA in the database!       ║${NC}"
echo -e "${RED}║  Database: $DB_NAME                                          ${NC}"
echo -e "${RED}║  Container: $DB_CONTAINER                                    ${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    log "Restore cancelled by user"
    exit 0
fi

# Create a backup of current state before restore
log "Creating safety backup of current database state..."
SAFETY_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$SAFETY_BACKUP"
log "Safety backup created: $SAFETY_BACKUP"

# Stop backend container to prevent connections
log "Note: You may want to stop the backend container during restore"
warn "Connections during restore may cause issues"

# Restore the database
log "Starting database restore..."

# Drop existing connections
log "Terminating existing database connections..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true

# Drop and recreate database
log "Recreating database..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"

# Restore from backup
log "Restoring data from backup..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1

# Verify restore
log "Verifying restore..."
TABLE_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
log "Tables restored: $TABLE_COUNT"

echo ""
log "=========================================="
log "Database restore completed successfully!"
log "=========================================="
log "Safety backup available at: $SAFETY_BACKUP"
echo ""
warn "Remember to restart your backend service if it was stopped"

exit 0
