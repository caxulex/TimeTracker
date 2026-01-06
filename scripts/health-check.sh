#!/bin/bash
# ============================================
# TIME TRACKER - HEALTH CHECK SCRIPT
# ============================================
# Comprehensive health monitoring for TimeTracker deployments.
# Can be used standalone or integrated with cron/monitoring systems.
#
# Usage:
#   ./health-check.sh              # Full health check
#   ./health-check.sh --quick      # Quick check (API only)
#   ./health-check.sh --json       # JSON output for monitoring
#   ./health-check.sh --watch      # Continuous monitoring
# ============================================

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8080}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
TIMEOUT="${TIMEOUT:-10}"

# Docker container names
DB_CONTAINER="${DB_CONTAINER:-timetracker-db}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-timetracker-backend}"
FRONTEND_CONTAINER="${FRONTEND_CONTAINER:-timetracker-frontend}"
REDIS_CONTAINER="${REDIS_CONTAINER:-timetracker-redis}"

# Thresholds
DISK_WARN_PERCENT=80
DISK_CRIT_PERCENT=90
MEM_WARN_PERCENT=80
MEM_CRIT_PERCENT=90
CPU_WARN_PERCENT=80

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Status tracking
OVERALL_STATUS="healthy"
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNED=0

# Logging functions
log_ok() { 
    echo -e "  ${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}
log_warn() { 
    echo -e "  ${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNED++))
    [ "$OVERALL_STATUS" = "healthy" ] && OVERALL_STATUS="degraded"
}
log_fail() { 
    echo -e "  ${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
    OVERALL_STATUS="unhealthy"
}
log_info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
log_section() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           TIME TRACKER - HEALTH CHECK                       ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
}

# Check API health endpoint
check_api_health() {
    log_section "API Health"
    
    local response
    local http_code
    
    # Make request and capture response + code
    response=$(curl -sf --max-time "$TIMEOUT" "$API_URL/health" 2>/dev/null) || true
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$API_URL/health" 2>/dev/null) || http_code="000"
    
    if [ "$http_code" = "200" ]; then
        log_ok "API endpoint: HTTP $http_code"
        
        # Parse JSON response if jq available
        if command -v jq &> /dev/null && [ -n "$response" ]; then
            local status=$(echo "$response" | jq -r '.status // "unknown"')
            local db_status=$(echo "$response" | jq -r '.checks.database // "unknown"')
            local redis_status=$(echo "$response" | jq -r '.checks.redis // "unknown"')
            
            [ "$status" = "healthy" ] && log_ok "Overall status: $status" || log_fail "Overall status: $status"
            [ "$db_status" = "healthy" ] && log_ok "Database: $db_status" || log_fail "Database: $db_status"
            [ "$redis_status" = "healthy" ] && log_ok "Redis: $redis_status" || log_fail "Redis: $redis_status"
        fi
    else
        log_fail "API endpoint: HTTP $http_code (expected 200)"
    fi
}

# Check frontend
check_frontend() {
    log_section "Frontend"
    
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$FRONTEND_URL" 2>/dev/null) || http_code="000"
    
    if [ "$http_code" = "200" ]; then
        log_ok "Frontend: HTTP $http_code"
    else
        log_fail "Frontend: HTTP $http_code (expected 200)"
    fi
}

# Check Docker containers
check_containers() {
    log_section "Docker Containers"
    
    local containers=("$BACKEND_CONTAINER" "$FRONTEND_CONTAINER" "$DB_CONTAINER" "$REDIS_CONTAINER")
    
    for container in "${containers[@]}"; do
        local status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "not found")
        local health=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
        
        if [ "$status" = "running" ]; then
            if [ "$health" = "healthy" ] || [ "$health" = "none" ]; then
                log_ok "$container: $status"
            else
                log_warn "$container: $status (health: $health)"
            fi
        else
            log_fail "$container: $status"
        fi
    done
}

