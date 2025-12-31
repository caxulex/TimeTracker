"""
AI Client Wrapper

Unified client for AI providers (Gemini and OpenAI).
Handles provider switching, fallback, error handling, and response parsing.
"""

import json
import asyncio
from typing import Optional, Dict, Any, List, Literal, Union
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from app.ai.config import ai_settings
from app.services.api_key_service import APIKeyService

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Base exception for AI provider errors."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class RateLimitError(AIProviderError):
    """Rate limit exceeded error."""
    pass


class InvalidResponseError(AIProviderError):
    """Invalid response from AI provider."""
    pass


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate AI response."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
        self._model_name = ai_settings.GEMINI_MODEL

    async def _get_client(self):
        """Get or create Gemini client (lazy initialization)."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self._model_name)
            except ImportError:
                raise AIProviderError(
                    "google-generativeai package not installed",
                    "gemini"
                )
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate response using Gemini."""
        try:
            client = await self._get_client()
            
            # Combine prompts for Gemini
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Run generation in thread pool (Gemini client is sync)
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens
                    }
                )
            )
            
            # Extract text response
            if hasattr(response, 'text'):
                text = response.text
            elif hasattr(response, 'parts') and response.parts:
                text = response.parts[0].text
            else:
                raise InvalidResponseError("Empty response from Gemini", "gemini")
            
            # Try to parse as JSON
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Return raw text if not JSON
                parsed = {"raw_text": text}
            
            return {
                "success": True,
                "provider": "gemini",
                "model": self._model_name,
                "data": parsed,
                "raw_response": text,
                "usage": {
                    "prompt_tokens": len(full_prompt.split()) * 1.3,  # Estimate
                    "completion_tokens": len(text.split()) * 1.3  # Estimate
                }
            }

        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str:
                raise RateLimitError(str(e), "gemini")
            raise AIProviderError(str(e), "gemini")

    async def is_available(self) -> bool:
        """Check if Gemini is available."""
        try:
            await self._get_client()
            return bool(self.api_key)
        except Exception:
            return False


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
        self._model_name = ai_settings.OPENAI_MODEL

    async def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise AIProviderError(
                    "openai package not installed",
                    "openai"
                )
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate response using OpenAI."""
        try:
            client = await self._get_client()
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=ai_settings.OPENAI_TIMEOUT
            )
            
            text = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"raw_text": text}
            
            return {
                "success": True,
                "provider": "openai",
                "model": self._model_name,
                "data": parsed,
                "raw_response": text,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0
                }
            }

        except asyncio.TimeoutError:
            raise AIProviderError("Request timed out", "openai", 408)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise RateLimitError(str(e), "openai", 429)
            raise AIProviderError(str(e), "openai")

    async def is_available(self) -> bool:
        """Check if OpenAI is available."""
        try:
            await self._get_client()
            return bool(self.api_key)
        except Exception:
            return False


class AIClient:
    """
    Unified AI client with provider fallback and error handling.
    
    Usage:
        client = AIClient()
        await client.initialize(db)
        response = await client.generate(
            system_prompt="You are a helpful assistant",
            user_prompt="Hello!",
            feature="ai_suggestions"  # For usage tracking
        )
    """

    def __init__(self):
        self._primary_provider: Optional[BaseAIProvider] = None
        self._fallback_provider: Optional[BaseAIProvider] = None
        self._initialized = False

    async def initialize(self, db) -> bool:
        """Initialize AI clients with API keys from database."""
        try:
            api_key_service = APIKeyService(db)
            
            # Get Gemini key (primary)
            gemini_key = await api_key_service.get_active_key_for_provider("gemini")
            if gemini_key:
                self._primary_provider = GeminiProvider(gemini_key)
                logger.info("Gemini provider initialized")

            # Get OpenAI key (fallback)
            openai_key = await api_key_service.get_active_key_for_provider("openai")
            if openai_key:
                self._fallback_provider = OpenAIProvider(openai_key)
                logger.info("OpenAI fallback provider initialized")

            self._initialized = self._primary_provider is not None or self._fallback_provider is not None
            
            if not self._initialized:
                logger.warning("No AI providers configured - AI features will be unavailable")
            
            return self._initialized

        except Exception as e:
            logger.error(f"Failed to initialize AI clients: {e}")
            return False

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prefer_provider: Optional[Literal["gemini", "openai"]] = None,
        feature: Optional[str] = None  # For logging/tracking
    ) -> Dict[str, Any]:
        """
        Generate AI response with automatic fallback.
        
        Args:
            system_prompt: System/instruction prompt
            user_prompt: User query/context
            temperature: Override default temperature
            max_tokens: Override default max tokens
            prefer_provider: Prefer specific provider if available
            feature: Feature name for usage tracking
            
        Returns:
            Dict with response data, provider info, and usage stats
        """
        if not self._initialized:
            raise AIProviderError("AI client not initialized", "none")

        temp = temperature or ai_settings.GEMINI_TEMPERATURE
        tokens = max_tokens or ai_settings.GEMINI_MAX_TOKENS

        # Determine provider order
        providers = self._get_provider_order(prefer_provider)
        
        errors = []
        for provider in providers:
            if provider is None:
                continue
            
            try:
                logger.info(f"Attempting AI generation with {provider.__class__.__name__}")
                response = await provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temp,
                    max_tokens=tokens
                )
                
                # Add feature tracking
                if feature:
                    response["feature"] = feature
                
                return response
                
            except RateLimitError as e:
                logger.warning(f"Rate limit hit on {e.provider}, trying fallback")
                errors.append(str(e))
                continue
            except AIProviderError as e:
                logger.warning(f"Provider {e.provider} failed: {e}")
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(f"Unexpected error with provider: {e}")
                errors.append(str(e))
                continue

        # All providers failed
        raise AIProviderError(
            f"All AI providers failed: {'; '.join(errors)}",
            "all"
        )

    def _get_provider_order(
        self,
        prefer: Optional[Literal["gemini", "openai"]] = None
    ) -> List[Optional[BaseAIProvider]]:
        """Get provider order based on preference."""
        if prefer == "openai" and self._fallback_provider:
            return [self._fallback_provider, self._primary_provider]
        return [self._primary_provider, self._fallback_provider]

    async def check_availability(self) -> Dict[str, bool]:
        """Check which providers are available."""
        result = {
            "gemini": False,
            "openai": False,
            "any": False
        }
        
        if self._primary_provider:
            result["gemini"] = await self._primary_provider.is_available()
        
        if self._fallback_provider:
            result["openai"] = await self._fallback_provider.is_available()
        
        result["any"] = result["gemini"] or result["openai"]
        return result

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized


# Singleton instance for dependency injection
_ai_client_instance: Optional[AIClient] = None


async def get_ai_client(db) -> AIClient:
    """Get or create AI client instance."""
    global _ai_client_instance
    
    if _ai_client_instance is None:
        _ai_client_instance = AIClient()
        await _ai_client_instance.initialize(db)
    
    return _ai_client_instance


async def reset_ai_client():
    """Reset the AI client instance (for testing or key updates)."""
    global _ai_client_instance
    _ai_client_instance = None
