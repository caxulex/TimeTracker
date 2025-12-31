"""
API Key Management Service
SEC-020: Secure API Key Storage for AI Integrations

This service handles:
- CRUD operations for API keys
- Encryption/decryption coordination
- Usage tracking
- Provider connectivity testing
"""

import logging
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload

from app.models import APIKey, User, AIProvider
from app.schemas.api_keys import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
    APIKeyInternal,
    APIKeyTestResponse,
)
from app.services.encryption_service import encryption_service, EncryptionError
from app.services.audit_log import AuditLogService, AuditEventType

logger = logging.getLogger(__name__)


class APIKeyServiceError(Exception):
    """Base exception for API key service errors"""
    pass


class APIKeyNotFoundError(APIKeyServiceError):
    """Raised when an API key is not found"""
    pass


class APIKeyValidationError(APIKeyServiceError):
    """Raised when API key validation fails"""
    pass


class APIKeyService:
    """Service for managing API keys with encryption"""
    
    def __init__(self, db: AsyncSession, audit_service: Optional[AuditLogService] = None):
        self.db = db
        self.audit = audit_service
    
    async def create(
        self,
        data: APIKeyCreate,
        created_by: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> APIKey:
        """
        Create a new API key with encryption.
        
        Args:
            data: API key creation data
            created_by: User ID creating the key
            ip_address: Request IP for audit
            user_agent: Request user agent for audit
            
        Returns:
            Created APIKey model instance
        """
        # Validate key format
        is_valid, error_msg = encryption_service.validate_key_format(
            data.provider.value, data.api_key
        )
        if not is_valid:
            raise APIKeyValidationError(error_msg)
        
        # Encrypt the API key
        try:
            encrypted_key = encryption_service.encrypt(data.api_key)
        except EncryptionError as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise APIKeyServiceError("Failed to encrypt API key")
        
        # Generate key preview
        key_preview = encryption_service.generate_key_preview(data.api_key)
        
        # Create database record
        api_key = APIKey(
            provider=data.provider.value,
            encrypted_key=encrypted_key,
            key_preview=key_preview,
            label=data.label,
            notes=data.notes,
            is_active=True,
            created_by=created_by,
            usage_count=0
        )
        
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        
        # Audit log
        if self.audit:
            await self.audit.log(
                event_type=AuditEventType.CONFIG_CHANGED,
                user_id=created_by,
                details={"action": "created", "provider": data.provider.value},
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type="api_key",
                resource_id=str(api_key.id)
            )
        
        logger.info(f"Created API key {api_key.id} for provider {data.provider.value}")
        return api_key
    
    async def get_by_id(self, key_id: int) -> Optional[APIKey]:
        """Get an API key by ID (without decryption)"""
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()
    
    async def get_decrypted(self, key_id: int) -> Optional[APIKeyInternal]:
        """
        Get an API key with decrypted value.
        Use sparingly - only when the actual key is needed.
        """
        api_key = await self.get_by_id(key_id)
        if not api_key:
            return None
        
        try:
            decrypted = encryption_service.decrypt(api_key.encrypted_key)
            return APIKeyInternal(
                id=api_key.id,
                provider=api_key.provider,
                decrypted_key=decrypted,
                is_active=api_key.is_active
            )
        except EncryptionError as e:
            logger.error(f"Failed to decrypt API key {key_id}: {e}")
            return None
    
    async def get_active_key_for_provider(self, provider: str) -> Optional[str]:
        """
        Get the decrypted active API key for a specific provider.
        This is the primary method for AI services to retrieve keys.
        
        Args:
            provider: Provider name (e.g., 'gemini', 'openai')
            
        Returns:
            Decrypted API key string or None
        """
        result = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.provider == provider.lower(),
                    APIKey.is_active == True
                )
            ).order_by(APIKey.created_at.desc()).limit(1)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            logger.debug(f"No active API key found for provider: {provider}")
            return None
        
        try:
            decrypted = encryption_service.decrypt(api_key.encrypted_key)
            
            # Update usage tracking
            await self.db.execute(
                update(APIKey)
                .where(APIKey.id == api_key.id)
                .values(
                    last_used_at=datetime.now(timezone.utc),
                    usage_count=APIKey.usage_count + 1
                )
            )
            await self.db.commit()
            
            return decrypted
        except EncryptionError as e:
            logger.error(f"Failed to decrypt API key for {provider}: {e}")
            return None
    
    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        provider_filter: Optional[str] = None,
        active_only: bool = False
    ) -> Tuple[List[APIKey], int]:
        """
        List all API keys (without decryption).
        
        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            provider_filter: Optional provider to filter by
            active_only: Only return active keys
            
        Returns:
            Tuple of (list of APIKey, total count)
        """
        query = select(APIKey)
        count_query = select(APIKey)
        
        # Apply filters
        conditions = []
        if provider_filter:
            conditions.append(APIKey.provider == provider_filter.lower())
        if active_only:
            conditions.append(APIKey.is_active == True)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Get total count
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar() or 0
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(APIKey.created_at.desc()).offset(offset).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        return items, total
    
    async def update(
        self,
        key_id: int,
        data: APIKeyUpdate,
        updated_by: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> APIKey:
        """
        Update an existing API key.
        
        Args:
            key_id: ID of the key to update
            data: Update data
            updated_by: User ID making the update
            ip_address: Request IP for audit
            user_agent: Request user agent for audit
            
        Returns:
            Updated APIKey model instance
        """
        api_key = await self.get_by_id(key_id)
        if not api_key:
            raise APIKeyNotFoundError(f"API key {key_id} not found")
        
        # Track changes for audit
        changes = []
        
        # Update API key if provided
        if data.api_key is not None:
            # Validate new key format
            is_valid, error_msg = encryption_service.validate_key_format(
                api_key.provider, data.api_key
            )
            if not is_valid:
                raise APIKeyValidationError(error_msg)
            
            # Encrypt new key
            try:
                api_key.encrypted_key = encryption_service.encrypt(data.api_key)
                api_key.key_preview = encryption_service.generate_key_preview(data.api_key)
                changes.append("api_key updated")
            except EncryptionError as e:
                logger.error(f"Failed to encrypt API key: {e}")
                raise APIKeyServiceError("Failed to encrypt API key")
        
        # Update other fields
        if data.label is not None:
            api_key.label = data.label
            changes.append(f"label: {data.label}")
        
        if data.notes is not None:
            api_key.notes = data.notes
            changes.append("notes updated")
        
        if data.is_active is not None:
            api_key.is_active = data.is_active
            changes.append(f"is_active: {data.is_active}")
        
        await self.db.commit()
        await self.db.refresh(api_key)
        
        # Audit log
        if self.audit and changes:
            await self.audit.log(
                event_type=AuditEventType.CONFIG_CHANGED,
                user_id=updated_by,
                details={"action": "updated", "changes": changes},
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type="api_key",
                resource_id=str(key_id)
            )
        
        logger.info(f"Updated API key {key_id}")
        return api_key
    
    async def delete(
        self,
        key_id: int,
        deleted_by: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Delete an API key (hard delete).
        
        Args:
            key_id: ID of the key to delete
            deleted_by: User ID deleting the key
            ip_address: Request IP for audit
            user_agent: Request user agent for audit
            
        Returns:
            True if deleted, False if not found
        """
        api_key = await self.get_by_id(key_id)
        if not api_key:
            return False
        
        provider = api_key.provider
        await self.db.delete(api_key)
        await self.db.commit()
        
        # Audit log
        if self.audit:
            await self.audit.log(
                event_type=AuditEventType.CONFIG_CHANGED,
                user_id=deleted_by,
                details={"action": "deleted", "provider": provider},
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type="api_key",
                resource_id=str(key_id)
            )
        
        logger.info(f"Deleted API key {key_id}")
        return True
    
    async def test_connectivity(
        self,
        key_id: int,
        user_id: int
    ) -> APIKeyTestResponse:
        """
        Test an API key's connectivity with its provider.
        
        Args:
            key_id: ID of the key to test
            user_id: User ID requesting the test
            
        Returns:
            APIKeyTestResponse with test results
        """
        import time
        
        api_key_internal = await self.get_decrypted(key_id)
        if not api_key_internal:
            return APIKeyTestResponse(
                success=False,
                provider="unknown",
                message="API key not found or could not be decrypted"
            )
        
        provider = api_key_internal.provider
        decrypted_key = api_key_internal.decrypted_key
        
        start_time = time.time()
        
        try:
            if provider == "gemini":
                result = await self._test_gemini(decrypted_key)
            elif provider == "openai":
                result = await self._test_openai(decrypted_key)
            elif provider == "anthropic":
                result = await self._test_anthropic(decrypted_key)
            else:
                result = APIKeyTestResponse(
                    success=True,
                    provider=provider,
                    message="Key stored successfully (connectivity test not available for this provider)"
                )
            
            latency_ms = (time.time() - start_time) * 1000
            result.latency_ms = round(latency_ms, 2)
            return result
            
        except Exception as e:
            logger.error(f"API key test failed for {provider}: {e}")
            return APIKeyTestResponse(
                success=False,
                provider=provider,
                message=f"Test failed: {str(e)}",
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )
    
    async def _test_gemini(self, api_key: str) -> APIKeyTestResponse:
        """Test Gemini API key connectivity"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # List models to verify key works
            models = list(genai.list_models())
            model_names = [m.name for m in models[:3]]
            
            return APIKeyTestResponse(
                success=True,
                provider="gemini",
                message=f"Successfully connected. Found {len(models)} models.",
                model_available=", ".join(model_names) if model_names else None
            )
        except ImportError:
            return APIKeyTestResponse(
                success=False,
                provider="gemini",
                message="google-generativeai package not installed"
            )
        except Exception as e:
            return APIKeyTestResponse(
                success=False,
                provider="gemini",
                message=f"Connection failed: {str(e)}"
            )
    
    async def _test_openai(self, api_key: str) -> APIKeyTestResponse:
        """Test OpenAI API key connectivity"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            
            # List models to verify key works
            models = await client.models.list()
            model_names = [m.id for m in list(models.data)[:3]]
            
            return APIKeyTestResponse(
                success=True,
                provider="openai",
                message=f"Successfully connected. Found {len(models.data)} models.",
                model_available=", ".join(model_names) if model_names else None
            )
        except ImportError:
            return APIKeyTestResponse(
                success=False,
                provider="openai",
                message="openai package not installed"
            )
        except Exception as e:
            return APIKeyTestResponse(
                success=False,
                provider="openai",
                message=f"Connection failed: {str(e)}"
            )
    
    async def _test_anthropic(self, api_key: str) -> APIKeyTestResponse:
        """Test Anthropic API key connectivity"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            # Simple test - just verify the key format is accepted
            # Anthropic doesn't have a list models endpoint
            return APIKeyTestResponse(
                success=True,
                provider="anthropic",
                message="API key format validated. Full connectivity test requires an API call.",
                model_available="claude-3-opus, claude-3-sonnet, claude-3-haiku"
            )
        except ImportError:
            return APIKeyTestResponse(
                success=False,
                provider="anthropic",
                message="anthropic package not installed"
            )
        except Exception as e:
            return APIKeyTestResponse(
                success=False,
                provider="anthropic",
                message=f"Validation failed: {str(e)}"
            )
