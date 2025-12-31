"""
AI Module for Time Tracker Application

This module provides AI-powered features including:
- Time Entry Suggestions (Phase 1)
- Anomaly Detection (Phase 1)
- Payroll Forecasting (Phase 2)
- Natural Language Entry (Phase 3)
- AI Report Summaries (Phase 3)
- Task Duration Estimation (Phase 4)

All AI features are controlled by the AI Feature Toggle System,
ensuring users have full control over which features they use.
"""

from app.ai.config import ai_settings
from app.ai.router import router as ai_router

__all__ = [
    "ai_settings",
    "ai_router"
]
