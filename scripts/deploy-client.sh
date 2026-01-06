#!/bin/bash
# ============================================
# TIME TRACKER - CLIENT DEPLOYMENT SCRIPT
# ============================================
# This script deploys a new instance of Time Tracker for a client.
# Run this on the target server after initial setup.
#
# Usage:
#   ./deploy-client.sh --domain client.example.com --name "Client Company"
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - Git installed
#   - Server has at least 1GB RAM
#   - Ports 80/443 available
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INSTALL_DIR="/opt/timetracker"
REPO_URL="https://github.com/your-org/timetracker.git"
BRANCH="master"
DOMAIN=""
CLIENT_NAME=""
ADMIN_EMAIL=""
SKIP_SSL=false
DRY_RUN=false

# Function: Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           TIME TRACKER - CLIENT DEPLOYMENT                  ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Function: Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Required Options:"
    echo "  --domain DOMAIN         Client domain (e.g., time.client.com)"
    echo "  --name NAME             Client/company name"
    echo "  --admin-email EMAIL     Initial admin email"
    echo ""
    echo "Optional:"
    echo "  --install-dir PATH      Installation directory (default: /opt/timetracker)"
    echo "  --repo URL              Git repository URL"
    echo "  --branch BRANCH         Git branch (default: master)"
    echo "  --skip-ssl              Skip SSL certificate setup"
    echo "  --dry-run               Show what would be done without executing"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --domain time.acme.com --name \"Acme Corp\" --admin-email admin@acme.com"
}

# Function: Log messages
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function: Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=()
    
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi
    
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        missing+=("docker compose")
    fi
    
    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        echo ""
        echo "Install them with:"
        echo "  sudo apt update && sudo apt install -y docker.io docker-compose-v2 git"
        exit 1
    fi
    
    log_info "All prerequisites met ✓"
}

# Function: Generate secrets
generate_secrets() {
    log_info "Generating secure secrets..."
    
    SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n')
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d '\n' | tr -dc 'a-zA-Z0-9')
    API_KEY_ENCRYPTION=$(openssl rand -base64 32 | tr -d '\n')
    ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '\n' | tr -dc 'a-zA-Z0-9')
    
    log_info "Secrets generated ✓"
}

# Function: Create environment file
create_env_file() {
    log_info "Creating environment configuration..."
    
    cat > "$INSTALL_DIR/.env.production" << EOF
# ============================================
# TIME TRACKER - PRODUCTION CONFIGURATION
# Client: ${CLIENT_NAME}
# Domain: ${DOMAIN}
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# ============================================

# === Security (Auto-generated - DO NOT SHARE) ===
SECRET_KEY=${SECRET_KEY}
DB_PASSWORD=${DB_PASSWORD}
API_KEY_ENCRYPTION_KEY=${API_KEY_ENCRYPTION}

# === Database ===
DB_USER=timetracker
DB_NAME=time_tracker
DATABASE_URL=postgresql+asyncpg://timetracker:\${DB_PASSWORD}@postgres:5432/time_tracker

# === Redis ===
REDIS_URL=redis://redis:6379

# === Domain & CORS ===
ALLOWED_ORIGINS=["https://${DOMAIN}"]
ALLOWED_HOSTS=["${DOMAIN}","localhost","127.0.0.1","backend"]
VITE_API_URL=/api

# === Environment ===
ENVIRONMENT=production
DEBUG=false

# === Security Settings ===
BCRYPT_ROUNDS=12
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# === Rate Limiting ===
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE=5

# === Initial Admin Account ===
# ⚠️ CHANGE PASSWORD AFTER FIRST LOGIN!
FIRST_SUPER_ADMIN_EMAIL=${ADMIN_EMAIL}
FIRST_SUPER_ADMIN_PASSWORD=${ADMIN_PASSWORD}

# === Branding ===
VITE_APP_NAME=${CLIENT_NAME} Time Tracker
VITE_COMPANY_NAME=${CLIENT_NAME}
VITE_SUPPORT_EMAIL=support@${DOMAIN}
VITE_PRIMARY_COLOR=#2563eb

# === Optional: AI Features (Add your keys) ===
# GEMINI_API_KEY=
# OPENAI_API_KEY=

# === Optional: Email Notifications ===
# SMTP_SERVER=smtp.${DOMAIN}
# SMTP_PORT=587
# SMTP_USERNAME=
# SMTP_PASSWORD=
# SMTP_FROM_EMAIL=noreply@${DOMAIN}
EOF
    
    # Secure the file
    chmod 600 "$INSTALL_DIR/.env.production"
    
    log_info "Environment file created ✓"
}

