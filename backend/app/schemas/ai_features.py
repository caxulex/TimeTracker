"""
Pydantic schemas for AI Feature Toggle System.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================
# GLOBAL FEATURE SETTINGS SCHEMAS
# ============================================

class AIFeatureSettingBase(BaseModel):
    """Base schema for AI feature settings."""
    feature_id: str = Field(..., description="Unique feature identifier")
    feature_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Feature description")
    is_enabled: bool = Field(True, description="Global enabled status")
    requires_api_key: bool = Field(True, description="Whether feature requires API key")
    api_provider: Optional[str] = Field(None, description="Required API provider")


class AIFeatureSettingResponse(AIFeatureSettingBase):
    """Schema for returning AI feature settings."""
    id: int
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class AIFeatureSettingUpdate(BaseModel):
    """Schema for updating global AI feature settings (admin only)."""
    is_enabled: bool = Field(..., description="Enable or disable the feature globally")


# ============================================
# USER PREFERENCE SCHEMAS
# ============================================

class UserAIPreferenceBase(BaseModel):
    """Base schema for user AI preferences."""
    feature_id: str = Field(..., description="Feature identifier")
    is_enabled: bool = Field(True, description="User's preference for this feature")


class UserAIPreferenceResponse(UserAIPreferenceBase):
    """Schema for returning user AI preferences."""
    id: int
    user_id: int
    admin_override: bool = Field(False, description="Whether admin has overridden this setting")
    admin_override_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserAIPreferenceUpdate(BaseModel):
    """Schema for updating user's own AI preference."""
    is_enabled: bool = Field(..., description="Enable or disable the feature for yourself")


class AdminOverrideRequest(BaseModel):
    """Schema for admin to override a user's preference."""
    is_enabled: bool = Field(..., description="Force this setting for the user")


# ============================================
# FEATURE STATUS SCHEMAS
# ============================================

class FeatureStatusResponse(BaseModel):
    """Detailed feature status for a user."""
    feature_id: str
    feature_name: str
    description: Optional[str] = None
    api_provider: Optional[str] = None
    is_enabled: bool = Field(..., description="Final computed status")
    global_enabled: bool = Field(..., description="Global admin setting")
    user_enabled: Optional[bool] = Field(None, description="User's preference (if set)")
    admin_override: bool = Field(False, description="Whether admin has overridden")
    reason: str = Field(..., description="Human-readable reason for status")


class UserFeaturesResponse(BaseModel):
    """Complete list of features with status for a user."""
    features: List[FeatureStatusResponse]


# ============================================
# ADMIN SUMMARY SCHEMAS
# ============================================

class FeatureUsageStats(BaseModel):
    """Usage statistics for a feature."""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time_ms: float = 0.0
    success_rate: float = 100.0
    period_days: int = 30


class AdminFeatureSummary(BaseModel):
    """Admin-level feature summary with usage stats."""
    feature_id: str
    feature_name: str
    description: Optional[str] = None
    is_enabled: bool
    api_provider: Optional[str] = None
    requires_api_key: bool = True
    enabled_user_count: int = 0
    total_user_count: int = 0
    usage_this_month: FeatureUsageStats


class AdminFeaturesResponse(BaseModel):
    """Complete admin features summary."""
    features: List[AdminFeatureSummary]


class UserPreferenceAdminView(BaseModel):
    """Admin view of a user's AI preferences."""
    user_id: int
    user_name: str
    user_email: str
    preferences: List[FeatureStatusResponse]


# ============================================
# USAGE LOG SCHEMAS
# ============================================

class AIUsageLogCreate(BaseModel):
    """Schema for creating usage log entry."""
    feature_id: str
    api_provider: Optional[str] = None
    tokens_used: Optional[int] = None
    estimated_cost: Optional[Decimal] = None
    response_time_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AIUsageLogResponse(BaseModel):
    """Schema for returning usage log entry."""
    id: int
    user_id: Optional[int] = None
    feature_id: str
    api_provider: Optional[str] = None
    tokens_used: Optional[int] = None
    estimated_cost: Optional[float] = None
    request_timestamp: datetime
    response_time_ms: Optional[int] = None
    success: bool
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class UsageSummaryResponse(BaseModel):
    """Overall AI usage summary."""
    period_days: int
    total_requests: int
    total_tokens: int
    total_cost: float
    unique_users: int
    features: Dict[str, Dict[str, Any]]


class UserUsageSummaryResponse(BaseModel):
    """User-specific usage summary."""
    user_id: int
    period_days: int
    total_tokens: int
    total_cost: float
    features: Dict[str, Dict[str, Any]]


# ============================================
# BATCH OPERATIONS
# ============================================

class BatchUserOverrideRequest(BaseModel):
    """Batch update preferences for multiple users."""
    user_ids: List[int] = Field(..., description="List of user IDs to update")
    feature_id: str = Field(..., description="Feature to update")
    is_enabled: bool = Field(..., description="Enable or disable for these users")


class BatchUpdateResponse(BaseModel):
    """Response for batch operations."""
    success: bool
    updated_count: int
    failed_count: int = 0
    message: str
