"""
Pydantic schemas for API Key management
SEC-020: Secure API Key Storage for AI Integrations
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class AIProviderEnum(str, Enum):
    """Supported AI providers"""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    OTHER = "other"


# ============================================
# REQUEST SCHEMAS
# ============================================

class APIKeyCreate(BaseModel):
    """Schema for creating a new API key"""
    provider: AIProviderEnum = Field(..., description="AI provider name")
    api_key: str = Field(..., min_length=10, description="The actual API key (will be encrypted)")
    label: Optional[str] = Field(None, max_length=255, description="Optional friendly name")
    notes: Optional[str] = Field(None, description="Optional notes about this key")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Ensure API key is not empty and has reasonable length"""
        if not v or not v.strip():
            raise ValueError("API key cannot be empty")
        if len(v) < 10:
            raise ValueError("API key is too short")
        if len(v) > 500:
            raise ValueError("API key is too long")
        return v.strip()


class APIKeyUpdate(BaseModel):
    """Schema for updating an existing API key"""
    api_key: Optional[str] = Field(None, min_length=10, description="New API key (will be encrypted)")
    label: Optional[str] = Field(None, max_length=255, description="Optional friendly name")
    notes: Optional[str] = Field(None, description="Optional notes")
    is_active: Optional[bool] = Field(None, description="Enable/disable the key")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate API key if provided"""
        if v is not None:
            if not v.strip():
                raise ValueError("API key cannot be empty")
            if len(v) < 10:
                raise ValueError("API key is too short")
            if len(v) > 500:
                raise ValueError("API key is too long")
            return v.strip()
        return v


class APIKeyTestRequest(BaseModel):
    """Schema for testing an API key's connectivity"""
    provider: Optional[AIProviderEnum] = Field(None, description="Override provider for testing")


# ============================================
# RESPONSE SCHEMAS
# ============================================

class APIKeyResponse(BaseModel):
    """Schema for API key responses (never exposes actual key)"""
    id: int
    provider: str
    key_preview: str  # e.g., "...xxxx"
    label: Optional[str] = None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    usage_count: int
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Schema for paginated API key list"""
    items: List[APIKeyResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class APIKeyTestResponse(BaseModel):
    """Schema for API key test results"""
    success: bool
    provider: str
    message: str
    latency_ms: Optional[float] = None
    model_available: Optional[str] = None


class APIKeyProviderInfo(BaseModel):
    """Information about a supported AI provider"""
    id: str
    name: str
    description: str
    key_format_hint: str
    documentation_url: Optional[str] = None


class SupportedProvidersResponse(BaseModel):
    """Schema for listing supported providers"""
    providers: List[APIKeyProviderInfo]


# ============================================
# INTERNAL SCHEMAS (for service layer)
# ============================================

class APIKeyInternal(BaseModel):
    """Internal schema with decrypted key (never sent to frontend)"""
    id: int
    provider: str
    decrypted_key: str  # The actual decrypted API key
    is_active: bool
    
    class Config:
        from_attributes = True


# Provider metadata
SUPPORTED_PROVIDERS: List[APIKeyProviderInfo] = [
    APIKeyProviderInfo(
        id="gemini",
        name="Google Gemini",
        description="Google's Gemini AI models for text generation and analysis",
        key_format_hint="API key from Google AI Studio (typically 39 characters)",
        documentation_url="https://ai.google.dev/docs"
    ),
    APIKeyProviderInfo(
        id="openai",
        name="OpenAI",
        description="OpenAI's GPT models for text generation, embeddings, and more",
        key_format_hint="Starts with 'sk-' or 'sk-proj-'",
        documentation_url="https://platform.openai.com/docs"
    ),
    APIKeyProviderInfo(
        id="anthropic",
        name="Anthropic Claude",
        description="Anthropic's Claude models for safe and helpful AI",
        key_format_hint="Starts with 'sk-ant-'",
        documentation_url="https://docs.anthropic.com"
    ),
    APIKeyProviderInfo(
        id="azure_openai",
        name="Azure OpenAI",
        description="Microsoft Azure-hosted OpenAI models",
        key_format_hint="API key from Azure OpenAI resource",
        documentation_url="https://learn.microsoft.com/azure/ai-services/openai/"
    ),
    APIKeyProviderInfo(
        id="other",
        name="Other Provider",
        description="Custom or unsupported AI provider",
        key_format_hint="Depends on provider",
        documentation_url=None
    ),
]