# Check container resource usage
check_container_resources() {
    log_section "Container Resources"
    
    # Get stats for all timetracker containers
    local stats=$(docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemPerc}},{{.MemUsage}}" 2>/dev/null | grep -E "timetracker" || true)
    
    if [ -z "$stats" ]; then
        log_warn "No container stats available"
        return
    fi
    
    echo "$stats" | while IFS=',' read -r name cpu mem mem_usage; do
        # Remove % sign for comparison
        cpu_num=${cpu%\%}
        mem_num=${mem%\%}
        
        # Format output
        local status_icon="${GREEN}✓${NC}"
        local note=""
        
        # Check CPU threshold
        if (( $(echo "$cpu_num > $CPU_WARN_PERCENT" | bc -l 2>/dev/null || echo 0) )); then
            status_icon="${YELLOW}⚠${NC}"
            note=" (high CPU)"
            ((CHECKS_WARNED++))
        fi
        
        # Check memory threshold
        if (( $(echo "$mem_num > $MEM_CRIT_PERCENT" | bc -l 2>/dev/null || echo 0) )); then
            status_icon="${RED}✗${NC}"
            note=" (critical memory!)"
            ((CHECKS_FAILED++))
            OVERALL_STATUS="unhealthy"
        elif (( $(echo "$mem_num > $MEM_WARN_PERCENT" | bc -l 2>/dev/null || echo 0) )); then
            status_icon="${YELLOW}⚠${NC}"
            note=" (high memory)"
            ((CHECKS_WARNED++))
        fi
        
        echo -e "  $status_icon $name: CPU $cpu, Mem $mem ($mem_usage)$note"
    done
}

# Check disk space
check_disk_space() {
    log_section "Disk Space"
    
    local usage=$(df -h . 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
    local available=$(df -h . 2>/dev/null | tail -1 | awk '{print $4}')
    
    if [ -n "$usage" ]; then
        if [ "$usage" -gt "$DISK_CRIT_PERCENT" ]; then
            log_fail "Disk usage: ${usage}% (critical! $available free)"
        elif [ "$usage" -gt "$DISK_WARN_PERCENT" ]; then
            log_warn "Disk usage: ${usage}% ($available free)"
        else
            log_ok "Disk usage: ${usage}% ($available free)"
        fi
    else
        log_warn "Could not determine disk usage"
    fi
    
    # Check Docker disk usage
    local docker_usage=$(docker system df 2>/dev/null | grep -E "^(Images|Containers|Volumes)" || true)
    if [ -n "$docker_usage" ]; then
        log_info "Docker disk usage:"
        echo "$docker_usage" | while read -r line; do
            echo "      $line"
        done
    fi
}

# Check database connectivity and stats
check_database() {
    log_section "Database"
    
    # Check if we can connect and get basic stats
    local db_size=$(docker exec "$DB_CONTAINER" psql -U postgres -d time_tracker -t -c "SELECT pg_size_pretty(pg_database_size('time_tracker'));" 2>/dev/null | tr -d ' ' || echo "unknown")
    local active_connections=$(docker exec "$DB_CONTAINER" psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='time_tracker';" 2>/dev/null | tr -d ' ' || echo "unknown")
    
    if [ "$db_size" != "unknown" ]; then
        log_ok "Database size: $db_size"
        log_ok "Active connections: $active_connections"
    else
        log_fail "Cannot connect to database"
    fi
}

# Check Redis
check_redis() {
    log_section "Redis"
    
    local redis_ping=$(docker exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null || echo "FAIL")
    local redis_memory=$(docker exec "$REDIS_CONTAINER" redis-cli info memory 2>/dev/null | grep "used_memory_human" | cut -d: -f2 | tr -d '\r' || echo "unknown")
    
    if [ "$redis_ping" = "PONG" ]; then
        log_ok "Redis: responding"
        log_ok "Memory usage: $redis_memory"
    else
        log_fail "Redis: not responding"
    fi
}

# Check recent errors in logs
check_logs() {
    log_section "Recent Logs"
    
    # Check backend logs for errors in last 100 lines
    local backend_errors=$(docker logs "$BACKEND_CONTAINER" --tail 100 2>&1 | grep -ci "error\|exception\|critical" || echo 0)
    local frontend_errors=$(docker logs "$FRONTEND_CONTAINER" --tail 100 2>&1 | grep -ci "error\|exception\|500" || echo 0)
    
    if [ "$backend_errors" -gt 10 ]; then
        log_warn "Backend: $backend_errors errors in recent logs"
    elif [ "$backend_errors" -gt 0 ]; then
        log_info "Backend: $backend_errors errors in recent logs"
    else
        log_ok "Backend: no recent errors"
    fi
    
    if [ "$frontend_errors" -gt 10 ]; then
        log_warn "Frontend: $frontend_errors errors in recent logs"
    elif [ "$frontend_errors" -gt 0 ]; then
        log_info "Frontend: $frontend_errors errors in recent logs"
    else
        log_ok "Frontend: no recent errors"
    fi
}

# Check SSL certificate (if applicable)
check_ssl() {
    local domain="${1:-}"
    
    if [ -z "$domain" ]; then
        return
    fi
    
    log_section "SSL Certificate"
    
    local expiry=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || echo "")
    
    if [ -n "$expiry" ]; then
        local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo 0)
        local now_epoch=$(date +%s)
        local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
        
        if [ "$days_left" -lt 7 ]; then
            log_fail "SSL expires in $days_left days ($expiry)"
        elif [ "$days_left" -lt 30 ]; then
            log_warn "SSL expires in $days_left days ($expiry)"
        else
            log_ok "SSL valid for $days_left days"
        fi
    else
        log_info "Could not check SSL certificate"
    fi
}

