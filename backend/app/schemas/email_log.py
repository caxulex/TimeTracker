# ============================================
# TIME TRACKER - EMAIL LOG SCHEMAS
# ============================================
# Pydantic schemas for email log tracking and monitoring.
# ============================================

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class EmailStatusEnum(str, Enum):
    """Email status enumeration"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class EmailTypeEnum(str, Enum):
    """Email type enumeration"""
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_APPROVED = "account_approved"
    ACCOUNT_REJECTED = "account_rejected"
    ACCOUNT_REQUEST_NOTIFICATION = "account_request_notification"
    PAYROLL_NOTIFICATION = "payroll_notification"
    TIME_ENTRY_REMINDER = "time_entry_reminder"
    NOTIFICATION = "notification"
    OTHER = "other"


class EmailLogBase(BaseModel):
    """Base schema for email logs"""
    to_email: str
    from_email: str
    subject: str
    email_type: str
    status: EmailStatusEnum = EmailStatusEnum.PENDING
    error_message: Optional[str] = None
    email_metadata: Optional[Dict[str, Any]] = None


class EmailLogCreate(EmailLogBase):
    """Schema for creating email logs"""
    company_id: Optional[int] = None


class EmailLogResponse(EmailLogBase):
    """Schema for email log response"""
    id: int
    company_id: Optional[int] = None
    retry_count: int
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailLogSummary(BaseModel):
    """Summary statistics for email logs"""
    total_emails: int
    sent_count: int
    delivered_count: int
    failed_count: int
    pending_count: int
    bounced_count: int
    success_rate: float  # Percentage of successful emails


class PaginatedEmailLogs(BaseModel):
    """Paginated email logs response"""
    items: List[EmailLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmailLogFilter(BaseModel):
    """Filter options for email log queries"""
    status: Optional[EmailStatusEnum] = None
    email_type: Optional[str] = None
    to_email: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
