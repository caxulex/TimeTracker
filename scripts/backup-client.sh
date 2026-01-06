#!/bin/bash
# ============================================
# TIME TRACKER - CLIENT BACKUP SCRIPT
# ============================================
# Complete backup solution for client deployments.
# Backs up database, uploads, and configuration.
#
# Usage:
#   ./backup-client.sh                    # Full backup
#   ./backup-client.sh --db-only          # Database only
#   ./backup-client.sh --restore FILE     # Restore from backup
#   ./backup-client.sh --list             # List available backups
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration (override via environment or .env file)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Docker container names
DB_CONTAINER="${DB_CONTAINER:-timetracker-postgres-1}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           TIME TRACKER - CLIENT BACKUP                      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --db-only          Backup database only"
    echo "  --full             Full backup (database + uploads + config)"
    echo "  --restore FILE     Restore from backup file"
    echo "  --list             List available backups"
    echo "  --clean            Remove backups older than RETENTION_DAYS"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR         Backup directory (default: ./backups)"
    echo "  RETENTION_DAYS     Days to keep backups (default: 30)"
    echo "  DB_CONTAINER       PostgreSQL container name"
    echo ""
    echo "Examples:"
    echo "  $0                           # Full backup"
    echo "  $0 --db-only                 # Database only"
    echo "  $0 --restore backups/db_20260106.sql.gz"
    echo "  $0 --list"
}

# Create backup directory
init_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
}

# Backup database
backup_database() {
    log_step "Backing up database..."
    
    local backup_file="$BACKUP_DIR/db_${TIMESTAMP}.sql.gz"
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "$DB_CONTAINER"; then
        # Try to find the container
        DB_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres|db' | head -1)
        if [ -z "$DB_CONTAINER" ]; then
            log_error "PostgreSQL container not found!"
            log_info "Available containers:"
            docker ps --format '  {{.Names}}'
            return 1
        fi
        log_warn "Using container: $DB_CONTAINER"
    fi
    
    # Get database credentials from container environment
    DB_USER=$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER 2>/dev/null || echo "postgres")
    DB_NAME=$(docker exec "$DB_CONTAINER" printenv POSTGRES_DB 2>/dev/null || echo "time_tracker")
    
    log_info "Database: $DB_NAME"
    log_info "Container: $DB_CONTAINER"
    
    # Perform backup
    if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-privileges | gzip > "$backup_file"; then
        
        local size=$(du -h "$backup_file" | cut -f1)
        log_info "Database backup completed: $backup_file ($size)"
        echo "$backup_file"
    else
        log_error "Database backup failed!"
        rm -f "$backup_file"
        return 1
    fi
}

# Backup uploads directory
backup_uploads() {
    log_step "Backing up uploads..."
    
    local backup_file="$BACKUP_DIR/uploads_${TIMESTAMP}.tar.gz"
    local uploads_dir="./uploads"
    
    if [ -d "$uploads_dir" ] && [ "$(ls -A $uploads_dir 2>/dev/null)" ]; then
        tar -czf "$backup_file" -C "$(dirname $uploads_dir)" "$(basename $uploads_dir)"
        local size=$(du -h "$backup_file" | cut -f1)
        log_info "Uploads backup completed: $backup_file ($size)"
        echo "$backup_file"
    else
        log_warn "No uploads directory found or empty, skipping"
    fi
}

