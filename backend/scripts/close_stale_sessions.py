#!/usr/bin/env python3
"""
Daily auto-close script for stale work sessions.

This script should be run via cron job (e.g., at midnight) to:
1. Close any work sessions that have been running for more than MAX_SESSION_HOURS
2. Stop any orphaned time entries (running entries without active sessions)

Usage:
    # Run directly
    python scripts/close_stale_sessions.py
    
    # Or via Docker
    docker-compose exec backend python scripts/close_stale_sessions.py

Cron example (run at midnight daily):
    0 0 * * * cd /app && python scripts/close_stale_sessions.py >> /var/log/session_cleanup.log 2>&1
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configuration
MAX_SESSION_HOURS = 12  # Sessions running longer than this will be auto-closed
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker")

# Convert sync URL to async if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


async def close_stale_sessions():
    """Close all stale work sessions and orphaned time entries."""
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    now = datetime.now(timezone.utc)
    max_age = now - timedelta(hours=MAX_SESSION_HOURS)
    
    print(f"[{now.isoformat()}] Starting stale session cleanup...")
    print(f"  - Closing sessions older than {MAX_SESSION_HOURS} hours (started before {max_age.isoformat()})")
    
    async with async_session() as db:
        try:
            # Import models here to avoid circular imports
            from app.models import WorkSession, TimeEntry, SessionBreak, SessionMeeting
            
            # 1. Find all stale sessions (running for too long)
            stale_sessions_result = await db.execute(
                select(WorkSession)
                .where(
                    and_(
                        WorkSession.end_time.is_(None),
                        WorkSession.start_time < max_age
                    )
                )
            )
            stale_sessions = stale_sessions_result.scalars().all()
            
            sessions_closed = 0
            entries_closed = 0
            breaks_closed = 0
            meetings_closed = 0
            
            for session in stale_sessions:
                # Close all time entries for this session
                entries_result = await db.execute(
                    select(TimeEntry).where(
                        and_(
                            TimeEntry.work_session_id == session.id,
                            TimeEntry.end_time.is_(None)
                        )
                    )
                )
                entries = entries_result.scalars().all()
                
                for entry in entries:
                    entry.end_time = now
                    entry.is_running = False
                    entry.is_paused = False
                    if entry.start_time:
                        total_elapsed = int((now - entry.start_time).total_seconds())
                        entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)
                    entries_closed += 1
                
                # Close all breaks for this session
                breaks_result = await db.execute(
                    select(SessionBreak).where(
                        and_(
                            SessionBreak.work_session_id == session.id,
                            SessionBreak.end_time.is_(None)
                        )
                    )
                )
                breaks = breaks_result.scalars().all()
                
                for brk in breaks:
                    brk.end_time = now
                    brk.duration_seconds = int((now - brk.start_time).total_seconds())
                    session.total_break_seconds += brk.duration_seconds
                    breaks_closed += 1
                
                # Close all meetings for this session
                meetings_result = await db.execute(
                    select(SessionMeeting).where(
                        and_(
                            SessionMeeting.work_session_id == session.id,
                            SessionMeeting.end_time.is_(None)
                        )
                    )
                )
                meetings = meetings_result.scalars().all()
                
                for mtg in meetings:
                    mtg.end_time = now
                    mtg.duration_seconds = int((now - mtg.start_time).total_seconds())
                    session.total_meeting_seconds += mtg.duration_seconds
                    meetings_closed += 1
                
                # Close the session
                session.end_time = now
                session.status = "auto_closed"
                session.total_work_seconds = sum(
                    (e.duration_seconds or 0) for e in entries
                )
                sessions_closed += 1
            
            # 2. Find and close orphaned time entries (no session or session already closed)
            orphan_result = await db.execute(
                select(TimeEntry).where(
                    and_(
                        TimeEntry.end_time.is_(None),
                        TimeEntry.start_time < max_age
                    )
                )
            )
            orphan_entries = orphan_result.scalars().all()
            
            orphans_closed = 0
            for entry in orphan_entries:
                entry.end_time = now
                entry.is_running = False
                entry.is_paused = False
                if entry.start_time:
                    total_elapsed = int((now - entry.start_time).total_seconds())
                    entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)
                orphans_closed += 1
            
            await db.commit()
            
            print(f"  ✓ Closed {sessions_closed} stale sessions")
            print(f"  ✓ Closed {entries_closed} time entries (linked to sessions)")
            print(f"  ✓ Closed {breaks_closed} open breaks")
            print(f"  ✓ Closed {meetings_closed} open meetings")
            print(f"  ✓ Closed {orphans_closed} orphaned time entries")
            print(f"[{datetime.now(timezone.utc).isoformat()}] Cleanup complete!")
            
            return {
                "sessions_closed": sessions_closed,
                "entries_closed": entries_closed + orphans_closed,
                "breaks_closed": breaks_closed,
                "meetings_closed": meetings_closed,
            }
            
        except Exception as e:
            print(f"  ✗ Error during cleanup: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    result = asyncio.run(close_stale_sessions())
    print(f"\nSummary: {result}")
