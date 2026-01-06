#!/bin/bash
# ============================================
# TIME TRACKER - FULL BACKUP RESTORE SCRIPT
# ============================================
# Disaster recovery script for full client restoration.
# Restores database, uploads, configuration, and verifies integrity.
#
# Usage:
#   ./restore-backup.sh backup_file.tar.gz
#   ./restore-backup.sh --list                # List available backups
#   ./restore-backup.sh --verify FILE         # Verify backup integrity
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RESTORE_TEMP="${RESTORE_TEMP:-/tmp/timetracker_restore}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Docker container names (adjust for your setup)
DB_CONTAINER="${DB_CONTAINER:-timetracker-db}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-timetracker-backend}"
FRONTEND_CONTAINER="${FRONTEND_CONTAINER:-timetracker-frontend}"

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }
log_success() { echo -e "${CYAN}[SUCCESS]${NC} $1"; }

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           TIME TRACKER - BACKUP RESTORE                     ║"
    echo "║           Disaster Recovery Tool                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS] [BACKUP_FILE]"
    echo ""
    echo "Options:"
    echo "  --list              List available backups in BACKUP_DIR"
    echo "  --verify FILE       Verify backup integrity without restoring"
    echo "  --db-only           Restore database only (skip uploads/config)"
    echo "  --no-confirm        Skip confirmation prompts (dangerous!)"
    echo "  --dry-run           Show what would be restored without doing it"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR          Backup directory (default: ./backups)"
    echo "  DB_CONTAINER        PostgreSQL container name"
    echo "  COMPOSE_FILE        Docker compose file to use"
    echo ""
    echo "Examples:"
    echo "  $0 backups/full_20260106_120000.tar.gz"
    echo "  $0 --verify backups/full_20260106_120000.tar.gz"
    echo "  $0 --list"
    echo "  $0 --db-only backups/db_20260106_120000.sql.gz"
}

# List available backups
list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory does not exist: $BACKUP_DIR"
        exit 1
    fi
    
    # Find and list backup files
    echo -e "${CYAN}Full Backups (.tar.gz):${NC}"
    find "$BACKUP_DIR" -maxdepth 1 -name "full_*.tar.gz" -type f -printf "  %f  (%s bytes, %Tc)\n" 2>/dev/null | sort -r | head -20
    
    echo ""
    echo -e "${CYAN}Database Backups (.sql.gz):${NC}"
    find "$BACKUP_DIR" -maxdepth 1 -name "db_*.sql.gz" -type f -printf "  %f  (%s bytes, %Tc)\n" 2>/dev/null | sort -r | head -20
    
    echo ""
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    BACKUP_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 \( -name "*.tar.gz" -o -name "*.sql.gz" \) -type f | wc -l)
    echo -e "Total: ${GREEN}$BACKUP_COUNT${NC} backups, ${GREEN}$TOTAL_SIZE${NC} total size"
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"
    
    log_step "Verifying backup integrity: $backup_file"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    # Check file extension and verify accordingly
    if [[ "$backup_file" == *.tar.gz ]]; then
        log_info "Checking tar.gz archive integrity..."
        if tar -tzf "$backup_file" > /dev/null 2>&1; then
            log_success "Archive integrity: OK"
            
            # List contents
            echo ""
            log_info "Archive contents:"
            tar -tzf "$backup_file" | head -30
            
            # Check for required files
            local has_db=$(tar -tzf "$backup_file" 2>/dev/null | grep -c "database.sql" || true)
            local has_config=$(tar -tzf "$backup_file" 2>/dev/null | grep -c ".env" || true)
            
            echo ""
            log_info "Backup components:"
            [ "$has_db" -gt 0 ] && echo -e "  ${GREEN}✓${NC} Database dump" || echo -e "  ${YELLOW}✗${NC} Database dump (missing)"
            [ "$has_config" -gt 0 ] && echo -e "  ${GREEN}✓${NC} Configuration" || echo -e "  ${YELLOW}✗${NC} Configuration (missing)"
            
        else
            log_error "Archive is corrupted!"
            exit 1
        fi
        
    elif [[ "$backup_file" == *.sql.gz ]]; then
        log_info "Checking gzip integrity..."
        if gzip -t "$backup_file" 2>/dev/null; then
            log_success "Gzip integrity: OK"
            
            # Show size info
            local compressed_size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file" 2>/dev/null)
            local uncompressed_size=$(gzip -l "$backup_file" | tail -1 | awk '{print $2}')
            echo -e "  Compressed:   $(numfmt --to=iec $compressed_size 2>/dev/null || echo "$compressed_size bytes")"
            echo -e "  Uncompressed: $(numfmt --to=iec $uncompressed_size 2>/dev/null || echo "$uncompressed_size bytes")"
        else
            log_error "Gzip file is corrupted!"
            exit 1
        fi
    else
        log_error "Unknown backup format. Expected .tar.gz or .sql.gz"
        exit 1
    fi
}