# Backup configuration
backup_config() {
    log_step "Backing up configuration..."
    
    local backup_file="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
    local config_files=()
    
    # Find config files to backup
    [ -f ".env" ] && config_files+=(".env")
    [ -f ".env.production" ] && config_files+=(".env.production")
    [ -f "docker-compose.prod.yml" ] && config_files+=("docker-compose.prod.yml")
    [ -f "Caddyfile" ] && config_files+=("Caddyfile")
    
    if [ ${#config_files[@]} -gt 0 ]; then
        tar -czf "$backup_file" "${config_files[@]}" 2>/dev/null || true
        local size=$(du -h "$backup_file" | cut -f1)
        log_info "Config backup completed: $backup_file ($size)"
        echo "$backup_file"
    else
        log_warn "No configuration files found, skipping"
    fi
}

# Full backup
full_backup() {
    print_banner
    log_info "Starting full backup..."
    log_info "Backup directory: $BACKUP_DIR"
    log_info "Timestamp: $TIMESTAMP"
    echo ""
    
    init_backup_dir
    
    local db_file=$(backup_database)
    local uploads_file=$(backup_uploads)
    local config_file=$(backup_config)
    
    # Create manifest
    local manifest_file="$BACKUP_DIR/manifest_${TIMESTAMP}.txt"
    cat > "$manifest_file" << EOF
# Time Tracker Backup Manifest
# Created: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Timestamp: $TIMESTAMP

DATABASE=$db_file
UPLOADS=$uploads_file
CONFIG=$config_file
EOF
    
    echo ""
    log_info "═══════════════════════════════════════════"
    log_info "       BACKUP COMPLETED SUCCESSFULLY!"
    log_info "═══════════════════════════════════════════"
    echo ""
    log_info "Backup files:"
    [ -n "$db_file" ] && log_info "  Database: $db_file"
    [ -n "$uploads_file" ] && log_info "  Uploads:  $uploads_file"
    [ -n "$config_file" ] && log_info "  Config:   $config_file"
    log_info "  Manifest: $manifest_file"
    echo ""
}

# Database only backup
db_only_backup() {
    print_banner
    log_info "Starting database-only backup..."
    init_backup_dir
    backup_database
}

# Restore from backup
restore_backup() {
    local backup_file="$1"
    
    print_banner
    log_warn "⚠️  RESTORE OPERATION - THIS WILL OVERWRITE EXISTING DATA!"
    echo ""
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    # Determine backup type
    if [[ "$backup_file" == *"db_"* ]]; then
        log_info "Restoring database from: $backup_file"
        
        read -p "Are you sure you want to restore? This will overwrite the database! (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log_warn "Restore cancelled"
            exit 0
        fi
        
        # Find container
        if ! docker ps --format '{{.Names}}' | grep -q "$DB_CONTAINER"; then
            DB_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres|db' | head -1)
        fi
        
        DB_USER=$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER 2>/dev/null || echo "postgres")
        DB_NAME=$(docker exec "$DB_CONTAINER" printenv POSTGRES_DB 2>/dev/null || echo "time_tracker")
        
        log_info "Restoring to database: $DB_NAME"
        
        # Restore
        if gunzip -c "$backup_file" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"; then
            log_info "Database restored successfully!"
        else
            log_error "Database restore failed!"
            exit 1
        fi
        
    elif [[ "$backup_file" == *"uploads_"* ]]; then
        log_info "Restoring uploads from: $backup_file"
        tar -xzf "$backup_file" -C .
        log_info "Uploads restored successfully!"
        
    elif [[ "$backup_file" == *"config_"* ]]; then
        log_warn "Config restore requires manual review. Contents:"
        tar -tzf "$backup_file"
        log_info "Extract manually with: tar -xzf $backup_file"
        
    else
        log_error "Unknown backup type"
        exit 1
    fi
}

# List available backups
list_backups() {
    print_banner
    log_info "Available backups in: $BACKUP_DIR"
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_warn "Backup directory does not exist"
        exit 0
    fi
    
    echo "Database Backups:"
    ls -lh "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null || echo "  (none)"
    echo ""
    
    echo "Upload Backups:"
    ls -lh "$BACKUP_DIR"/uploads_*.tar.gz 2>/dev/null || echo "  (none)"
    echo ""
    
    echo "Config Backups:"
    ls -lh "$BACKUP_DIR"/config_*.tar.gz 2>/dev/null || echo "  (none)"
    echo ""
    
    # Show total size
    if [ "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        local total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
        log_info "Total backup size: $total_size"
    fi
}

# Clean old backups
clean_backups() {
    print_banner
    log_info "Cleaning backups older than $RETENTION_DAYS days..."
    
    local count_before=$(ls -1 "$BACKUP_DIR"/*.{sql.gz,tar.gz} 2>/dev/null | wc -l || echo 0)
    
    find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "manifest_*.txt" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    local count_after=$(ls -1 "$BACKUP_DIR"/*.{sql.gz,tar.gz} 2>/dev/null | wc -l || echo 0)
    local removed=$((count_before - count_after))
    
    log_info "Removed $removed old backup files"
    log_info "Remaining backups: $count_after"
}

# Parse command line arguments
MODE="full"
RESTORE_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --db-only)
            MODE="db-only"
            shift
            ;;
        --full)
            MODE="full"
            shift
            ;;
        --restore)
            MODE="restore"
            RESTORE_FILE="$2"
            shift 2
            ;;
        --list)
            MODE="list"
            shift
            ;;
        --clean)
            MODE="clean"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Execute based on mode
case $MODE in
    full)
        full_backup
        ;;
    db-only)
        db_only_backup
        ;;
    restore)
        restore_backup "$RESTORE_FILE"
        ;;
    list)
        list_backups
        ;;
    clean)
        clean_backups
        ;;
esac
