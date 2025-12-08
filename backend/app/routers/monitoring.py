"""
Health Check and Monitoring Endpoints
TASK-064: Add basic monitoring endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Dict, Any
import os
import sys
import platform
import psutil

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Basic health check endpoint.
    Returns overall system health status.
    """
    status = "healthy"
    checks = {}
    
    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy", "message": "Connected"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "message": str(e)}
        status = "unhealthy"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


@router.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint.
    Returns 200 if the service is running.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """
    Kubernetes readiness probe endpoint.
    Returns 200 if the service is ready to accept traffic.
    """
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {str(e)}")


@router.get("/metrics")
async def get_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get system metrics (admin only).
    Returns CPU, memory, disk usage, and application stats.
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    # Process metrics
    process = psutil.Process()
    process_memory = process.memory_info()
    
    # Database stats
    db_stats = {}
    try:
        result = await db.execute(text("""
            SELECT 
                (SELECT COUNT(*) FROM users) as user_count,
                (SELECT COUNT(*) FROM projects) as project_count,
                (SELECT COUNT(*) FROM time_entries) as entry_count,
                (SELECT COUNT(*) FROM teams) as team_count
        """))
        row = result.fetchone()
        if row:
            db_stats = {
                "users": row[0],
                "projects": row[1],
                "time_entries": row[2],
                "teams": row[3]
            }
    except Exception:
        db_stats = {"error": "Could not fetch stats"}
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent
            }
        },
        "process": {
            "pid": process.pid,
            "memory_mb": round(process_memory.rss / (1024**2), 2),
            "cpu_percent": process.cpu_percent()
        },
        "database": db_stats,
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@router.get("/info")
async def get_info() -> Dict[str, Any]:
    """
    Get application info.
    Returns version, environment, and other metadata.
    """
    return {
        "name": "Time Tracker API",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "python_version": platform.python_version(),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stats/activity")
async def get_activity_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get activity statistics for monitoring dashboards.
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)
    one_week_ago = now - timedelta(weeks=1)
    
    try:
        # Time entries in last hour
        result = await db.execute(text("""
            SELECT COUNT(*) FROM time_entries 
            WHERE created_at > :one_hour_ago
        """), {"one_hour_ago": one_hour_ago})
        entries_last_hour = result.scalar() or 0
        
        # Active users today
        result = await db.execute(text("""
            SELECT COUNT(DISTINCT user_id) FROM time_entries 
            WHERE created_at > :one_day_ago
        """), {"one_day_ago": one_day_ago})
        active_users_today = result.scalar() or 0
        
        # Total hours this week
        result = await db.execute(text("""
            SELECT COALESCE(SUM(duration_seconds), 0) / 3600.0 
            FROM time_entries 
            WHERE start_time > :one_week_ago
        """), {"one_week_ago": one_week_ago})
        hours_this_week = round(result.scalar() or 0, 2)
        
        # Running timers
        result = await db.execute(text("""
            SELECT COUNT(*) FROM time_entries WHERE is_running = true
        """))
        running_timers = result.scalar() or 0
        
        return {
            "timestamp": now.isoformat(),
            "entries_last_hour": entries_last_hour,
            "active_users_today": active_users_today,
            "hours_this_week": hours_this_week,
            "running_timers": running_timers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")
