from unittest.mock import AsyncMock

import pytest

from app.ai.services.ai_client import (
    AIClient,
    AIProviderError,
    BaseAIProvider,
    RateLimitError,
)


class _SuccessfulProvider(BaseAIProvider):
    def __init__(self, key_id: int):
        super().__init__(key_id)

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 1000):
        return {
            "success": True,
            "provider": "gemini",
            "data": {"answer": "ok"},
        }

    async def is_available(self) -> bool:
        return True


class _RateLimitedProvider(BaseAIProvider):
    def __init__(self, key_id: int):
        super().__init__(key_id)

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 1000):
        raise RateLimitError("429 Too Many Requests", "gemini", 429)

    async def is_available(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_ai_client_records_success_on_successful_call() -> None:
    client = AIClient()
    client._initialized = True
    client._primary_provider = _SuccessfulProvider(key_id=101)
    client._fallback_provider = None
    client._api_key_service = AsyncMock()

    result = await client.generate(
        system_prompt="system",
        user_prompt="user",
        feature="suggestions",
    )

    assert result["success"] is True
    assert result["feature"] == "suggestions"
    client._api_key_service.record_success.assert_awaited_once_with(101)
    client._api_key_service.record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_ai_client_records_failure_on_429() -> None:
    client = AIClient()
    client._initialized = True
    client._primary_provider = _RateLimitedProvider(key_id=202)
    client._fallback_provider = None
    client._api_key_service = AsyncMock()

    with pytest.raises(AIProviderError):
        await client.generate(system_prompt="system", user_prompt="user")

    client._api_key_service.record_success.assert_not_called()
    client._api_key_service.record_failure.assert_awaited_once_with(
        202,
        "429 Too Many Requests",
        429,
    )
