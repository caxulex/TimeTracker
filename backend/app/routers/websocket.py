"""
Time Tracker API - WebSocket Router for Real-time Features
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional
import json
import logging
import asyncio
from datetime import datetime

from app.dependencies import get_current_user_ws, get_current_user
from app.models import User

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
    
    async def connect(self, websocket: WebSocket, user_id: int, team_ids: list[int] = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Register user in teams
        if team_ids:
            for team_id in team_ids:
                if team_id not in self.team_members:
                    self.team_members[team_id] = set()
                self.team_members[team_id].add(user_id)
        
        logger.info(f"User {user_id} connected via WebSocket")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
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
    
    async def broadcast_to_all(self, message: dict, exclude_user: int = None):
        """Broadcast a message to all connected users"""
        for user_id in list(self.active_connections.keys()):
            if user_id != exclude_user:
                await self.send_personal_message(message, user_id)
    
    def set_active_timer(self, user_id: int, timer_info: dict):
        """Set active timer for a user"""
        self.active_timers[user_id] = {
            **timer_info,
            "user_id": user_id,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    def clear_active_timer(self, user_id: int):
        """Clear active timer for a user"""
        if user_id in self.active_timers:
            del self.active_timers[user_id]
    
    def get_active_timers(self, team_id: int = None, company_id: int = None) -> list[dict]:
        """Get all active timers, optionally filtered by team or company"""
        timers = list(self.active_timers.values())
        
        # Filter by company if specified (multi-tenant isolation)
        if company_id is not None:
            timers = [t for t in timers if t.get("company_id") == company_id]
        
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


# Global connection manager instance
manager = ConnectionManager()


async def load_active_timers_from_db():
    """Load all active timers from the database into the connection manager"""
    from app.database import get_db
    from app.models import TimeEntry, User, Project, Task
    from sqlalchemy import select
    from datetime import timezone, datetime as dt
    
    # Get a database session
    async for db in get_db():
        try:
            # Query all active time entries
            result = await db.execute(
                select(TimeEntry, User, Project, Task)
                .join(User, TimeEntry.user_id == User.id)
                .join(Project, TimeEntry.project_id == Project.id)
                .outerjoin(Task, TimeEntry.task_id == Task.id)
                .where(TimeEntry.end_time == None)
            )
            
            rows = result.all()
            
            # Update the manager's active_timers dictionary
            for entry, user, project, task in rows:
                # Calculate elapsed seconds
                start = entry.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                now = dt.now(timezone.utc)
                elapsed = int((now - start).total_seconds())
                
                timer_info = {
                    "user_id": user.id,
                    "user_name": user.name,
                    "company_id": user.company_id,  # For multi-tenant filtering
                    "project_id": project.id,
                    "project_name": project.name,
                    "task_id": task.id if task else None,
                    "task_name": task.name if task else None,
                    "description": entry.description,
                    "start_time": entry.start_time.isoformat(),
                    "elapsed_seconds": elapsed
                }
                
                manager.active_timers[user.id] = timer_info
                
            logger.info(f"Loaded {len(rows)} active timers from database")
            
        except Exception as e:
            logger.error(f"Error loading active timers: {e}")
        finally:
            await db.close()
        break  # Only need one iteration of the async generator


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
        user = await get_current_user_ws(token)
        if not user:
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        # Get user's team IDs (simplified - in production, fetch from DB)
        team_ids = []  # Could be populated from user's teams
        
        await manager.connect(websocket, user.id, team_ids)
        
        # Load active timers from database and populate the manager
        await load_active_timers_from_db()
        
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
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.id if user else 'unknown'}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if user:
            manager.disconnect(websocket, user.id)


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
            "start_time": data.get("start_time", datetime.utcnow().isoformat())
        }
        manager.set_active_timer(user.id, timer_info)
        
        # Broadcast to team
        await manager.broadcast_to_all({
            "type": "timer_started",
            "user_id": user.id,
            "user_name": user.name,
            **timer_info
        }, exclude_user=user.id)
        
        # Confirm to sender
        await websocket.send_json({
            "type": "timer_start_confirmed",
            "timer": timer_info
        })
    
    elif msg_type == "timer_stop":
        # User stopped a timer
        manager.clear_active_timer(user.id)
        
        # Broadcast to team
        await manager.broadcast_to_all({
            "type": "timer_stopped",
            "user_id": user.id,
            "user_name": user.name,
            "duration_seconds": data.get("duration_seconds"),
            "project_name": data.get("project_name"),
            "task_name": data.get("task_name")
        }, exclude_user=user.id)
        
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
        # Apply company filter for multi-tenant isolation
        company_id = user.company_id if (user.company_id is not None or user.role != 'super_admin') else None
        active_timers = manager.get_active_timers(team_id, company_id)
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
    # Apply company filter for multi-tenant isolation
    company_id = current_user.company_id if (current_user.company_id is not None or current_user.role != 'super_admin') else None
    timers = manager.get_active_timers(team_id, company_id)
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


