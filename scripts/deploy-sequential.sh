#!/bin/bash
# ============================================
# Sequential Build Script for Limited RAM Servers (1GB)
# ============================================
# ⚠️  CRITICAL: This script builds ONE container at a time
#     to prevent Out-Of-Memory crashes on 1GB RAM servers.
#
# 📝 NOTE: Scheduler containers (scheduler, scheduler-hourly,
#     scheduler-daily) share the backend image
#     (image: timetracker-backend:latest in docker-compose.prod.yml)
#     and therefore do NOT require separate build steps. The
#     `docker compose up -d` step below will detect the updated
#     backend image and recreate the scheduler containers
#     automatically so they always run the latest backend code.
#
# 📝 NOTE: Database migrations are applied AS PART OF this script,
#     after both images are built but BEFORE any long-running
#     container is started. The schedulers' on-startup sync loop
#     would otherwise race the un-migrated schema (see incident
#     2026-05-12 where a deferred `alembic upgrade head` caused
#     6024 "current transaction is aborted" errors in the first
#     scheduler-daily cron run).
#
# ❌ NEVER USE: docker compose up -d --build
# ❌ NEVER USE: docker compose build --no-cache
# ❌ NEVER USE: docker compose build (without specifying service)
# ============================================

set -e

cd /home/ubuntu/timetracker

echo "============================================"
echo "🚀 Sequential Build Deployment (RAM-Safe)"
echo "============================================"
echo "⚠️  Building ONE container at a time to prevent OOM"
echo ""

# Step 1: Stop running containers first to free RAM
echo "📦 Step 1/9: Stopping containers to free RAM..."
docker compose -f docker-compose.prod.yml down || true
echo "✅ Containers stopped"

# Step 2: Aggressive cleanup to maximize available RAM
echo ""
echo "🧹 Step 2/9: Freeing memory (aggressive cleanup)..."
docker system prune -f
docker builder prune -f -a
echo "✅ Memory freed"

# Step 3: Check available memory
echo ""
echo "📊 Step 3/9: Checking available memory..."
free -m
echo ""

# Step 4: Build BACKEND only (no --no-cache, no parallel builds!)
echo ""
echo "🔧 Step 4/9: Building BACKEND only..."
echo "   This may take 2-3 minutes..."
docker compose -f docker-compose.prod.yml build backend
echo "✅ Backend built!"

# Step 5: Clear build cache AGAIN before frontend
echo ""
echo "🧹 Step 5/9: Clearing build cache before frontend..."
docker builder prune -f
echo "✅ Cache cleared"

# Step 6: Build FRONTEND only (this is the heavy one)
echo ""
echo "🔧 Step 6/9: Building FRONTEND only..."
echo "   This may take 3-5 minutes..."
docker compose -f docker-compose.prod.yml build frontend
echo "✅ Frontend built!"

# Step 7: Apply DB migrations BEFORE long-running containers
echo ""
echo "🗄️  Step 7/9: Applying database migrations..."
echo "   This must precede container startup, or the scheduler"
echo "   containers' on-startup sync loop will race the un-migrated"
echo "   schema and produce cascading 'transaction aborted' errors."
# NOTE: 'postgres' here matches the service name defined in docker-compose.prod.yml.
# If that service is ever renamed, update both references below.
docker compose -f docker-compose.prod.yml up -d postgres
echo "   Waiting for DB to be ready..."
for i in {1..30}; do
  if docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ DB ready"
    break
  fi
  sleep 2
done
docker compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head
echo "✅ Migrations applied"

# Step 8: Start all services
echo ""
echo "🚀 Step 8/9: Starting all services..."
docker compose -f docker-compose.prod.yml up -d
echo "✅ Services started!"

# Step 9: Final cleanup and status
echo ""
echo "🧹 Step 9/9: Final cleanup..."
docker system prune -f

echo ""
echo "============================================"
echo "📊 Deployment Status:"
echo "============================================"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "🏥 Health Check:"
sleep 5
curl -s http://localhost:8080/health || echo "⚠️  Backend still starting..."

echo ""
echo "============================================"
echo "✅ Deployment complete!"
echo "🌐 https://timetracker.shaemarcus.com"
echo "============================================"
