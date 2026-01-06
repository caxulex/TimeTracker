#!/bin/bash
# ============================================
# Sequential Build Script for Limited RAM Servers
# Builds frontend and backend ONE AT A TIME to avoid OOM
# ============================================

set -e

cd /home/ubuntu/timetracker

echo "🚀 Sequential Build Deployment"
echo "==============================="
echo ""

# Step 1: Pull latest code
echo "📥 Pulling latest code..."
git pull origin master

# Step 2: Free up memory first
echo ""
echo "🧹 Cleaning up to free memory..."
docker system prune -f
docker builder prune -f

# Step 3: Build BACKEND first (lighter build)
echo ""
echo "🔧 Building BACKEND..."
docker compose -f docker-compose.prod.yml build backend
echo "✅ Backend built!"

# Step 4: Clear build cache before frontend
echo ""
echo "🧹 Clearing build cache..."
docker builder prune -f

# Step 5: Build FRONTEND (heavier build - needs the RAM we just freed)
echo ""
echo "🔧 Building FRONTEND (this takes a while)..."
docker compose -f docker-compose.prod.yml build frontend
echo "✅ Frontend built!"

# Step 6: Restart services
echo ""
echo "🔄 Restarting services..."
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# Step 7: Final cleanup
echo ""
echo "🧹 Final cleanup..."
docker system prune -f

# Step 8: Check status
echo ""
echo "📊 Service Status:"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "✅ Deployment complete!"
echo "🌐 https://timetracker.shaemarcus.com"
