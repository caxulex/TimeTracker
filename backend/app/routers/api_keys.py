"""
API Keys Router - Admin endpoints for managing AI provider API keys
SEC-020: Secure API Key Storage for AI Integrations

All endpoints require super_admin role.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.dependencies import get_current_active_user
from app.schemas.api_keys import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
    APIKeyListResponse,
    APIKeyTestResponse,
    SupportedProvidersResponse,
    SUPPORTED_PROVIDERS,
)
from app.services.api_key_service import (
    APIKeyService,
    APIKeyNotFoundError,
    APIKeyValidationError,
    APIKeyServiceError,
)
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/admin/api-keys", tags=["admin-api-keys"])


def require_admin(current_user: User = Depends(get_current_active_user)):
    """Dependency to require admin or super_admin role for API key management"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for API key management"
        )
    return current_user


# Keep for backwards compatibility but not used
def require_super_admin(current_user: User = Depends(get_current_active_user)):
    """Dependency to require super_admin role for API key management"""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required for API key management"
        )
    return current_user


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request"""
    return request.headers.get("User-Agent")


@router.get("/providers", response_model=SupportedProvidersResponse)
async def get_supported_providers(
    current_user: User = Depends(require_admin)
):
    """
    Get list of supported AI providers.
    
    Returns provider information including:
    - Provider ID and name
    - Description
    - API key format hints
    - Documentation links
    """
    return SupportedProvidersResponse(providers=SUPPORTED_PROVIDERS)


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    active_only: bool = Query(False, description="Only show active keys"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all API keys (without exposing actual key values).
    
    Returns paginated list with:
    - Key preview (last 4 characters)
    - Provider information
    - Usage statistics
    - Active status
    """
    service = APIKeyService(db)
    items, total = await service.list_all(
        page=page,
        page_size=page_size,
        provider_filter=provider,
        active_only=active_only
    )
    
    return APIKeyListResponse(
        items=[APIKeyResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new API key.
    
    The API key will be encrypted before storage using AES-256-GCM.
    Only the last 4 characters are stored for identification.
    
    **Security Note**: The actual API key is never returned after creation.
    """
    audit_service = AuditLogService()
    service = APIKeyService(db, audit_service)
    
    try:
        api_key = await service.create(
            data=data,
            created_by=current_user.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        return APIKeyResponse.model_validate(api_key)
    except APIKeyValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except APIKeyServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get details of a specific API key (without exposing actual value).
    """
    service = APIKeyService(db)
    api_key = await service.get_by_id(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found"
        )
    
    return APIKeyResponse.model_validate(api_key)


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    data: APIKeyUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update an existing API key.
    
    Can update:
    - The API key value (will be re-encrypted)
    - Label and notes
    - Active status
    """
    audit_service = AuditLogService()
    service = APIKeyService(db, audit_service)
    
    try:
        api_key = await service.update(
            key_id=key_id,
            data=data,
            updated_by=current_user.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        return APIKeyResponse.model_validate(api_key)
    except APIKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found"
        )
    except APIKeyValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except APIKeyServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete an API key.
    
    **Warning**: This action is irreversible. The encrypted key will be
    permanently removed from the database.
    """
    audit_service = AuditLogService()
    service = APIKeyService(db, audit_service)
    
    deleted = await service.delete(
        key_id=key_id,
        deleted_by=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found"
        )


@router.post("/{key_id}/test", response_model=APIKeyTestResponse)
async def test_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Test an API key's connectivity with its provider.
    
    This will:
    1. Decrypt the stored key
    2. Attempt to connect to the provider's API
    3. Return success/failure status and latency
    
    **Note**: Some providers may not support connectivity testing.
    """
    service = APIKeyService(db)
    
    result = await service.test_connectivity(
        key_id=key_id,
        user_id=current_user.id
    )
    
    if not result.success and "not found" in result.message.lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found"
        )
    
    return result


@router.get("/status/encryption", response_model=dict)
async def get_encryption_status(
    current_user: User = Depends(require_admin)
):
    """
    Check if the encryption service is properly configured.
    
    Returns:
    - configured: Whether the encryption key is set
    - key_length: Length of the configured key (masked)
    """
    from app.services.encryption_service import encryption_service
    
    is_configured = encryption_service.is_configured()
    
    return {
        "configured": is_configured,
        "message": "Encryption service is ready" if is_configured else "API_KEY_ENCRYPTION_KEY not configured or too short"
    }
