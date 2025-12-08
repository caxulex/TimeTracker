"""
Audit Logging Service
SEC-015: Comprehensive Audit Logging Implementation
Logs security-relevant events for monitoring and compliance
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from enum import Enum
from redis.asyncio import Redis
import redis.asyncio as redis_module

from app.config import settings

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events"""
    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    PASSWORD_CHANGE = "auth.password.change"
    PASSWORD_RESET_REQUEST = "auth.password.reset_request"
    
    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_DEACTIVATED = "user.deactivated"
    USER_ACTIVATED = "user.activated"
    USER_ROLE_CHANGED = "user.role.changed"
    
    # Account security events
    ACCOUNT_LOCKED = "security.account.locked"
    ACCOUNT_UNLOCKED = "security.account.unlocked"
    SUSPICIOUS_ACTIVITY = "security.suspicious"
    RATE_LIMITED = "security.rate_limited"
    
    # Data access events
    PAYROLL_ACCESSED = "data.payroll.accessed"
    PAYROLL_EXPORTED = "data.payroll.exported"
    REPORT_GENERATED = "data.report.generated"
    SENSITIVE_DATA_VIEWED = "data.sensitive.viewed"
    
    # Admin events
    ADMIN_ACTION = "admin.action"
    CONFIG_CHANGED = "admin.config.changed"
    SYSTEM_SETTING_CHANGED = "admin.setting.changed"
    
    # API events
    API_ERROR = "api.error"
    PERMISSION_DENIED = "api.permission.denied"


