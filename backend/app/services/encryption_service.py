"""
Encryption Service for API Key Management
SEC-020: Secure encryption of API keys at rest using AES-256-GCM

This service handles:
- Encryption of API keys before database storage
- Decryption of API keys when needed by AI services
- Key preview generation for safe display in UI
"""

import os
import base64
import secrets
import logging
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from app.config import settings

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass


class EncryptionService:
    """
    AES-256-GCM encryption service for secure API key storage.
    
    Encryption format: base64(salt || nonce || ciphertext || tag)
    - Salt: 16 bytes (used for key derivation)
    - Nonce: 12 bytes (required by GCM)
    - Ciphertext: variable length
    - Tag: 16 bytes (authentication tag, appended by AESGCM)
    """
    
    SALT_LENGTH = 16
    NONCE_LENGTH = 12
    KEY_LENGTH = 32  # 256 bits
    ITERATIONS = 100_000  # PBKDF2 iterations
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption service with master key.
        
        Args:
            master_key: Base64-encoded master encryption key.
                       Falls back to settings.API_KEY_ENCRYPTION_KEY if not provided.
        """
        self._master_key = master_key or settings.API_KEY_ENCRYPTION_KEY
        
        if not self._master_key:
            logger.warning(
                "API_KEY_ENCRYPTION_KEY not set. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
    
    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive an encryption key from the master key using PBKDF2.
        
        This adds an extra layer of security by using a unique salt
        for each encrypted value.
        """
        if not self._master_key:
            raise EncryptionError("Encryption key not configured")
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.ITERATIONS,
            backend=default_backend()
        )
        
        # Use the master key bytes for derivation
        master_bytes = self._master_key.encode('utf-8')
        return kdf.derive(master_bytes)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string (API key).
        
        Args:
            plaintext: The API key to encrypt
            
        Returns:
            Base64-encoded encrypted data (salt + nonce + ciphertext + tag)
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty value")
        
        try:
            # Generate random salt and nonce
            salt = secrets.token_bytes(self.SALT_LENGTH)
            nonce = secrets.token_bytes(self.NONCE_LENGTH)
            
            # Derive encryption key from master key + salt
            key = self._derive_key(salt)
            
            # Encrypt using AES-256-GCM
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            
            # Combine: salt || nonce || ciphertext (includes tag)
            encrypted_data = salt + nonce + ciphertext
            
            # Return base64-encoded string for storage
            return base64.b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted API key.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext API key
            
        Raises:
            EncryptionError: If decryption fails
        """
        if not encrypted_data:
            raise EncryptionError("Cannot decrypt empty value")
        
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # Extract components
            salt = data[:self.SALT_LENGTH]
            nonce = data[self.SALT_LENGTH:self.SALT_LENGTH + self.NONCE_LENGTH]
            ciphertext = data[self.SALT_LENGTH + self.NONCE_LENGTH:]
            
            # Derive key from master key + salt
            key = self._derive_key(salt)
            
            # Decrypt using AES-256-GCM
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise EncryptionError(f"Failed to decrypt data: {str(e)}")
    
    @staticmethod
    def generate_key_preview(api_key: str, visible_chars: int = 4) -> str:
        """
        Generate a safe preview of an API key for display.
        
        Args:
            api_key: The full API key
            visible_chars: Number of characters to show at the end
            
        Returns:
            Preview string like "...xxxx"
        """
        if not api_key:
            return ""
        
        if len(api_key) <= visible_chars:
            return "*" * len(api_key)
        
        return f"...{api_key[-visible_chars:]}"
    
    @staticmethod
    def mask_key(api_key: str, show_start: int = 4, show_end: int = 4) -> str:
        """
        Mask an API key showing only start and end characters.
        
        Args:
            api_key: The full API key
            show_start: Characters to show at start
            show_end: Characters to show at end
            
        Returns:
            Masked string like "sk-p...xxxx"
        """
        if not api_key:
            return ""
        
        if len(api_key) <= (show_start + show_end):
            return "*" * len(api_key)
        
        return f"{api_key[:show_start]}...{api_key[-show_end:]}"
    
    def is_configured(self) -> bool:
        """Check if the encryption service is properly configured."""
        return bool(self._master_key and len(self._master_key) >= 32)
    
    def validate_key_format(self, provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
        """
        Validate API key format for known providers.
        
        Args:
            provider: The AI provider name
            api_key: The API key to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not api_key or len(api_key) < 10:
            return False, "API key is too short"
        
        # Provider-specific validation
        validations = {
            "openai": lambda k: k.startswith(("sk-", "sk-proj-")),
            "gemini": lambda k: len(k) >= 20,  # Gemini keys are typically 39 chars
            "anthropic": lambda k: k.startswith("sk-ant-"),
            "azure_openai": lambda k: len(k) >= 20,
        }
        
        validator = validations.get(provider.lower())
        if validator and not validator(api_key):
            return False, f"Invalid {provider} API key format"
        
        return True, None


# Global encryption service instance
encryption_service = EncryptionService()
