"""
Audit logging service for tracking all system changes
"""

from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from enum import Enum
import json
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Import AuditLog model from models
from app.models import AuditLog


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    ROLE_CHANGE = "ROLE_CHANGE"
    TIMER_START = "TIMER_START"
    TIMER_STOP = "TIMER_STOP"


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[int]
    user_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[int]
    ip_address: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    details: Optional[str]

    class Config:
        from_attributes = True


class PaginatedAuditLogs(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AuditLogger:
    """Service for logging audit events"""
    
    @staticmethod
    async def log(
        db: AsyncSession,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[int] = None,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        details: Optional[str] = None
    ):
        """Create an audit log entry"""
        log_entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            details=details
        )
        
        db.add(log_entry)
        # Note: caller should commit the transaction
    
    @staticmethod
    async def get_logs(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PaginatedAuditLogs:
        """Get paginated audit logs"""
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
            count_query = count_query.where(AuditLog.user_id == user_id)
        
        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
            count_query = count_query.where(AuditLog.resource_type == resource_type)
        
        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
            count_query = count_query.where(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)
            count_query = count_query.where(AuditLog.timestamp <= end_date)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(AuditLog.timestamp.desc())
        result = await db.execute(query)
        logs = result.scalars().all()
        
        items = []
        for log in logs:
            items.append(AuditLogResponse(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                user_email=log.user_email,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                ip_address=log.ip_address,
                old_values=json.loads(log.old_values) if log.old_values else None,
                new_values=json.loads(log.new_values) if log.new_values else None,
                details=log.details
            ))
        
        return PaginatedAuditLogs(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total > 0 else 1
        )


# Global instance
audit_logger = AuditLogger()
