"""
AI Configuration Settings

Centralized configuration for all AI features including:
- API provider settings (Gemini, OpenAI, Anthropic)
- Rate limiting
- Caching
- Feature thresholds
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class AISettings(BaseSettings):
    """AI-specific configuration settings."""
    
    model_config = {
        "env_prefix": "AI_",
        "extra": "ignore",
        "case_sensitive": True,
    }

    # ============================================
    # GEMINI SETTINGS (Primary Provider)
    # ============================================
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model to use for AI features"
    )
    GEMINI_TIMEOUT: int = Field(
        default=30,
        description="Timeout in seconds for Gemini API calls"
    )
    GEMINI_MAX_TOKENS: int = Field(
        default=1024,
        description="Maximum tokens for Gemini responses"
    )
    GEMINI_TEMPERATURE: float = Field(
        default=0.7,
        description="Temperature for Gemini responses (0.0-1.0)"
    )

    # ============================================
    # OPENAI SETTINGS (Fallback Provider)
    # ============================================
    OPENAI_MODEL: str = Field(
        default="gpt-3.5-turbo",
        description="OpenAI model to use for AI features"
    )
    OPENAI_TIMEOUT: int = Field(
        default=30,
        description="Timeout in seconds for OpenAI API calls"
    )
    OPENAI_MAX_TOKENS: int = Field(
        default=1024,
        description="Maximum tokens for OpenAI responses"
    )
    OPENAI_TEMPERATURE: float = Field(
        default=0.7,
        description="Temperature for OpenAI responses (0.0-1.0)"
    )

    # ============================================
    # RATE LIMITING
    # ============================================
    REQUESTS_PER_MINUTE: int = Field(
        default=30,
        description="Maximum AI requests per minute per user"
    )
    REQUESTS_PER_HOUR: int = Field(
        default=500,
        description="Maximum AI requests per hour per user"
    )
    GLOBAL_REQUESTS_PER_MINUTE: int = Field(
        default=300,
        description="Maximum AI requests per minute globally"
    )

    # ============================================
    # CACHING
    # ============================================
    CACHE_TTL_SUGGESTIONS: int = Field(
        default=300,
        description="TTL in seconds for suggestion cache (5 min)"
    )
    CACHE_TTL_ANOMALIES: int = Field(
        default=3600,
        description="TTL in seconds for anomaly cache (1 hour)"
    )
    CACHE_TTL_USER_CONTEXT: int = Field(
        default=900,
        description="TTL in seconds for user context cache (15 min)"
    )
    CACHE_TTL_FORECASTS: int = Field(
        default=86400,
        description="TTL in seconds for forecast cache (24 hours)"
    )

    # ============================================
    # SUGGESTION SETTINGS
    # ============================================
    SUGGESTION_CONFIDENCE_THRESHOLD: float = Field(
        default=0.6,
        description="Minimum confidence score for suggestions (0.0-1.0)"
    )
    SUGGESTION_MAX_RESULTS: int = Field(
        default=5,
        description="Maximum number of suggestions to return"
    )
    SUGGESTION_LOOKBACK_DAYS: int = Field(
        default=30,
        description="Days of history to analyze for suggestions"
    )
    SUGGESTION_MIN_ENTRIES: int = Field(
        default=10,
        description="Minimum entries required for pattern analysis"
    )

    # ============================================
    # ANOMALY DETECTION SETTINGS
    # ============================================
    ANOMALY_EXTENDED_DAY_HOURS: float = Field(
        default=12.0,
        description="Hours threshold for extended work day anomaly"
    )
    ANOMALY_CONSECUTIVE_LONG_DAYS: int = Field(
        default=5,
        description="Consecutive days threshold for burnout warning"
    )
    ANOMALY_LONG_DAY_HOURS: float = Field(
        default=10.0,
        description="Hours per day for consecutive long days check"
    )
    ANOMALY_WEEKEND_HOURS: float = Field(
        default=4.0,
        description="Weekend hours threshold for unusual activity"
    )
    ANOMALY_MISSING_HOURS_MIN: float = Field(
        default=2.0,
        description="Minimum logged hours before missing time warning"
    )
    ANOMALY_EXPECTED_HOURS_DEFAULT: float = Field(
        default=8.0,
        description="Default expected hours per day"
    )
    ANOMALY_SCAN_DAYS: int = Field(
        default=7,
        description="Days to scan for anomaly detection"
    )

    # ============================================
    # NLP SETTINGS (Phase 3)
    # ============================================
    NLP_CONFIDENCE_THRESHOLD: float = Field(
        default=0.7,
        description="Minimum confidence score to auto-confirm NLP parse"
    )
    NLP_USE_AI_ENHANCEMENT: bool = Field(
        default=True,
        description="Whether to use AI for enhanced NLP parsing"
    )
    NLP_MAX_SUGGESTIONS: int = Field(
        default=5,
        description="Maximum project suggestions for low-confidence parses"
    )

    # ============================================
    # REPORTING SETTINGS (Phase 3)
    # ============================================
    REPORT_CACHE_TTL: int = Field(
        default=3600,
        description="TTL in seconds for report cache (1 hour)"
    )
    REPORT_USE_AI_SUMMARY: bool = Field(
        default=True,
        description="Whether to use AI for generating report summaries"
    )
    REPORT_MAX_INSIGHTS: int = Field(
        default=10,
        description="Maximum insights to include in reports"
    )

    # ============================================
    # COST TRACKING
    # ============================================
    GEMINI_COST_PER_1K_INPUT: float = Field(
        default=0.000075,
        description="Cost per 1K input tokens for Gemini Flash"
    )
    GEMINI_COST_PER_1K_OUTPUT: float = Field(
        default=0.0003,
        description="Cost per 1K output tokens for Gemini Flash"
    )
    OPENAI_COST_PER_1K_INPUT: float = Field(
        default=0.0005,
        description="Cost per 1K input tokens for GPT-3.5"
    )
    OPENAI_COST_PER_1K_OUTPUT: float = Field(
        default=0.0015,
        description="Cost per 1K output tokens for GPT-3.5"
    )

    # ============================================
    # FEATURE FLAGS (Database-controlled overrides)
    # ============================================
    # These are defaults; actual status comes from ai_feature_settings table
    DEFAULT_SUGGESTIONS_ENABLED: bool = True
    DEFAULT_ANOMALY_DETECTION_ENABLED: bool = True
    DEFAULT_FORECASTING_ENABLED: bool = False
    DEFAULT_NLP_ENABLED: bool = False
    DEFAULT_REPORT_SUMMARIES_ENABLED: bool = False
    DEFAULT_TASK_ESTIMATION_ENABLED: bool = False


# Create global AI settings instance
ai_settings = AISettings()
