#!/bin/bash
# ============================================
# TIME TRACKER - SECRETS GENERATOR
# ============================================
# Generates secure random secrets for Time Tracker deployment.
# Can be used standalone or called by deploy-client.sh.
#
# Usage:
#   ./generate-secrets.sh                    # Print to stdout
#   ./generate-secrets.sh --env              # Print as .env format
#   ./generate-secrets.sh --output .env      # Write to file
#   ./generate-secrets.sh --json             # Print as JSON
# ============================================

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Options
OUTPUT_FORMAT="plain"
OUTPUT_FILE=""

# Function: Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --env           Output as .env format"
    echo "  --json          Output as JSON format"
    echo "  --output FILE   Write to file instead of stdout"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Print secrets in plain format"
    echo "  $0 --env                    # Print as environment variables"
    echo "  $0 --env --output .env      # Write to .env file"
    echo "  $0 --json                   # Print as JSON"
}

# Function: Generate a secure random string
generate_secret() {
    local length=${1:-64}
    openssl rand -base64 "$length" | tr -d '\n'
}

# Function: Generate alphanumeric string (safe for passwords)
generate_password() {
    local length=${1:-24}
    openssl rand -base64 "$length" | tr -d '\n' | tr -dc 'a-zA-Z0-9' | head -c "$length"
}

# Function: Generate URL-safe string
generate_urlsafe() {
    local length=${1:-64}
    openssl rand -base64 "$length" | tr -d '\n' | tr '+/' '-_' | tr -d '='
}

# Generate all secrets
SECRET_KEY=$(generate_urlsafe 64)
API_KEY_ENCRYPTION_KEY=$(generate_urlsafe 32)
DB_PASSWORD=$(generate_password 32)
REDIS_PASSWORD=$(generate_password 32)
ADMIN_PASSWORD=$(generate_password 16)
SESSION_SECRET=$(generate_urlsafe 32)
WEBHOOK_SECRET=$(generate_urlsafe 32)

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            OUTPUT_FORMAT="env"
            shift
            ;;
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --output)
            OUTPUT_FILE="$2"
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

# Function: Output in plain format
output_plain() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}           TIME TRACKER - GENERATED SECRETS${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Store these secrets securely! They cannot be recovered.${NC}"
    echo ""
    echo "SECRET_KEY (JWT signing):"
    echo "  $SECRET_KEY"
    echo ""
    echo "API_KEY_ENCRYPTION_KEY (AES-256 encryption):"
    echo "  $API_KEY_ENCRYPTION_KEY"
    echo ""
    echo "DB_PASSWORD (PostgreSQL):"
    echo "  $DB_PASSWORD"
    echo ""
    echo "REDIS_PASSWORD (optional, for secured Redis):"
    echo "  $REDIS_PASSWORD"
    echo ""
    echo "ADMIN_PASSWORD (initial admin account):"
    echo "  $ADMIN_PASSWORD"
    echo ""
    echo "SESSION_SECRET (session encryption):"
    echo "  $SESSION_SECRET"
    echo ""
    echo "WEBHOOK_SECRET (webhook signatures):"
    echo "  $WEBHOOK_SECRET"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
}

# Function: Output in .env format
output_env() {
    cat << EOF
# ============================================
# TIME TRACKER - GENERATED SECRETS
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# ⚠️ Store securely! Do not commit to version control!
# ============================================

# JWT Signing Key (required)
SECRET_KEY=${SECRET_KEY}

# AES-256 Encryption Key for API keys (required)
API_KEY_ENCRYPTION_KEY=${API_KEY_ENCRYPTION_KEY}

# Database Password (required)
DB_PASSWORD=${DB_PASSWORD}

# Redis Password (optional - for secured Redis instances)
# REDIS_PASSWORD=${REDIS_PASSWORD}

# Initial Admin Password (change after first login!)
FIRST_SUPER_ADMIN_PASSWORD=${ADMIN_PASSWORD}

# Session Secret (for cookie signing)
# SESSION_SECRET=${SESSION_SECRET}

# Webhook Signature Secret (for outgoing webhooks)
# WEBHOOK_SECRET=${WEBHOOK_SECRET}
EOF
}

# Function: Output in JSON format
output_json() {
    cat << EOF
{
  "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "secrets": {
    "SECRET_KEY": "${SECRET_KEY}",
    "API_KEY_ENCRYPTION_KEY": "${API_KEY_ENCRYPTION_KEY}",
    "DB_PASSWORD": "${DB_PASSWORD}",
    "REDIS_PASSWORD": "${REDIS_PASSWORD}",
    "FIRST_SUPER_ADMIN_PASSWORD": "${ADMIN_PASSWORD}",
    "SESSION_SECRET": "${SESSION_SECRET}",
    "WEBHOOK_SECRET": "${WEBHOOK_SECRET}"
  }
}
EOF
}

# Output based on format
output() {
    case $OUTPUT_FORMAT in
        plain)
            output_plain
            ;;
        env)
            output_env
            ;;
        json)
            output_json
            ;;
    esac
}

# Write to file or stdout
if [ -n "$OUTPUT_FILE" ]; then
    output > "$OUTPUT_FILE"
    chmod 600 "$OUTPUT_FILE"
    echo -e "${GREEN}Secrets written to: $OUTPUT_FILE${NC}"
    echo -e "${YELLOW}File permissions set to 600 (owner read/write only)${NC}"
else
    output
fi
