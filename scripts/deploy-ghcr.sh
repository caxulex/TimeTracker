#!/bin/bash
# ============================================
# Deploy Pre-Built Images from GitHub Container Registry
# NO LOCAL BUILD - Just pull and restart
# ============================================

set -e

echo "🚀 TimeTracker Deployment (Pre-built Images)"
echo "============================================="

# Navigate to app directory
cd /home/ubuntu/timetracker

# Ensure we're using the GHCR compose file
COMPOSE_FILE="docker-compose.prod.ghcr.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ $COMPOSE_FILE not found!"
    echo "   Make sure to copy it from the repo first."
    exit 1
fi

# Login to GitHub Container Registry (if not already logged in)
echo ""
echo "📦 Logging into GitHub Container Registry..."
# Note: You need to set GITHUB_TOKEN environment variable or use gh CLI
if [ -n "$GITHUB_TOKEN" ]; then
    echo "$GITHUB_TOKEN" | docker login ghcr.io -u caxulex --password-stdin
else
    echo "   (Assuming already logged in or using gh auth)"
fi

# Pull latest images
echo ""
echo "⬇️  Pulling latest images from GHCR..."
docker compose -f "$COMPOSE_FILE" pull

# Stop and remove old containers (keep volumes!)
echo ""
echo "🔄 Stopping old containers..."
docker compose -f "$COMPOSE_FILE" down --remove-orphans

# Start new containers
echo ""
echo "🚀 Starting containers with new images..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "🔍 Checking service health..."
docker compose -f "$COMPOSE_FILE" ps

# Show backend logs briefly
echo ""
echo "📋 Recent backend logs:"
docker logs timetracker-backend --tail 20

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Application should be available at: https://timetracker.shaemarcus.com"
echo ""
