"""
Account request schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class AccountRequestCreate(BaseModel):
    """Schema for creating a new account request"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    message: Optional[str] = Field(None, max_length=500)


class AccountRequestResponse(BaseModel):
    """Schema for account request response"""
    id: int
    email: str
    name: str
    phone: Optional[str]
    job_title: Optional[str]
    department: Optional[str]
    message: Optional[str]
    status: str
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[int]
    admin_notes: Optional[str]
    
    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    """Schema for approval/rejection decision"""
    admin_notes: Optional[str] = Field(None, max_length=1000)


class PaginatedAccountRequests(BaseModel):
    """Paginated account requests response"""
    items: list[AccountRequestResponse]
    total: int
    page: int
    page_size: int
    pages: int