# Check if containers are running
check_containers() {
    log_step "Checking container status..."
    
    local db_running=$(docker ps --filter "name=$DB_CONTAINER" --format "{{.Names}}" 2>/dev/null | grep -c "$DB_CONTAINER" || true)
    
    if [ "$db_running" -eq 0 ]; then
        log_warn "Database container '$DB_CONTAINER' is not running"
        log_info "Attempting to start containers..."
        docker compose -f "$COMPOSE_FILE" up -d db redis
        sleep 5
    fi
    
    log_success "Container check complete"
}

# Stop application (keep database running)
stop_application() {
    log_step "Stopping application containers..."
    docker compose -f "$COMPOSE_FILE" stop backend frontend 2>/dev/null || true
    log_success "Application stopped"
}

# Restore database from SQL dump
restore_database() {
    local dump_file="$1"
    
    log_step "Restoring database..."
    
    # Decompress if needed
    if [[ "$dump_file" == *.gz ]]; then
        log_info "Decompressing dump file..."
        gunzip -c "$dump_file" > "$RESTORE_TEMP/database.sql"
        dump_file="$RESTORE_TEMP/database.sql"
    fi
    
    # Get database credentials from environment or docker compose
    local db_name="${DB_NAME:-time_tracker}"
    local db_user="${DB_USER:-postgres}"
    
    # Drop existing connections and restore
    log_info "Terminating existing connections..."
    docker exec "$DB_CONTAINER" psql -U "$db_user" -c "
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '$db_name'
        AND pid <> pg_backend_pid();
    " 2>/dev/null || true
    
    log_info "Dropping and recreating database..."
    docker exec "$DB_CONTAINER" psql -U "$db_user" -c "DROP DATABASE IF EXISTS $db_name;" 2>/dev/null || true
    docker exec "$DB_CONTAINER" psql -U "$db_user" -c "CREATE DATABASE $db_name;" 2>/dev/null
    
    log_info "Restoring data..."
    docker exec -i "$DB_CONTAINER" psql -U "$db_user" -d "$db_name" < "$dump_file"
    
    log_success "Database restored successfully"
}

# Restore uploads directory
restore_uploads() {
    local uploads_archive="$1"
    
    if [ -f "$uploads_archive" ]; then
        log_step "Restoring uploads..."
        
        # Create uploads directory if needed
        mkdir -p ./uploads
        
        # Extract uploads
        tar -xzf "$uploads_archive" -C ./uploads 2>/dev/null || \
        tar -xf "$uploads_archive" -C ./uploads
        
        log_success "Uploads restored"
    else
        log_warn "No uploads archive found, skipping..."
    fi
}

# Restore configuration (with confirmation)
restore_config() {
    local config_file="$1"
    
    if [ -f "$config_file" ]; then
        log_step "Restoring configuration..."
        
        if [ -f ".env" ]; then
            log_warn "Existing .env file will be backed up to .env.pre-restore"
            cp .env .env.pre-restore
        fi
        
        cp "$config_file" .env
        log_success "Configuration restored (review .env before starting)"
    else
        log_warn "No configuration file found in backup"
    fi
}

# Start application
start_application() {
    log_step "Starting application..."
    docker compose -f "$COMPOSE_FILE" up -d
    
    # Wait for health check
    log_info "Waiting for application to be healthy..."
    sleep 10
    
    # Check health
    local health_ok=false
    for i in {1..30}; do
        if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
            health_ok=true
            break
        fi
        sleep 2
    done
    
    if [ "$health_ok" = true ]; then
        log_success "Application is healthy!"
    else
        log_warn "Health check timed out. Check logs with: docker compose logs"
    fi
}

