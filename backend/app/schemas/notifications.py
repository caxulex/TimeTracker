# ============================================
# TIME TRACKER - NOTIFICATION SCHEMAS
# ============================================
# Pydantic schemas for in-app notifications.
# ============================================

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class NotificationTypeEnum(str, Enum):
    """Notification type enumeration"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    TIMER_REMINDER = "timer_reminder"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    TEAM_UPDATE = "team_update"
    PAYROLL = "payroll"
    SYSTEM = "system"


class NotificationBase(BaseModel):
    """Base schema for notifications"""
    type: NotificationTypeEnum = NotificationTypeEnum.INFO
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    link: Optional[str] = Field(None, max_length=500)
    entity_type: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    """Schema for creating notifications"""
    user_id: int


class NotificationBulkCreate(NotificationBase):
    """Schema for creating notifications for multiple users"""
    user_ids: List[int] = Field(..., min_items=1)


class NotificationResponse(NotificationBase):
    """Schema for notification response"""
    id: int
    user_id: int
    company_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list"""
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    """Schema for marking notifications as read"""
    notification_ids: Optional[List[int]] = None  # If None, mark all as read


class NotificationMarkReadResponse(BaseModel):
    """Schema for mark read response"""
    updated_count: int
    message: str


class NotificationDeleteRequest(BaseModel):
    """Schema for deleting notifications"""
    notification_ids: Optional[List[int]] = None  # If None, delete all read notifications


class NotificationDeleteResponse(BaseModel):
    """Schema for delete response"""
    deleted_count: int
    message: str


class UnreadCountResponse(BaseModel):
    """Schema for unread count response"""
    unread_count: int
