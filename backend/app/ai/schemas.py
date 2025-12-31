"""
AI Schemas

Pydantic schemas for AI features API endpoints.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field


# ============================================
# SUGGESTION SCHEMAS
# ============================================

class SuggestionRequest(BaseModel):
    """Request for time entry suggestions."""
    partial_description: Optional[str] = Field(
        None,
        max_length=500,
        description="Partial text user is typing"
    )
    use_ai: bool = Field(
        True,
        description="Whether to use AI enhancement"
    )
    limit: int = Field(
        5,
        ge=1,
        le=10,
        description="Max suggestions to return"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "partial_description": "working on dashboard",
                "use_ai": True,
                "limit": 5
            }
        }
    }


class Suggestion(BaseModel):
    """Single suggestion result."""
    project_id: int
    project_name: str
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    suggested_description: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    reason: str
    source: str  # "pattern", "ai", "recent"


class SuggestionResponse(BaseModel):
    """Response with suggestions."""
    suggestions: List[Suggestion]
    enabled: bool
    total_found: int = 0
    context: Optional[Dict[str, str]] = None
    rate_limited: bool = False
    error: Optional[str] = None
    message: Optional[str] = None


class SuggestionFeedback(BaseModel):
    """Feedback on suggestion quality."""
    suggestion_project_id: int
    accepted: bool
    actual_project_id: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "suggestion_project_id": 1,
                "accepted": True,
                "actual_project_id": None
            }
        }
    }


# ============================================
# ANOMALY SCHEMAS
# ============================================

class AnomalyScanRequest(BaseModel):
    """Request for anomaly scan."""
    user_id: Optional[int] = Field(
        None,
        description="Specific user to scan (admin only)"
    )
    team_id: Optional[int] = Field(
        None,
        description="Team to scan (admin only)"
    )
    period_days: int = Field(
        7,
        ge=1,
        le=90,
        description="Days to look back"
    )
    scan_all: bool = Field(
        False,
        description="Scan all users (admin only)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "period_days": 7,
                "scan_all": False
            }
        }
    }


class AnomalyDetails(BaseModel):
    """Details about a detected anomaly."""
    type: str  # extended_day, consecutive_long_days, etc.
    severity: str  # info, warning, critical
    user_id: int
    user_name: str
    description: str
    detected_at: datetime
    details: Dict[str, Any]
    recommendation: Optional[str] = None


class AnomalyScanResponse(BaseModel):
    """Response from anomaly scan."""
    anomalies: List[AnomalyDetails]
    enabled: bool
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, int]] = None
    scan_date: str
    period_days: int
    error: Optional[str] = None
    message: Optional[str] = None


class AnomalyDismissRequest(BaseModel):
    """Request to dismiss/acknowledge anomaly."""
    user_id: int
    anomaly_type: str
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for dismissal"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "anomaly_type": "extended_day",
                "reason": "Project deadline - approved overtime"
            }
        }
    }


# ============================================
# AI STATUS SCHEMAS
# ============================================

class AIProviderStatus(BaseModel):
    """Status of AI providers."""
    gemini: bool
    openai: bool
    any: bool


class AIStatusResponse(BaseModel):
    """AI system status response."""
    providers: AIProviderStatus
    features: Dict[str, bool]
    cache_stats: Optional[Dict[str, int]] = None


# ============================================
# FORECASTING SCHEMAS (Phase 2)
# ============================================

class PayrollForecastRequest(BaseModel):
    """Request for payroll forecast."""
    period_type: str = Field(
        "bi_weekly",
        description="Payroll period type: weekly, bi_weekly, semi_monthly, monthly"
    )
    periods_ahead: int = Field(
        1,
        ge=1,
        le=6,
        description="Number of periods to forecast"
    )
    include_overtime: bool = Field(
        True,
        description="Include overtime projections"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "period_type": "bi_weekly",
                "periods_ahead": 2,
                "include_overtime": True
            }
        }
    }


class PayrollForecastItem(BaseModel):
    """Single payroll forecast result."""
    period_start: str
    period_end: str
    predicted_total: float
    predicted_regular: float
    predicted_overtime: float
    confidence: float
    lower_bound: float
    upper_bound: float
    trend: str
    factors: List[Dict[str, Any]]


class PayrollForecastResponse(BaseModel):
    """Response with payroll forecasts."""
    forecasts: List[PayrollForecastItem]
    enabled: bool
    period_type: Optional[str] = None
    historical_periods_used: Optional[int] = None
    generated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class OvertimeRiskRequest(BaseModel):
    """Request for overtime risk assessment."""
    days_ahead: int = Field(
        7,
        ge=1,
        le=30,
        description="Days to project ahead"
    )
    team_id: Optional[int] = Field(
        None,
        description="Optional team filter"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "days_ahead": 7,
                "team_id": None
            }
        }
    }


class OvertimeRiskItem(BaseModel):
    """Single overtime risk assessment."""
    user_id: int
    user_name: str
    current_hours: float
    projected_hours: float
    overtime_threshold: float
    risk_level: str
    projected_overtime: float
    estimated_cost: float
    recommendation: str


class OvertimeRiskResponse(BaseModel):
    """Response with overtime risk assessments."""
    risks: List[OvertimeRiskItem]
    enabled: bool
    period: Optional[str] = None
    users_assessed: Optional[int] = None
    users_at_risk: Optional[int] = None
    generated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class ProjectBudgetRequest(BaseModel):
    """Request for project budget forecast."""
    project_id: Optional[int] = Field(
        None,
        description="Specific project ID"
    )
    team_id: Optional[int] = Field(
        None,
        description="Team projects filter"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "project_id": 1,
                "team_id": None
            }
        }
    }


class ProjectBudgetItem(BaseModel):
    """Single project budget forecast."""
    project_id: int
    project_name: str
    budget_total: float
    spent_to_date: float
    projected_total: float
    burn_rate_daily: float
    days_remaining: int
    projected_completion: Optional[str] = None
    risk_level: str
    budget_utilization_pct: float
    recommendations: List[str]


class ProjectBudgetResponse(BaseModel):
    """Response with project budget forecasts."""
    forecasts: List[ProjectBudgetItem]
    enabled: bool
    projects_analyzed: Optional[int] = None
    generated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class CashFlowWeek(BaseModel):
    """Single week cash flow projection."""
    week_start: str
    week_end: str
    is_payroll_week: bool
    projected_payroll: float
    cumulative: float


class CashFlowResponse(BaseModel):
    """Response with cash flow forecast."""
    forecast: List[CashFlowWeek]
    enabled: bool
    average_payroll: Optional[float] = None
    generated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================
# NLP SCHEMAS (Phase 3)
# ============================================

class NLPParseRequest(BaseModel):
    """Request to parse natural language time entry."""
    text: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language input to parse"
    )
    timezone: str = Field(
        "UTC",
        description="User's timezone for date interpretation"
    )
    use_ai: bool = Field(
        True,
        description="Whether to use AI for enhanced parsing"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Log 2 hours on Project Alpha yesterday",
                "timezone": "America/New_York",
                "use_ai": True
            }
        }
    }


class ParsedEntity(BaseModel):
    """A parsed entity from NLP."""
    type: str  # project, task, duration, date
    value: Any
    original: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    id: Optional[int] = None


class NLPParseResult(BaseModel):
    """Parsed time entry result."""
    original_text: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    duration_display: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    confidence_level: str  # high, medium, low
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    parsed_entities: List[ParsedEntity] = []
    suggestions: List[Dict[str, Any]] = []


class NLPParseResponse(BaseModel):
    """Response from NLP parsing."""
    success: bool
    enabled: bool = True
    result: Optional[NLPParseResult] = None
    error: Optional[str] = None
    message: Optional[str] = None


class NLPConfirmRequest(BaseModel):
    """Request to confirm and create time entry from NLP parse."""
    parsed_result: Dict[str, Any] = Field(
        ...,
        description="The parsed result to confirm"
    )
    modifications: Optional[Dict[str, Any]] = Field(
        None,
        description="User modifications to the parsed result"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "parsed_result": {
                    "project_id": 1,
                    "duration_seconds": 7200,
                    "description": "Client meeting"
                },
                "modifications": {
                    "task_id": 5
                }
            }
        }
    }


class NLPConfirmResponse(BaseModel):
    """Response from confirming NLP entry."""
    success: bool
    time_entry_id: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


# ============================================
# REPORT SUMMARY SCHEMAS (Phase 3)
# ============================================

class WeeklySummaryRequest(BaseModel):
    """Request for weekly summary."""
    team_id: Optional[int] = Field(
        None,
        description="Team to generate summary for"
    )
    include_ai: bool = Field(
        True,
        description="Whether to use AI for summary generation"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_id": 1,
                "include_ai": True
            }
        }
    }


class Insight(BaseModel):
    """A single insight from analysis."""
    type: str  # productivity, project_health, team_performance, etc.
    title: str
    description: str
    severity: str  # info, warning, critical
    metric_value: Optional[float] = None
    metric_label: Optional[str] = None
    action_items: List[str] = []
    related_entity: Optional[Dict[str, Any]] = None


class ProjectDailyHours(BaseModel):
    """Daily hours entry."""
    date: str
    hours: float


class TopProject(BaseModel):
    """Top project by hours."""
    name: str
    hours: float


class SummaryMetrics(BaseModel):
    """Metrics for summary."""
    week_start: str
    week_end: str
    user_count: int = 1
    total_hours: float
    last_week_hours: float
    hours_change_pct: float
    projects_count: int
    top_projects: List[TopProject]
    daily_hours: List[ProjectDailyHours]
    avg_daily_hours: float
    max_daily_hours: float
    min_daily_hours: float


class AttentionItem(BaseModel):
    """Item needing attention."""
    title: str
    description: str
    severity: str
    actions: List[str] = []


class WeeklySummary(BaseModel):
    """Weekly summary result."""
    period_start: str
    period_end: str
    summary_text: str
    highlights: List[str]
    attention_needed: List[AttentionItem]
    recommendations: List[str]
    insights: List[Insight]
    metrics: SummaryMetrics
    generated_at: str


class WeeklySummaryResponse(BaseModel):
    """Response with weekly summary."""
    success: bool
    enabled: bool = True
    summary: Optional[WeeklySummary] = None
    error: Optional[str] = None
    message: Optional[str] = None


class ProjectHealthRequest(BaseModel):
    """Request for project health assessment."""
    project_id: int = Field(
        ...,
        description="Project ID to assess"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "project_id": 1
            }
        }
    }


class ProjectHealthMetrics(BaseModel):
    """Project health metrics."""
    total_hours: float
    this_week_hours: float
    last_week_hours: float
    activity_trend: str  # increasing, decreasing, stable, new
    total_tasks: int
    completed_tasks: int
    task_completion_rate: float
    contributor_count: int


class ProjectHealthResponse(BaseModel):
    """Response with project health."""
    success: bool
    enabled: bool = True
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    health_score: Optional[int] = None  # 0-100
    health_status: Optional[str] = None  # healthy, moderate, at_risk, critical
    metrics: Optional[ProjectHealthMetrics] = None
    insights: List[Insight] = []
    generated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class UserInsightsRequest(BaseModel):
    """Request for user insights."""
    target_user_id: Optional[int] = Field(
        None,
        description="User to analyze (defaults to requester)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "target_user_id": None
            }
        }
    }


class UserMetrics(BaseModel):
    """User metrics."""
    user_name: Optional[str] = None
    expected_hours: float = 40
    total_hours_30d: float
    avg_daily_hours: float
    active_projects: int
    productivity_trend: str  # improving, declining, stable, new


class UserInsightsResponse(BaseModel):
    """Response with user insights."""
    success: bool
    enabled: bool = True
    user_id: Optional[int] = None
    metrics: Optional[UserMetrics] = None
    insights: List[Insight] = []
    generated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================
# PHASE 4: ML ANOMALY DETECTION SCHEMAS
# ============================================

class MLAnomalyScanRequest(BaseModel):
    """Request for ML-based anomaly scan."""
    user_id: Optional[int] = Field(
        None,
        description="Specific user to scan (admin only)"
    )
    period_days: int = Field(
        7,
        ge=1,
        le=90,
        description="Days to analyze"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": None,
                "period_days": 7
            }
        }
    }


class MLAnomalyItem(BaseModel):
    """ML-detected anomaly."""
    type: str
    severity: str
    user_id: int
    user_name: str
    description: str
    confidence: float
    detected_at: str
    details: Dict[str, Any] = {}
    recommendation: Optional[str] = None


class MLAnomalyScanResponse(BaseModel):
    """Response with ML anomalies."""
    success: bool
    enabled: bool = True
    anomalies: List[MLAnomalyItem] = []
    total_found: int = 0
    ml_enabled: bool = False
    scanned_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class BurnoutAssessmentRequest(BaseModel):
    """Request for burnout risk assessment."""
    user_id: Optional[int] = Field(
        None,
        description="User to assess (defaults to self)"
    )
    period_days: int = Field(
        30,
        ge=7,
        le=90,
        description="Days to analyze"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": None,
                "period_days": 30
            }
        }
    }


class BurnoutFactor(BaseModel):
    """Individual burnout risk factor."""
    name: str
    score: float
    max_score: float
    detail: str


class BurnoutAssessmentResponse(BaseModel):
    """Response with burnout assessment."""
    success: bool
    enabled: bool = True
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    risk_level: Optional[str] = None  # low, moderate, high, critical
    risk_score: Optional[float] = None  # 0-100
    factors: List[BurnoutFactor] = []
    recommendations: List[str] = []
    trend: Optional[str] = None  # improving, stable, worsening
    assessed_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class TeamBurnoutScanRequest(BaseModel):
    """Request for team burnout scan."""
    team_id: Optional[int] = Field(
        None,
        description="Team to scan (None = all users)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_id": None
            }
        }
    }


class TeamBurnoutResponse(BaseModel):
    """Response with team burnout scan."""
    success: bool
    enabled: bool = True
    assessments: List[Dict[str, Any]] = []
    risk_distribution: Dict[str, int] = {}
    total_users: int = 0
    high_risk_count: int = 0
    assessed_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class UserBaselineRequest(BaseModel):
    """Request for user baseline calculation."""
    user_id: Optional[int] = Field(
        None,
        description="User to calculate baseline for"
    )
    period_days: int = Field(
        30,
        ge=7,
        le=180,
        description="Days to include in baseline"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": None,
                "period_days": 30
            }
        }
    }


class UserBaselineResponse(BaseModel):
    """Response with user baseline."""
    success: bool
    enabled: bool = True
    user_id: Optional[int] = None
    avg_daily_hours: Optional[float] = None
    std_daily_hours: Optional[float] = None
    avg_weekly_hours: Optional[float] = None
    typical_start_hour: Optional[float] = None
    typical_end_hour: Optional[float] = None
    preferred_days: List[int] = []
    avg_entry_duration: Optional[float] = None
    entries_per_day: Optional[float] = None
    data_points: int = 0
    calculated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================
# PHASE 4: TASK DURATION ESTIMATION SCHEMAS
# ============================================

class TaskEstimationRequest(BaseModel):
    """Request for task duration estimation."""
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Task description"
    )
    project_id: Optional[int] = Field(
        None,
        description="Project context"
    )
    scheduled_hour: Optional[int] = Field(
        None,
        ge=0,
        le=23,
        description="Planned start hour (0-23)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "Implement user authentication feature",
                "project_id": 1,
                "scheduled_hour": 10
            }
        }
    }


class SimilarTask(BaseModel):
    """Similar historical task."""
    description: str
    duration_minutes: float
    similarity: float


class EstimationFactor(BaseModel):
    """Factor affecting estimation."""
    name: str
    description: str
    impact: Optional[str] = None  # faster, slower, neutral


class TaskEstimationResponse(BaseModel):
    """Response with duration estimate."""
    success: bool
    enabled: bool = True
    estimated_minutes: Optional[float] = None
    estimated_hours: Optional[float] = None
    confidence: Optional[float] = None
    range_min_minutes: Optional[float] = None
    range_max_minutes: Optional[float] = None
    method: Optional[str] = None  # ml, historical, fallback
    factors: List[EstimationFactor] = []
    similar_tasks: List[SimilarTask] = []
    recommendation: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class BatchTaskEstimationRequest(BaseModel):
    """Request for batch task estimation."""
    tasks: List[TaskEstimationRequest] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Tasks to estimate"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tasks": [
                    {"description": "Write unit tests", "project_id": 1},
                    {"description": "Code review", "project_id": 1}
                ]
            }
        }
    }


class BatchEstimationItem(BaseModel):
    """Single estimation in batch result."""
    description: str
    estimated_minutes: float
    estimated_hours: float
    confidence: float


class BatchTaskEstimationResponse(BaseModel):
    """Response with batch estimates."""
    success: bool
    enabled: bool = True
    estimates: List[BatchEstimationItem] = []
    total_minutes: float = 0
    total_hours: float = 0
    error: Optional[str] = None
    message: Optional[str] = None


class ModelTrainingRequest(BaseModel):
    """Request to train estimation model."""
    period_days: int = Field(
        180,
        ge=30,
        le=365,
        description="Days of data to use"
    )
    team_id: Optional[int] = Field(
        None,
        description="Team to train on"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "period_days": 180,
                "team_id": None
            }
        }
    }


class ModelTrainingResponse(BaseModel):
    """Response with training results."""
    success: bool
    enabled: bool = True
    samples_used: Optional[int] = None
    mae_minutes: Optional[float] = None
    rmse_minutes: Optional[float] = None
    trained_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class UserPerformanceProfileResponse(BaseModel):
    """Response with user performance profile."""
    success: bool
    enabled: bool = True
    user_id: Optional[int] = None
    avg_task_duration: Optional[float] = None
    task_completion_rate: Optional[float] = None
    speed_factor: Optional[float] = None
    preferred_task_types: List[str] = []
    peak_performance_hours: List[int] = []
    task_count: int = 0
    calculated_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class EstimationStatsResponse(BaseModel):
    """Response with estimation service stats."""
    success: bool
    model_trained: bool = False
    ml_available: bool = False
    cached_profiles: int = 0
    min_samples_required: int = 50
    tfidf_features: int = 0


# ============================================
# PHASE 5: SEMANTIC SEARCH SCHEMAS
# ============================================

class SemanticSearchRequest(BaseModel):
    """Request for semantic task search."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query"
    )
    team_id: Optional[int] = Field(
        None,
        description="Limit to team's projects"
    )
    project_id: Optional[int] = Field(
        None,
        description="Limit to specific project"
    )
    limit: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum results"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "frontend dashboard",
                "team_id": 1,
                "limit": 10
            }
        }
    }