# Full restore from tar.gz archive
restore_full() {
    local backup_file="$1"
    local db_only="$2"
    
    log_step "Extracting backup archive..."
    
    # Create temp directory
    rm -rf "$RESTORE_TEMP"
    mkdir -p "$RESTORE_TEMP"
    
    # Extract archive
    tar -xzf "$backup_file" -C "$RESTORE_TEMP"
    
    # Find and restore database
    local db_dump=$(find "$RESTORE_TEMP" -name "*.sql" -o -name "*.sql.gz" | head -1)
    if [ -n "$db_dump" ]; then
        restore_database "$db_dump"
    else
        log_error "No database dump found in archive!"
        exit 1
    fi
    
    if [ "$db_only" != "true" ]; then
        # Restore uploads if present
        local uploads_archive=$(find "$RESTORE_TEMP" -name "uploads*.tar*" | head -1)
        [ -n "$uploads_archive" ] && restore_uploads "$uploads_archive"
        
        # Restore config if present
        local config_file=$(find "$RESTORE_TEMP" -name ".env*" | head -1)
        [ -n "$config_file" ] && restore_config "$config_file"
    fi
    
    # Cleanup
    rm -rf "$RESTORE_TEMP"
}

# Main restoration flow
do_restore() {
    local backup_file="$1"
    local db_only="${2:-false}"
    local no_confirm="${3:-false}"
    local dry_run="${4:-false}"
    
    # Validate backup file
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    # Show what will happen
    echo ""
    log_warn "⚠️  THIS WILL OVERWRITE EXISTING DATA!"
    echo ""
    echo "Backup file: $backup_file"
    echo "Database:    Will be dropped and recreated"
    [ "$db_only" != "true" ] && echo "Uploads:     Will be overwritten if present in backup"
    [ "$db_only" != "true" ] && echo "Config:      Will be backed up and replaced"
    echo ""
    
    if [ "$dry_run" = "true" ]; then
        log_info "DRY RUN - No changes made"
        verify_backup "$backup_file"
        exit 0
    fi
    
    # Confirm unless --no-confirm
    if [ "$no_confirm" != "true" ]; then
        read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm
        if [ "$confirm" != "yes" ]; then
            log_info "Restore cancelled"
            exit 0
        fi
    fi
    
    # Verify backup first
    verify_backup "$backup_file"
    
    # Check containers
    check_containers
    
    # Stop application
    stop_application
    
    # Perform restore based on file type
    if [[ "$backup_file" == *.tar.gz ]] && [[ "$backup_file" != *db_*.tar.gz ]]; then
        restore_full "$backup_file" "$db_only"
    elif [[ "$backup_file" == *.sql.gz ]] || [[ "$backup_file" == *.sql ]]; then
        restore_database "$backup_file"
    else
        log_error "Unknown backup format"
        exit 1
    fi
    
    # Start application
    start_application
    
    echo ""
    log_success "╔════════════════════════════════════════════════════════════╗"
    log_success "║              RESTORE COMPLETED SUCCESSFULLY!                ║"
    log_success "╚════════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Next steps:"
    echo "  1. Verify application at http://localhost:3000"
    echo "  2. Check logs: docker compose logs -f"
    echo "  3. Run migrations if needed: docker exec $BACKEND_CONTAINER alembic upgrade head"
}

# Parse arguments
main() {
    print_banner
    
    local action="restore"
    local backup_file=""
    local db_only="false"
    local no_confirm="false"
    local dry_run="false"
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --list)
                list_backups
                exit 0
                ;;
            --verify)
                if [ -z "$2" ]; then
                    log_error "Missing backup file for --verify"
                    usage
                    exit 1
                fi
                verify_backup "$2"
                exit 0
                ;;
            --db-only)
                db_only="true"
                shift
                ;;
            --no-confirm)
                no_confirm="true"
                shift
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                backup_file="$1"
                shift
                ;;
        esac
    done
    
    if [ -z "$backup_file" ]; then
        log_error "Missing backup file argument"
        usage
        exit 1
    fi
    
    do_restore "$backup_file" "$db_only" "$no_confirm" "$dry_run"
}

main "$@"
