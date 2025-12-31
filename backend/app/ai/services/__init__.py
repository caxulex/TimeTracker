"""
AI Services Module

Contains all AI-powered service implementations:
- AIClient: Unified AI provider client (Gemini/OpenAI)
- SuggestionService: Time entry suggestions
- AnomalyService: Anomaly detection
- ForecastingService: Payroll and budget forecasting (Phase 2)
- NLPService: Natural language processing (Phase 3)
- ReportingService: AI report summaries (Phase 3)
"""

from app.ai.services.ai_client import (
    AIClient,
    get_ai_client,
    reset_ai_client,
    AIProviderError,
    RateLimitError
)
from app.ai.services.suggestion_service import (
    SuggestionService,
    SuggestionResult,
    get_suggestion_service
)
from app.ai.services.anomaly_service import (
    AnomalyService,
    Anomaly,
    AnomalyType,
    AnomalySeverity,
    get_anomaly_service
)
from app.ai.services.forecasting_service import (
    ForecastingService,
    PayrollForecast,
    OvertimeRisk,
    ProjectBudgetForecast,
    ForecastType,
    RiskLevel,
    get_forecasting_service
)
from app.ai.services.nlp_service import (
    NLPService,
    NLPParseResult,
    ParseConfidence,
    get_nlp_service
)
from app.ai.services.reporting_service import (
    AIReportingService,
    ReportSummary,
    Insight,
    InsightType,
    InsightSeverity,
    get_reporting_service
)

__all__ = [
    # AI Client
    "AIClient",
    "get_ai_client",
    "reset_ai_client",
    "AIProviderError",
    "RateLimitError",
    # Suggestion Service
    "SuggestionService",
    "SuggestionResult",
    "get_suggestion_service",
    # Anomaly Service
    "AnomalyService",
    "Anomaly",
    "AnomalyType",
    "AnomalySeverity",
    "get_anomaly_service",
    # Forecasting Service (Phase 2)
    "ForecastingService",
    "PayrollForecast",
    "OvertimeRisk",
    "ProjectBudgetForecast",
    "ForecastType",
    "RiskLevel",
    "get_forecasting_service",
    # NLP Service (Phase 3)
    "NLPService",
    "NLPParseResult",
    "ParseConfidence",
    "get_nlp_service",
    # Reporting Service (Phase 3)
    "AIReportingService",
    "ReportSummary",
    "Insight",
    "InsightType",
    "InsightSeverity",
    "get_reporting_service"
]
