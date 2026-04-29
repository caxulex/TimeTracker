"""
Time Tracker API - WebSocket Router for Real-time Features

WebSocket lifecycle (per connection):
  1. Connect: client opens ``/api/ws/ws?token=...``.
  2. Auth: token validated via ``get_current_user_ws`` (fail-closed on Redis down).
  3. Load team_ids: query ``TeamMember`` for the user once; cached on the
     manager for the life of this connection (stale across team changes).
  4. Tenant-scoped warm of ``manager.active_timers`` for the user's company
     (does NOT overwrite entries belonging to other tenants).
  5. Subscribe: register the socket in the connection manager.
  6. Loop: receive_json with timeout; on timeout send ping. Targeted
     exception handling — ``CancelledError`` is re-raised, disconnects break.
  7. Disconnect: cleanup connection + team membership entries.
"""

import asyncio
import logging
from typing import Dict, Optional, Set

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

try:  # websockets is a transitive dep of starlette/uvicorn
    from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
except ImportError:  # pragma: no cover - safety net only
    class ConnectionClosedError(Exception):  # type: ignore[no-redef]
        pass

    class ConnectionClosedOK(Exception):  # type: ignore[no-redef]
        pass

from app.dependencies import (
    FILTER_NULL_COMPANY,
    BlacklistUnavailableError,
    get_company_filter,
    get_current_user,
    get_current_user_ws,
)
from app.models import User
from app.utils.timewindow import now_utc

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # team_id -> set of user_ids
        self.team_members: Dict[int, Set[int]] = {}
        # user_id -> current timer info
        self.active_timers: Dict[int, dict] = {}
        # user_id -> company_id (for multi-tenant filtering)
        self.user_companies: Dict[int, Optional[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, team_ids: list[int] = None, company_id: int = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

        # Track user's company for multi-tenant broadcasts
        self.user_companies[user_id] = company_id

        # Register user in teams
        if team_ids:
            for team_id in team_ids:
                if team_id not in self.team_members:
                    self.team_members[team_id] = set()
                self.team_members[team_id].add(user_id)

        logger.info(f"User {user_id} (company={company_id}) connected via WebSocket")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                # Clean up company tracking
                if user_id in self.user_companies:
                    del self.user_companies[user_id]
                # Remove from teams
                for team_id, members in self.team_members.items():
                    members.discard(user_id)

        logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    disconnected.append(connection)

            # Clean up disconnected sockets
            for conn in disconnected:
                self.active_connections[user_id].discard(conn)

    async def broadcast_to_team(self, message: dict, team_id: int, exclude_user: int = None):
        """Broadcast a message to all team members"""
        if team_id in self.team_members:
            for user_id in self.team_members[team_id]:
                if user_id != exclude_user:
                    await self.send_personal_message(message, user_id)

    async def broadcast_to_company(self, message: dict, company_id: int | None, exclude_user: int = None):
        """Broadcast a message to all users in the same company (multi-tenant safe)"""
        for user_id in list(self.active_connections.keys()):
            if user_id != exclude_user:
                user_company = self.user_companies.get(user_id)
                # Match company_id exactly (both None or same value)
                if user_company == company_id:
                    await self.send_personal_message(message, user_id)

    async def broadcast_to_all(self, message: dict, exclude_user: int = None):
        """Broadcast a message to all connected users - USE WITH CAUTION (only for system-wide messages)"""
        for user_id in list(self.active_connections.keys()):
            if user_id != exclude_user:
                await self.send_personal_message(message, user_id)

    def set_active_timer(self, user_id: int, timer_info: dict):
        """Set active timer for a user"""
        self.active_timers[user_id] = {
            **timer_info,
            "user_id": user_id,
            "updated_at": now_utc().isoformat()
        }

    def clear_active_timer(self, user_id: int):
        """Clear active timer for a user"""
        if user_id in self.active_timers:
            del self.active_timers[user_id]

    def get_active_timers(self, team_id: int = None, company_filter = None) -> list[dict]:
        """Get all active timers, optionally filtered by team or company

        Args:
            team_id: Filter by team (optional)
            company_filter: Company filter from get_company_filter():
                - None: super_admin sees all
                - FILTER_NULL_COMPANY: platform users see only NULL company_id
                - int: company-scoped users see only their company
        """
        timers = list(self.active_timers.values())

        # Filter by company for multi-tenant isolation
        if company_filter is not None:
            if company_filter == FILTER_NULL_COMPANY:
                # Platform users without company see only NULL company_id timers
                timers = [t for t in timers if t.get("company_id") is None]
            else:
                # Company-scoped users see only their company's timers
                timers = [t for t in timers if t.get("company_id") == company_filter]
        # If company_filter is None (super_admin), return all timers

        # Filter by team if specified
        if team_id and team_id in self.team_members:
            team_user_ids = self.team_members[team_id]
            timers = [t for t in timers if t.get("user_id") in team_user_ids]

        return timers

    def get_online_users(self, team_id: int = None) -> list[int]:
        """Get list of online user IDs"""
        if team_id and team_id in self.team_members:
            return [uid for uid in self.team_members[team_id] if uid in self.active_connections]
        return list(self.active_connections.keys())

    # ============================================
    # MICRO-TASK SESSION BROADCASTS
    # ============================================

    async def broadcast_session_started(self, company_id: int | None, user_id: int, user_name: str, session_data: dict):
        """Broadcast when a user starts their work session."""
        await self.broadcast_to_company({
            "type": "session_started",
            "user_id": user_id,
            "user_name": user_name,
            "data": session_data
        }, company_id=company_id)

    async def broadcast_session_ended(self, company_id: int | None, user_id: int, user_name: str, session_data: dict):
        """Broadcast when a user ends their work session."""
        await self.broadcast_to_company({
            "type": "session_ended",
            "user_id": user_id,
            "user_name": user_name,
            "data": session_data
        }, company_id=company_id)

    async def broadcast_break_started(self, company_id: int | None, user_id: int, user_name: str, break_data: dict):
        """Broadcast when a user starts a break."""
        await self.broadcast_to_company({
            "type": "break_started",
            "user_id": user_id,
            "user_name": user_name,
            "data": break_data
        }, company_id=company_id)

    async def broadcast_break_ended(self, company_id: int | None, user_id: int, user_name: str, break_data: dict):
        """Broadcast when a user ends a break."""
        await self.broadcast_to_company({
            "type": "break_ended",
            "user_id": user_id,
            "user_name": user_name,
            "data": break_data
        }, company_id=company_id)

    async def broadcast_meeting_started(self, company_id: int | None, user_id: int, user_name: str, meeting_data: dict):
        """Broadcast when a user starts a meeting."""
        await self.broadcast_to_company({
            "type": "meeting_started",
            "user_id": user_id,
            "user_name": user_name,
            "data": meeting_data
        }, company_id=company_id)

    async def broadcast_meeting_ended(self, company_id: int | None, user_id: int, user_name: str, meeting_data: dict):
        """Broadcast when a user ends a meeting."""
        await self.broadcast_to_company({
            "type": "meeting_ended",
            "user_id": user_id,
            "user_name": user_name,
            "data": meeting_data
        }, company_id=company_id)

    async def broadcast_task_switched(self, company_id: int | None, user_id: int, user_name: str, task_data: dict):
        """Broadcast when a user switches to a different task."""
        await self.broadcast_to_company({
            "type": "task_switched",
            "user_id": user_id,
            "user_name": user_name,
            "data": task_data
        }, company_id=company_id)


# Global connection manager instance
manager = ConnectionManager()


async def load_active_timers_from_db(company_id: Optional[int] = None) -> int:
    """Load active (running) timers from the database into the manager cache.

    B13: tenant-scoped cache writes.
      * ``company_id=None`` — startup warm cache. Loads every tenant's
        running timers in a single pass; intended to run ONCE at app
        startup from ``main.py`` lifespan.
      * ``company_id=<int>`` — per-connection load. Loads only rows whose
        owning user's ``company_id`` matches. The cache is updated via
        ``dict.update`` so entries for other tenants are never touched.

    The function is best-effort and never raises. Failures are logged with
    the ``app.warm_cache_failed`` identifier so the app can continue with
    a (possibly empty) cache instead of crashing the WS connect path or
    the FastAPI startup hook.
    Returns the number of rows loaded (0 on failure).
    """
    from datetime import timezone

    from sqlalchemy import select

    from app.database import async_session
    from app.models import Project, Task, TimeEntry, User

    try:
        async with async_session() as db:
            stmt = (
                select(TimeEntry, User, Project, Task)
                .join(User, TimeEntry.user_id == User.id)
                .outerjoin(Project, TimeEntry.project_id == Project.id)
                .outerjoin(Task, TimeEntry.task_id == Task.id)
                .where(TimeEntry.end_time.is_(None))
            )
            if company_id is not None:
                stmt = stmt.where(User.company_id == company_id)

            result = await db.execute(stmt)
            rows = result.all()

            new_entries: Dict[int, dict] = {}
            for entry, user, project, task in rows:
                start = entry.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                elapsed = int((now_utc() - start).total_seconds())

                new_entries[user.id] = {
                    "user_id": user.id,
                    "user_name": user.name,
                    "company_id": user.company_id,  # For multi-tenant filtering
                    "project_id": project.id if project else None,
                    "project_name": project.name if project else "Meeting",
                    "task_id": task.id if task else None,
                    "task_name": task.name if task else None,
                    "description": entry.description,
                    "start_time": entry.start_time.isoformat(),
                    "elapsed_seconds": elapsed,
                }

            # Merge — never replace the entire cache. Entries for tenants
            # not in this query keep their existing values.
            manager.active_timers.update(new_entries)
            logger.info(
                "Loaded %d active timers from database (company_id=%s)",
                len(rows),
                company_id,
            )
            return len(rows)
    except Exception as e:
        logger.error(
            "app.warm_cache_failed: company_id=%s error=%s",
            company_id,
            e,
            exc_info=True,
        )
        return 0


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time updates.

    Connect with: ws://localhost:8080/api/ws/ws?token=<jwt_token>

    Message types:
    - ping: Keep-alive ping
    - timer_start: User started a timer
    - timer_stop: User stopped a timer
    - timer_update: Timer duration update
    - get_active_timers: Request list of active timers
    - get_online_users: Request list of online users
    """
    user = None
    try:
        # Authenticate user from token
        try:
            user = await get_current_user_ws(token)
        except BlacklistUnavailableError:
            # B4: fail-closed when JWT blacklist backend (Redis) is down.
            # Logged inside _check_blacklist_or_fail_closed.
            await websocket.close(
                code=1011, reason="Authentication service temporarily unavailable"
            )
            return
        if not user:
            await websocket.close(code=4001, reason="Authentication failed")
            return

        # B8 Part 2: populate team_ids from TeamMember at connect time.
        # The list is cached on the manager via ``connect()`` for the lifetime
        # of this connection. It is intentionally NOT refreshed during the
        # connection — team-membership changes mid-session won't propagate
        # until the client reconnects. This is acceptable for a realtime WS
        # path; see "Risks observed" in POST_LAUNCH_TODO.md.
        team_ids = await _load_user_team_ids(user.id)

        # Connect with company_id for multi-tenant broadcast filtering
        await manager.connect(websocket, user.id, team_ids, company_id=user.company_id)

        # B13: tenant-scoped cache load. Only rows for the connecting user's
        # company are merged into ``manager.active_timers``; entries for
        # other tenants are not touched. The full cross-tenant warm runs
        # once at startup from ``main.py`` lifespan.
        await load_active_timers_from_db(company_id=user.company_id)

        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "user_id": user.id,
            "message": "Connected to Time Tracker real-time service"
        })

        # Main message loop
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60)
                await handle_message(websocket, user, data)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive. B8/B21: targeted
                # exception handling — never swallow CancelledError, treat
                # protocol close as a clean exit, log everything else.
                try:
                    await websocket.send_json({"type": "ping"})
                except asyncio.CancelledError:
                    raise
                except WebSocketDisconnect:
                    break
                except (ConnectionClosedError, ConnectionClosedOK):
                    break
                except Exception as e:
                    logger.error(
                        "ws.ping_send_failed user_id=%s company_id=%s: %s",
                        user.id,
                        user.company_id,
                        e,
                        exc_info=True,
                    )
                    break
            except asyncio.CancelledError:
                raise
            except WebSocketDisconnect:
                break
            except (ConnectionClosedError, ConnectionClosedOK):
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.id if user else 'unknown'}")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if user:
            manager.disconnect(websocket, user.id)


async def _load_user_team_ids(user_id: int) -> list[int]:
    """Fetch the team IDs the user currently belongs to.

    Best-effort: on DB failure, returns an empty list and logs at ERROR.
    Team-scoped broadcasts will then simply not reach this connection
    until the client reconnects.
    """
    from sqlalchemy import select

    from app.database import async_session
    from app.models import TeamMember

    try:
        async with async_session() as db:
            result = await db.execute(
                select(TeamMember.team_id).where(TeamMember.user_id == user_id)
            )
            return [row[0] for row in result.all()]
    except Exception as e:
        logger.error(
            "ws.team_ids_load_failed user_id=%s: %s", user_id, e, exc_info=True
        )
        return []


async def handle_message(websocket: WebSocket, user: User, data: dict):
    """Handle incoming WebSocket messages"""
    msg_type = data.get("type")

    if msg_type == "ping":
        await websocket.send_json({"type": "pong"})

    elif msg_type == "pong":
        pass  # Client responded to our ping

    elif msg_type == "timer_start":
        # User started a timer
        timer_info = {
            "user_name": user.name,
            "company_id": user.company_id,  # For multi-tenant filtering
            "project_id": data.get("project_id"),
            "project_name": data.get("project_name"),
            "task_id": data.get("task_id"),
            "task_name": data.get("task_name"),
            "description": data.get("description"),
            "start_time": data.get("start_time", now_utc().isoformat())
        }
        manager.set_active_timer(user.id, timer_info)

        # Broadcast to SAME COMPANY ONLY (multi-tenant isolation)
        await manager.broadcast_to_company({
            "type": "timer_started",
            "user_id": user.id,
            "user_name": user.name,
            **timer_info
        }, company_id=user.company_id, exclude_user=user.id)

        # Confirm to sender
        await websocket.send_json({
            "type": "timer_start_confirmed",
            "timer": timer_info
        })

    elif msg_type == "timer_stop":
        # User stopped a timer
        manager.clear_active_timer(user.id)

        # Broadcast to SAME COMPANY ONLY (multi-tenant isolation)
        await manager.broadcast_to_company({
            "type": "timer_stopped",
            "user_id": user.id,
            "user_name": user.name,
            "duration_seconds": data.get("duration_seconds"),
            "project_name": data.get("project_name"),
            "task_name": data.get("task_name")
        }, company_id=user.company_id, exclude_user=user.id)

        # Confirm to sender
        await websocket.send_json({
            "type": "timer_stop_confirmed"
        })

    elif msg_type == "timer_update":
        # Periodic timer duration update
        if user.id in manager.active_timers:
            manager.active_timers[user.id]["elapsed_seconds"] = data.get("elapsed_seconds", 0)

    elif msg_type == "get_active_timers":
        # Request list of active timers with company filtering
        team_id = data.get("team_id")
        # Apply company filter for multi-tenant isolation using proper helper
        company_filter = get_company_filter(user)
        active_timers = manager.get_active_timers(team_id, company_filter)
        await websocket.send_json({
            "type": "active_timers",
            "timers": active_timers
        })

    elif msg_type == "get_online_users":
        # Request list of online users
        team_id = data.get("team_id")
        online_users = manager.get_online_users(team_id)
        await websocket.send_json({
            "type": "online_users",
            "users": online_users
        })

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })


# HTTP endpoints for real-time status (for clients that can't use WebSocket)

@router.get("/active-timers")
async def get_active_timers(
    team_id: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """Get list of currently active timers with company filtering"""
    # Apply company filter for multi-tenant isolation using proper helper
    company_filter = get_company_filter(current_user)
    timers = manager.get_active_timers(team_id, company_filter)
    return {
        "timers": timers,
        "count": len(timers)
    }


@router.get("/online-users")
async def get_online_users(
    team_id: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """Get list of currently online users"""
    return {
        "users": manager.get_online_users(team_id),
        "count": len(manager.get_online_users(team_id))
    }


