"""
AI Utilities Module

Contains utility functions for AI services:
- Prompt templates
- Cache management
- Token counting
- Cost calculation
"""

from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.ai.utils.prompt_templates import PromptTemplates, prompt_templates

__all__ = [
    "PromptTemplates",
    "prompt_templates",
    "AICacheManager",
    "get_cache_manager",
]