class SimilarTaskResult(BaseModel):
    """A similar task from search results."""
    task_id: Optional[int] = None
    task_name: str
    project_id: Optional[int] = None
    project_name: str
    description: str
    similarity_score: float
    avg_duration_minutes: Optional[float] = None
    times_used: int
    last_used: Optional[datetime] = None


class SemanticSearchResponse(BaseModel):
    """Response with semantic search results."""
    success: bool
    enabled: bool = True
    query: str
    results: List[SimilarTaskResult] = []
    search_time_ms: float
    method: str  # "embedding", "keyword", "hybrid"
    error: Optional[str] = None
    message: Optional[str] = None


class TimeSuggestionsRequest(BaseModel):
    """Request for time-based task suggestions."""
    hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour of day (0-23)"
    )
    day_of_week: int = Field(
        ...,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday)"
    )
    team_id: Optional[int] = None
    limit: int = Field(5, ge=1, le=20)


# ============================================
# PHASE 5: TEAM ANALYTICS SCHEMAS
# ============================================

class TeamAnalyticsRequest(BaseModel):
    """Request for team analytics report."""
    team_id: int = Field(
        ...,
        description="Team ID to analyze"
    )
    period_days: int = Field(
        30,
        ge=7,
        le=365,
        description="Analysis period in days"
    )
    include_ai_insights: bool = Field(
        True,
        description="Include AI-generated insights"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_id": 1,
                "period_days": 30,
                "include_ai_insights": True
            }
        }
    }