class AuditSeverity(str, Enum):
    """Severity levels for audit events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogService:
    """
    Service for creating and querying audit logs.
    Logs to both application logger and Redis for persistence.
    """
    
    def __init__(self):
        self._redis: Optional[Redis] = None
        self._prefix = "audit:"
        self._max_logs_in_memory = 10000
        self._retention_days = 90  # Keep logs for 90 days
    
    async def get_redis(self) -> Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            try:
                self._redis = redis_module.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
            except Exception as e:
                logger.error(f"Failed to connect to Redis for audit logging: {e}")
                raise
        return self._redis
    
    async def log(
        self,
        event_type: AuditEventType,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        success: bool = True
    ) -> str:
        """
        Create an audit log entry.
        
        Args:
            event_type: Type of audit event
            user_id: ID of user performing action
            user_email: Email of user performing action
            ip_address: Client IP address
            user_agent: Client user agent string
            resource_type: Type of resource being accessed
            resource_id: ID of resource being accessed
            action: Specific action performed
            details: Additional details (dict)
            severity: Log severity level
            success: Whether the action succeeded
        
        Returns:
            Audit log entry ID
        """
        timestamp = datetime.now(timezone.utc)
        log_id = f"{timestamp.strftime('%Y%m%d%H%M%S%f')}-{event_type.value}"
        
        log_entry = {
            "id": log_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value,
            "severity": severity.value,
            "success": success,
            "user_id": user_id,
            "user_email": user_email,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "details": details or {}
        }
        
        # Log to application logger
        log_message = f"AUDIT: {event_type.value} | user={user_email or user_id} | ip={ip_address} | success={success}"
        if details:
            log_message += f" | details={json.dumps(details)}"
        
        log_level = getattr(logging, severity.value.upper(), logging.INFO)
        logger.log(log_level, log_message)
        
        # Store in Redis
        try:
            redis_client = await self.get_redis()
            
            # Store log entry
            key = f"{self._prefix}log:{log_id}"
            await redis_client.setex(
                key,
                self._retention_days * 24 * 60 * 60,
                json.dumps(log_entry)
            )
            
            # Add to sorted set for time-based queries
            await redis_client.zadd(
                f"{self._prefix}timeline",
                {log_id: timestamp.timestamp()}
            )
            
            # Add to user-specific list if user_id provided
            if user_id:
                await redis_client.lpush(
                    f"{self._prefix}user:{user_id}",
                    log_id
                )
                await redis_client.ltrim(
                    f"{self._prefix}user:{user_id}",
                    0,
                    999  # Keep last 1000 events per user
                )
            
            # Add to event type list
            await redis_client.lpush(
                f"{self._prefix}type:{event_type.value}",
                log_id
            )
            await redis_client.ltrim(
                f"{self._prefix}type:{event_type.value}",
                0,
                999
            )
            
        except Exception as e:
            logger.error(f"Failed to store audit log in Redis: {e}")
        
        return log_id
    
    async def log_auth_success(
        self,
        user_id: int,
        user_email: str,
        ip_address: str,
        user_agent: Optional[str] = None
    ):
        """Log successful authentication"""
        await self.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=AuditSeverity.INFO,
            success=True
        )
    
    async def log_auth_failure(
        self,
        email: str,
        ip_address: str,
        reason: str,
        user_agent: Optional[str] = None
    ):
        """Log failed authentication"""
        await self.log(
            event_type=AuditEventType.LOGIN_FAILED,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"reason": reason},
            severity=AuditSeverity.WARNING,
            success=False
        )
    
    async def log_logout(
        self,
        user_id: int,
        user_email: str,
        ip_address: str
    ):
        """Log user logout"""
        await self.log(
            event_type=AuditEventType.LOGOUT,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address
        )
    
    async def log_account_locked(
        self,
        email: str,
        ip_address: str,
        attempts: int
    ):
        """Log account lockout"""
        await self.log(
            event_type=AuditEventType.ACCOUNT_LOCKED,
            user_email=email,
            ip_address=ip_address,
            details={"failed_attempts": attempts},
            severity=AuditSeverity.WARNING,
            success=False
        )
    
    async def log_permission_denied(
        self,
        user_id: int,
        user_email: str,
        ip_address: str,
        resource: str,
        action: str
    ):
        """Log permission denied event"""
        await self.log(
            event_type=AuditEventType.PERMISSION_DENIED,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            resource_type=resource,
            action=action,
            severity=AuditSeverity.WARNING,
            success=False
        )
    
    async def log_payroll_access(
        self,
        user_id: int,
        user_email: str,
        ip_address: str,
        payroll_period_id: Optional[int] = None,
        action: str = "view"
    ):
        """Log payroll data access"""
        await self.log(
            event_type=AuditEventType.PAYROLL_ACCESSED,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            resource_type="payroll_period",
            resource_id=str(payroll_period_id) if payroll_period_id else None,
            action=action,
            severity=AuditSeverity.INFO
        )
    
    async def log_admin_action(
        self,
        admin_id: int,
        admin_email: str,
        ip_address: str,
        action: str,
        target_user_id: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """Log admin action"""
        await self.log(
            event_type=AuditEventType.ADMIN_ACTION,
            user_id=admin_id,
            user_email=admin_email,
            ip_address=ip_address,
            resource_type="user" if target_user_id else None,
            resource_id=str(target_user_id) if target_user_id else None,
            action=action,
            details=details,
            severity=AuditSeverity.INFO
        )
    
    async def get_user_logs(
        self,
        user_id: int,
        limit: int = 100
    ) -> list:
        """Get audit logs for a specific user"""
        try:
            redis_client = await self.get_redis()
            log_ids = await redis_client.lrange(
                f"{self._prefix}user:{user_id}",
                0,
                limit - 1
            )
            
            logs = []
            for log_id in log_ids:
                log_data = await redis_client.get(f"{self._prefix}log:{log_id}")
                if log_data:
                    logs.append(json.loads(log_data))
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get user logs: {e}")
            return []
    
    async def get_recent_logs(
        self,
        event_type: Optional[AuditEventType] = None,
        limit: int = 100
    ) -> list:
        """Get recent audit logs, optionally filtered by event type"""
        try:
            redis_client = await self.get_redis()
            
            if event_type:
                log_ids = await redis_client.lrange(
                    f"{self._prefix}type:{event_type.value}",
                    0,
                    limit - 1
                )
            else:
                # Get from timeline
                log_ids = await redis_client.zrevrange(
                    f"{self._prefix}timeline",
                    0,
                    limit - 1
                )
            
            logs = []
            for log_id in log_ids:
                log_data = await redis_client.get(f"{self._prefix}log:{log_id}")
                if log_data:
                    logs.append(json.loads(log_data))
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get recent logs: {e}")
            return []
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global instance
audit_log = AuditLogService()