# Generate JSON output
output_json() {
    cat << EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$OVERALL_STATUS",
  "checks": {
    "passed": $CHECKS_PASSED,
    "warned": $CHECKS_WARNED,
    "failed": $CHECKS_FAILED
  },
  "api_url": "$API_URL",
  "frontend_url": "$FRONTEND_URL"
}
EOF
}

# Print summary
print_summary() {
    echo ""
    echo "════════════════════════════════════════════════════════════"
    
    local status_color
    case "$OVERALL_STATUS" in
        healthy) status_color="${GREEN}" ;;
        degraded) status_color="${YELLOW}" ;;
        unhealthy) status_color="${RED}" ;;
    esac
    
    echo -e "Overall Status: ${status_color}${OVERALL_STATUS^^}${NC}"
    echo -e "Checks Passed:  ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "Checks Warned:  ${YELLOW}$CHECKS_WARNED${NC}"
    echo -e "Checks Failed:  ${RED}$CHECKS_FAILED${NC}"
    echo "════════════════════════════════════════════════════════════"
    
    # Return appropriate exit code
    case "$OVERALL_STATUS" in
        healthy) return 0 ;;
        degraded) return 1 ;;
        unhealthy) return 2 ;;
    esac
}

# Quick check (API only)
quick_check() {
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_URL/health" 2>/dev/null) || http_code="000"
    
    if [ "$http_code" = "200" ]; then
        echo "OK"
        exit 0
    else
        echo "FAIL (HTTP $http_code)"
        exit 2
    fi
}

# Watch mode (continuous monitoring)
watch_mode() {
    local interval="${1:-30}"
    
    echo "Monitoring every ${interval}s (Ctrl+C to stop)"
    echo ""
    
    while true; do
        clear
        main_check
        echo ""
        echo "Next check in ${interval}s..."
        sleep "$interval"
    done
}

# Main check routine
main_check() {
    check_api_health
    check_frontend
    check_containers
    check_container_resources
    check_disk_space
    check_database
    check_redis
    check_logs
    
    print_summary
}

# Usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --quick          Quick check (API health only)"
    echo "  --json           Output in JSON format"
    echo "  --watch [SEC]    Continuous monitoring (default: 30s)"
    echo "  --ssl DOMAIN     Also check SSL certificate"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  API_URL          Backend API URL (default: http://localhost:8080)"
    echo "  FRONTEND_URL     Frontend URL (default: http://localhost:3000)"
    echo "  TIMEOUT          Request timeout in seconds (default: 10)"
    echo ""
    echo "Exit Codes:"
    echo "  0 - Healthy"
    echo "  1 - Degraded (warnings present)"
    echo "  2 - Unhealthy (failures present)"
}

# Main
main() {
    local json_output=false
    local ssl_domain=""
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --quick)
                quick_check
                ;;
            --json)
                json_output=true
                shift
                ;;
            --watch)
                local interval="${2:-30}"
                shift 2 2>/dev/null || shift
                watch_mode "$interval"
                ;;
            --ssl)
                ssl_domain="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    if [ "$json_output" = true ]; then
        # Suppress normal output for JSON
        check_api_health > /dev/null 2>&1 || true
        check_containers > /dev/null 2>&1 || true
        output_json
    else
        print_banner
        main_check
        [ -n "$ssl_domain" ] && check_ssl "$ssl_domain"
    fi
}

main "$@"