class TeamMemberMetricsSchema(BaseModel):
    """Individual team member metrics."""
    user_id: int
    user_name: str
    total_hours: float
    avg_daily_hours: float
    productive_hours_ratio: float
    projects_worked: int
    tasks_completed: int
    consistency_score: float
    overtime_hours: float
    weekend_hours: float


class TeamVelocitySchema(BaseModel):
    """Team velocity for a period."""
    period_start: date
    period_end: date
    total_hours: float
    hours_per_member: float
    tasks_completed: int
    projects_active: int
    avg_task_duration_hours: float
    velocity_trend: str
    change_percent: float


class CollaborationEdgeSchema(BaseModel):
    """Collaboration between team members."""
    user1_id: int
    user1_name: str
    user2_id: int
    user2_name: str
    shared_projects: int
    interaction_score: float


class TeamAnalyticsResponse(BaseModel):
    """Complete team analytics report response."""
    success: bool
    enabled: bool = True
    team_id: int
    team_name: str
    period_days: int
    total_members: int
    active_members: int
    total_hours: float
    avg_hours_per_member: float
    total_projects: int
    total_tasks: int
    member_metrics: List[TeamMemberMetricsSchema] = []
    velocity_history: List[TeamVelocitySchema] = []
    current_velocity_trend: str
    collaboration_edges: List[CollaborationEdgeSchema] = []
    collaboration_density: float
    workload_gini: float
    top_contributors: List[Dict[str, Any]] = []
    underutilized_members: List[Dict[str, Any]] = []
    ai_insights: List[str] = []
    recommendations: List[str] = []
    generated_at: datetime
    error: Optional[str] = None
    message: Optional[str] = None


class TeamComparisonRequest(BaseModel):
    """Request to compare multiple teams."""
    team_ids: List[int] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Teams to compare"
    )
    period_days: int = Field(
        30,
        ge=7,
        le=365
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "team_ids": [1, 2, 3],
                "period_days": 30
            }
        }
    }


class TeamComparisonResponse(BaseModel):
    """Response with team comparison data."""
    success: bool
    enabled: bool = True
    period_days: int
    teams_compared: int
    comparisons: List[Dict[str, Any]] = []
    generated_at: str
    error: Optional[str] = None
    message: Optional[str] = None