# Function: Clone repository
clone_repository() {
    log_info "Cloning repository..."
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Directory exists, pulling latest..."
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout "$BRANCH"
        git pull origin "$BRANCH"
    else
        git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    
    log_info "Repository ready ✓"
}

# Function: Build and deploy (sequential to avoid OOM)
deploy_application() {
    log_info "Building and deploying application..."
    
    cd "$INSTALL_DIR"
    
    # Copy env file
    cp .env.production .env
    
    # Clean up first
    log_info "Cleaning up Docker resources..."
    docker system prune -f || true
    docker builder prune -f || true
    
    # Build backend first (lighter)
    log_info "Building backend..."
    docker compose -f docker-compose.prod.yml build --no-cache backend
    
    # Clean cache between builds
    docker builder prune -f || true
    
    # Build frontend (heavier)
    log_info "Building frontend..."
    docker compose -f docker-compose.prod.yml build --no-cache frontend
    
    # Start services
    log_info "Starting services..."
    docker compose -f docker-compose.prod.yml up -d
    
    # Final cleanup
    docker system prune -f || true
    
    log_info "Application deployed ✓"
}

# Function: Setup SSL with Caddy
setup_ssl() {
    if [ "$SKIP_SSL" = true ]; then
        log_warn "Skipping SSL setup (--skip-ssl flag)"
        return
    fi
    
    log_info "Setting up SSL certificate..."
    
    # Create Caddyfile
    cat > "$INSTALL_DIR/Caddyfile" << EOF
${DOMAIN} {
    reverse_proxy localhost:80
    encode gzip
    
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
EOF
    
    # Install Caddy if not present
    if ! command -v caddy &> /dev/null; then
        log_info "Installing Caddy..."
        sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
        sudo apt update
        sudo apt install -y caddy
    fi
    
    # Copy Caddyfile and reload
    sudo cp "$INSTALL_DIR/Caddyfile" /etc/caddy/Caddyfile
    sudo systemctl reload caddy
    
    log_info "SSL configured ✓"
}

# Function: Print deployment summary
print_summary() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              DEPLOYMENT COMPLETE! 🎉                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Access your Time Tracker instance:"
    echo -e "  ${BLUE}URL:${NC}      https://${DOMAIN}"
    echo ""
    echo "Initial Admin Credentials:"
    echo -e "  ${BLUE}Email:${NC}    ${ADMIN_EMAIL}"
    echo -e "  ${BLUE}Password:${NC} ${ADMIN_PASSWORD}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Change the admin password immediately after first login!${NC}"
    echo ""
    echo "Configuration file: $INSTALL_DIR/.env.production"
    echo ""
    echo "Useful commands:"
    echo "  View logs:     docker compose -f docker-compose.prod.yml logs -f"
    echo "  Restart:       docker compose -f docker-compose.prod.yml restart"
    echo "  Stop:          docker compose -f docker-compose.prod.yml down"
    echo "  Update:        cd $INSTALL_DIR && git pull && ./scripts/deploy-sequential.sh"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --name)
            CLIENT_NAME="$2"
            shift 2
            ;;
        --admin-email)
            ADMIN_EMAIL="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --repo)
            REPO_URL="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --skip-ssl)
            SKIP_SSL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
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

# Main execution
print_banner

# Validate required arguments
if [ -z "$DOMAIN" ] || [ -z "$CLIENT_NAME" ] || [ -z "$ADMIN_EMAIL" ]; then
    log_error "Missing required arguments!"
    echo ""
    usage
    exit 1
fi

log_info "Deploying Time Tracker for: $CLIENT_NAME"
log_info "Domain: $DOMAIN"
log_info "Install directory: $INSTALL_DIR"
echo ""

if [ "$DRY_RUN" = true ]; then
    log_warn "DRY RUN MODE - No changes will be made"
    echo ""
    echo "Would perform:"
    echo "  1. Check prerequisites"
    echo "  2. Clone repository to $INSTALL_DIR"
    echo "  3. Generate secure secrets"
    echo "  4. Create .env.production file"
    echo "  5. Build Docker containers (sequential)"
    echo "  6. Start services"
    echo "  7. Setup SSL with Caddy"
    exit 0
fi

# Run deployment steps
check_prerequisites
clone_repository
generate_secrets
create_env_file
deploy_application
setup_ssl
print_summary
