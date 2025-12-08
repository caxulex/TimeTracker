"""
Pydantic schemas for authentication
SEC-003: Enhanced with password strength validation hints
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
import re


class UserRegister(BaseModel):
    """Schema for user registration with strong password requirements"""
    email: EmailStr
    password: str = Field(
        ..., 
        min_length=12, 
        max_length=128,
        description="Password must be 12-128 characters with uppercase, lowercase, number, and special character"
    )
    name: str = Field(..., min_length=1, max_length=255)
    
    @field_validator('password')
    @classmethod
    def validate_password_basic(cls, v: str) -> str:
        """Basic password validation - detailed validation done in endpoint"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request"""
    refresh_token: str


class PasswordChange(BaseModel):
    """Schema for password change with strong validation"""
    current_password: str
    new_password: str = Field(
        ..., 
        min_length=12, 
        max_length=128,
        description="Password must be 12-128 characters with uppercase, lowercase, number, and special character"
    )

    @field_validator('new_password')
    @classmethod
    def validate_new_password_basic(cls, v: str) -> str:
        """Basic password validation - detailed validation done in endpoint"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        return v


class UserResponse(BaseModel):
    """Schema for user response (no sensitive data)"""
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    
    # Contact Information
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    
    # Employment Details
    job_title: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None  # full_time, part_time, contractor
    start_date: Optional[str] = None  # date as string
    expected_hours_per_week: Optional[float] = None
    manager_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user profile update"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None


class Message(BaseModel):
    """Generic message response"""
    message: str


class PasswordStrength(BaseModel):
    """Schema for password strength response"""
    score: int = Field(..., ge=0, le=100, description="Password strength score 0-100")
    label: str = Field(..., description="Human-readable strength label")
    is_valid: bool = Field(..., description="Whether password meets all requirements")
    errors: list[str] = Field(default=[], description="List of validation errors")


class SecurityStatus(BaseModel):
    """Schema for security status information"""
    account_locked: bool = False
    lockout_remaining_seconds: int = 0
    failed_attempts: int = 0
    max_attempts: int = 5
