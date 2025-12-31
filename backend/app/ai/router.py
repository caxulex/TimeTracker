"""
AI Router

API endpoints for AI features:
- Time entry suggestions
- Anomaly detection
- Payroll forecasting
- Budget predictions
- AI status and health
- ML anomaly detection (Phase 4)
- Task duration estimation (Phase 4)
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User
from app.ai.services import (
    get_suggestion_service,
    get_anomaly_service,
    get_ai_client,
    AIProviderError
)
from app.ai.services.forecasting_service import get_forecasting_service
from app.ai.services.nlp_service import get_nlp_service
from app.ai.services.reporting_service import get_reporting_service
from app.ai.services.ml_anomaly_service import get_ml_anomaly_service
from app.ai.services.task_estimation_service import get_task_estimation_service
from app.ai.utils import get_cache_manager
from app.ai.schemas import (
    SuggestionRequest,
    SuggestionResponse,
    SuggestionFeedback,
    AnomalyScanRequest,
    AnomalyScanResponse,
    AnomalyDismissRequest,
    AIStatusResponse,
    AIProviderStatus,
    # Forecasting schemas
    PayrollForecastRequest,
    PayrollForecastResponse,
    OvertimeRiskRequest,
    OvertimeRiskResponse,
    ProjectBudgetRequest,
    ProjectBudgetResponse,
    CashFlowResponse,
    # NLP schemas (Phase 3)
    NLPParseRequest,
    NLPParseResponse,
    NLPConfirmRequest,
    NLPConfirmResponse,
    # Report schemas (Phase 3)
    WeeklySummaryRequest,
    WeeklySummaryResponse,
    ProjectHealthRequest,
    ProjectHealthResponse,
    UserInsightsRequest,
    UserInsightsResponse,
    # Phase 4: ML Anomaly schemas
    MLAnomalyScanRequest,
    MLAnomalyScanResponse,
    BurnoutAssessmentRequest,
    BurnoutAssessmentResponse,
    TeamBurnoutScanRequest,
    TeamBurnoutResponse,
    UserBaselineRequest,
    UserBaselineResponse,
    # Phase 4: Task Estimation schemas
    TaskEstimationRequest,
    TaskEstimationResponse,
    BatchTaskEstimationRequest,
    BatchTaskEstimationResponse,
    ModelTrainingRequest,
    ModelTrainingResponse,
    UserPerformanceProfileResponse,
    EstimationStatsResponse,
    # Phase 5: Semantic Search schemas
    SemanticSearchRequest,
    SemanticSearchResponse,
    SimilarTaskResult,
    TimeSuggestionsRequest,
    # Phase 5: Team Analytics schemas
    TeamAnalyticsRequest,
    TeamAnalyticsResponse,
    TeamMemberMetricsSchema,
    TeamVelocitySchema,
    CollaborationEdgeSchema,
    TeamComparisonRequest,
    TeamComparisonResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai",
    tags=["AI Features"]
)


# ============================================
# SUGGESTIONS ENDPOINTS
# ============================================

@router.post(
    "/suggestions/time-entry",
    response_model=SuggestionResponse,
    summary="Get time entry suggestions",
    description="""
    Get intelligent suggestions for time entry based on:
    - User's historical patterns
    - Current time of day/week
    - Partial description typed
    - AI enhancement (optional)
    
    Returns up to 5 suggestions sorted by confidence.
    """
)
async def get_time_entry_suggestions(
    request: SuggestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get AI-powered time entry suggestions."""
    try:
        service = await get_suggestion_service(db)
        result = await service.get_suggestions(
            user_id=current_user.id,
            partial_description=request.partial_description,
            limit=request.limit,
            use_ai=request.use_ai
        )
        return result
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggestions: {str(e)}"
        )


@router.post(
    "/suggestions/feedback",
    summary="Submit suggestion feedback",
    description="Record whether a suggestion was accepted or rejected."
)
async def submit_suggestion_feedback(
    feedback: SuggestionFeedback,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Record feedback on suggestion quality."""
    try:
        service = await get_suggestion_service(db)
        success = await service.record_feedback(
            user_id=current_user.id,
            suggestion_project_id=feedback.suggestion_project_id,
            accepted=feedback.accepted,
            actual_project_id=feedback.actual_project_id
        )
        return {"success": success}
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback"
        )


# ============================================
# ANOMALY ENDPOINTS
# ============================================

@router.post(
    "/anomalies/scan",
    response_model=AnomalyScanResponse,
    summary="Scan for anomalies",
    description="""
    Scan for anomalies in time tracking data.
    
    - Regular users: Can only scan their own data
    - Admins/Managers: Can scan specific users, teams, or all users
    
    Detects:
    - Extended work days (>12 hours)
    - Consecutive long days
    - Weekend work spikes
    - Missing time entries
    - Potential duplicates
    - Burnout risk indicators
    """
)
async def scan_anomalies(
    request: AnomalyScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Scan for time tracking anomalies."""
    try:
        service = await get_anomaly_service(db)
        
        # Permission checks
        is_admin = current_user.role in ["admin", "superadmin"]
        is_manager = current_user.role == "manager"
        
        if request.scan_all:
            if not is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can scan all users"
                )
            result = await service.scan_all_users(
                period_days=request.period_days,
                team_id=request.team_id
            )
        elif request.user_id and request.user_id != current_user.id:
            if not (is_admin or is_manager):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot scan other users"
                )
            result = await service.scan_user(
                user_id=request.user_id,
                period_days=request.period_days
            )
        else:
            # Scan own data
            result = await service.scan_user(
                user_id=current_user.id,
                period_days=request.period_days
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan anomalies: {str(e)}"
        )


@router.get(
    "/anomalies",
    response_model=AnomalyScanResponse,
    summary="Get recent anomalies",
    description="Get cached anomaly scan results for current user."
)
async def get_anomalies(
    period_days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent anomalies for current user."""
    try:
        service = await get_anomaly_service(db)
        result = await service.scan_user(
            user_id=current_user.id,
            period_days=period_days
        )
        return result
    except Exception as e:
        logger.error(f"Error getting anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get anomalies"
        )


@router.get(
    "/anomalies/all",
    response_model=AnomalyScanResponse,
    summary="Get all user anomalies (Admin)",
    description="Get anomalies for all users. Admin only."
)
async def get_all_anomalies(
    period_days: int = 7,
    team_id: Optional[int] = None,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Get anomalies for all users (admin/manager only)."""
    try:
        service = await get_anomaly_service(db)
        result = await service.scan_all_users(
            period_days=period_days,
            team_id=team_id
        )
        return result
    except Exception as e:
        logger.error(f"Error getting all anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get anomalies"
        )


@router.post(
    "/anomalies/dismiss",
    summary="Dismiss anomaly",
    description="Dismiss/acknowledge an anomaly. Admin only."
)
async def dismiss_anomaly(
    request: AnomalyDismissRequest,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Dismiss/acknowledge an anomaly."""
    try:
        service = await get_anomaly_service(db)
        success = await service.dismiss_anomaly(
            user_id=request.user_id,
            anomaly_type=request.anomaly_type,
            dismissed_by=current_user.id,
            reason=request.reason
        )
        return {"success": success}
    except Exception as e:
        logger.error(f"Error dismissing anomaly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss anomaly"
        )


# ============================================
# STATUS ENDPOINTS
# ============================================

@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Get AI status",
    description="Get status of AI providers and features."
)
async def get_ai_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get AI system status."""
    try:
        from app.services.ai_feature_service import AIFeatureManager
        
        # Check AI providers
        client = await get_ai_client(db)
        provider_status = await client.check_availability()
        
        # Get feature status
        fm = AIFeatureManager(db)
        features = {}
        for feature_name in ["ai_suggestions", "ai_anomaly_alerts"]:
            features[feature_name] = await fm.is_enabled(feature_name, current_user.id)
        
        # Get cache stats (admin only)
        cache_stats = None
        if current_user.role in ["admin", "superadmin"]:
            cache = await get_cache_manager()
            cache_stats = await cache.get_cache_stats()
        
        return {
            "providers": provider_status,
            "features": features,
            "cache_stats": cache_stats
        }
    except Exception as e:
        logger.error(f"Error getting AI status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get AI status"
        )


@router.post(
    "/status/reset-client",
    summary="Reset AI client (Admin)",
    description="Reset AI client to reload API keys. Admin only."
)
async def reset_ai_client_endpoint(
    current_user: User = Depends(require_role(["admin", "superadmin"])),
    db: AsyncSession = Depends(get_db)
):
    """Reset AI client to reload API keys."""
    try:
        from app.ai.services import reset_ai_client
        await reset_ai_client()
        
        # Reinitialize
        client = await get_ai_client(db)
        provider_status = await client.check_availability()
        
        return {
            "success": True,
            "providers": provider_status
        }
    except Exception as e:
        logger.error(f"Error resetting AI client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset AI client"
        )


# ============================================
# FORECASTING ENDPOINTS (Phase 2)
# ============================================

@router.post(
    "/forecast/payroll",
    response_model=PayrollForecastResponse,
    summary="Forecast payroll costs",
    description="""
    Generate payroll forecasts for upcoming periods.
    
    Uses historical payroll data to predict:
    - Total payroll cost
    - Regular hours cost
    - Overtime cost
    - Confidence intervals
    - Trend analysis
    
    Requires at least 3 completed payroll periods for accurate forecasts.
    """
)
async def forecast_payroll(
    request: PayrollForecastRequest,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Get payroll forecast."""
    try:
        service = await get_forecasting_service(db)
        result = await service.forecast_payroll(
            user_id=current_user.id,
            period_type=request.period_type,
            periods_ahead=request.periods_ahead,
            include_overtime=request.include_overtime
        )
        return result
    except Exception as e:
        logger.error(f"Error forecasting payroll: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to forecast payroll: {str(e)}"
        )


@router.post(
    "/forecast/overtime-risk",
    response_model=OvertimeRiskResponse,
    summary="Assess overtime risk",
    description="""
    Identify employees at risk of exceeding overtime thresholds.
    
    Analyzes:
    - Current week hours
    - Historical average daily hours
    - Projected end-of-week hours
    - Estimated overtime cost
    
    Returns risk levels: low, medium, high, critical
    """
)
async def assess_overtime_risk(
    request: OvertimeRiskRequest,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Assess overtime risk for employees."""
    try:
        service = await get_forecasting_service(db)
        result = await service.assess_overtime_risk(
            user_id=current_user.id,
            days_ahead=request.days_ahead,
            team_id=request.team_id
        )
        return result
    except Exception as e:
        logger.error(f"Error assessing overtime risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assess overtime risk: {str(e)}"
        )


@router.post(
    "/forecast/project-budget",
    response_model=ProjectBudgetResponse,
    summary="Forecast project budget",
    description="""
    Forecast budget consumption for projects.
    
    Analyzes:
    - Current spending vs budget
    - Burn rate trends
    - Projected completion date
    - Budget risk assessment
    
    Returns recommendations for budget management.
    """
)
async def forecast_project_budget(
    request: ProjectBudgetRequest,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Get project budget forecast."""
    try:
        service = await get_forecasting_service(db)
        result = await service.forecast_project_budget(
            user_id=current_user.id,
            project_id=request.project_id,
            team_id=request.team_id
        )
        return result
    except Exception as e:
        logger.error(f"Error forecasting project budget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to forecast project budget: {str(e)}"
        )


@router.get(
    "/forecast/cash-flow",
    response_model=CashFlowResponse,
    summary="Forecast cash flow",
    description="""
    Project weekly cash flow for payroll obligations.
    
    Shows:
    - Weekly payroll projections
    - Payroll week indicators
    - Cumulative outflow
    """
)
async def forecast_cash_flow(
    weeks_ahead: int = 4,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Get cash flow forecast."""
    try:
        service = await get_forecasting_service(db)
        result = await service.forecast_cash_flow(
            user_id=current_user.id,
            weeks_ahead=min(weeks_ahead, 12)  # Max 12 weeks
        )
        return result
    except Exception as e:
        logger.error(f"Error forecasting cash flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to forecast cash flow: {str(e)}"
        )


# ============================================
# NLP ENDPOINTS (Phase 3)
# ============================================

@router.post(
    "/nlp/parse",
    response_model=NLPParseResponse,
    summary="Parse natural language time entry",
    description="""
    Parse natural language input into time entry fields.
    
    Supports inputs like:
    - "Log 2 hours on Project Alpha yesterday"
    - "3h client meeting for marketing project"
    - "worked 45 min on bug fixes this morning"
    
    Returns parsed entities with confidence scores.
    If confidence is low, suggestions are provided.
    """
)
async def parse_time_entry(
    request: NLPParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Parse natural language into time entry."""
    try:
        service = await get_nlp_service(db)
        result = await service.parse_time_entry(
            text=request.text,
            user_id=current_user.id,
            timezone=request.timezone,
            use_ai=request.use_ai
        )
        return result
    except Exception as e:
        logger.error(f"Error parsing NLP entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse entry: {str(e)}"
        )


@router.post(
    "/nlp/confirm",
    response_model=NLPConfirmResponse,
    summary="Confirm and create time entry from NLP",
    description="""
    Confirm a parsed NLP result and create the time entry.
    
    Optionally include modifications to override parsed values.
    """
)
async def confirm_nlp_entry(
    request: NLPConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Confirm and create time entry from NLP parse."""
    try:
        service = await get_nlp_service(db)
        result = await service.confirm_entry(
            user_id=current_user.id,
            parsed_result=request.parsed_result,
            modifications=request.modifications
        )
        return result
    except Exception as e:
        logger.error(f"Error confirming NLP entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create entry: {str(e)}"
        )


# ============================================
# REPORT SUMMARY ENDPOINTS (Phase 3)
# ============================================

@router.post(
    "/reports/weekly-summary",
    response_model=WeeklySummaryResponse,
    summary="Generate weekly summary",
    description="""
    Generate an AI-powered weekly productivity summary.
    
    Includes:
    - Total hours logged
    - Comparison vs last week
    - Top projects by time
    - Key insights and recommendations
    - Attention items (if any)
    """
)
async def generate_weekly_summary(
    request: WeeklySummaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate weekly summary report."""
    try:
        service = await get_reporting_service(db)
        result = await service.generate_weekly_summary(
            user_id=current_user.id,
            team_id=request.team_id,
            include_ai=request.include_ai
        )
        return result
    except Exception as e:
        logger.error(f"Error generating weekly summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.post(
    "/reports/project-health",
    response_model=ProjectHealthResponse,
    summary="Assess project health",
    description="""
    Generate a health assessment for a project.
    
    Analyzes:
    - Activity trends
    - Task completion rate
    - Team involvement
    - Budget utilization
    
    Returns health score (0-100) and actionable insights.
    """
)
async def assess_project_health(
    request: ProjectHealthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assess project health."""
    try:
        service = await get_reporting_service(db)
        result = await service.generate_project_health(
            user_id=current_user.id,
            project_id=request.project_id
        )
        return result
    except Exception as e:
        logger.error(f"Error assessing project health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assess project: {str(e)}"
        )


@router.post(
    "/reports/user-insights",
    response_model=UserInsightsResponse,
    summary="Generate user insights",
    description="""
    Generate personalized insights for a user.
    
    Analyzes:
    - Work patterns
    - Productivity trends
    - Project distribution
    - Work-life balance indicators
    
    Admins can view insights for other users.
    """
)
async def generate_user_insights(
    request: UserInsightsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate user-specific insights."""
    try:
        # Permission check for viewing other users
        target_id = request.target_user_id or current_user.id
        if target_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view other users' insights"
            )
        
        service = await get_reporting_service(db)
        result = await service.generate_user_insights(
            user_id=current_user.id,
            target_user_id=target_id
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating user insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {str(e)}"
        )


# ============================================
# ML ANOMALY DETECTION ENDPOINTS (Phase 4)
# ============================================

@router.post(
    "/ml/anomalies/scan",
    response_model=MLAnomalyScanResponse,
    summary="Scan for ML-based anomalies",
    description="""
    Scan for anomalies using machine learning.
    
    Uses Isolation Forest for statistical outlier detection
    and behavioral baselines for personalized analysis.
    
    Detects:
    - Statistical outliers in work patterns
    - Pattern deviations from baseline
    - Behavioral changes over time
    - Workload imbalances
    - Time pattern anomalies
    """
)
async def scan_ml_anomalies(
    request: MLAnomalyScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Scan for ML-detected anomalies."""
    try:
        service = await get_ml_anomaly_service(db)
        
        # Permission check
        target_id = request.user_id or current_user.id
        if target_id != current_user.id and current_user.role not in ["admin", "superadmin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot scan other users"
            )
        
        anomalies = await service.detect_ml_anomalies(
            user_id=target_id,
            period_days=request.period_days
        )
        
        return MLAnomalyScanResponse(
            success=True,
            anomalies=[a.to_dict() for a in anomalies],  # type: ignore
            total_found=len(anomalies),
            ml_enabled=True,
            scanned_at=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning ML anomalies: {e}")
        return MLAnomalyScanResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/ml/burnout/assess",
    response_model=BurnoutAssessmentResponse,
    summary="Assess burnout risk",
    description="""
    Assess burnout risk for a user.
    
    Analyzes factors including:
    - Overtime frequency
    - Weekend work patterns
    - Late work hours
    - Schedule inconsistency
    - Consecutive work days
    
    Returns risk level, score, and recommendations.
    """
)
async def assess_burnout_risk(
    request: BurnoutAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assess burnout risk for user."""
    try:
        service = await get_ml_anomaly_service(db)
        
        # Permission check
        target_id = request.user_id or current_user.id
        if target_id != current_user.id and current_user.role not in ["admin", "superadmin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assess other users' burnout risk"
            )
        
        assessment = await service.assess_burnout_risk(
            user_id=target_id,
            period_days=request.period_days
        )
        
        return BurnoutAssessmentResponse(
            success=True,
            user_id=assessment.user_id,
            user_name=assessment.user_name,
            risk_level=assessment.risk_level.value,
            risk_score=assessment.risk_score,
            factors=assessment.factors,  # type: ignore
            recommendations=assessment.recommendations,
            trend=assessment.trend,
            assessed_at=assessment.assessed_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assessing burnout: {e}")
        return BurnoutAssessmentResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/ml/burnout/team-scan",
    response_model=TeamBurnoutResponse,
    summary="Scan team for burnout risk",
    description="""
    Scan all team members for burnout risk.
    
    Returns risk distribution and identifies high-risk employees.
    Admin/manager access required.
    """
)
async def scan_team_burnout(
    request: TeamBurnoutScanRequest,
    current_user: User = Depends(require_role(["admin", "superadmin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Scan team for burnout risk."""
    try:
        service = await get_ml_anomaly_service(db)
        result = await service.scan_team_burnout(team_id=request.team_id)
        
        return TeamBurnoutResponse(
            success=True,
            assessments=result["assessments"],
            risk_distribution=result["risk_distribution"],
            total_users=result["total_users"],
            high_risk_count=result["high_risk_count"],
            assessed_at=result["assessed_at"]
        )
    except Exception as e:
        logger.error(f"Error scanning team burnout: {e}")
        return TeamBurnoutResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/ml/baseline/calculate",
    response_model=UserBaselineResponse,
    summary="Calculate user baseline",
    description="""
    Calculate behavioral baseline for a user.
    
    Analyzes historical data to establish:
    - Average and typical work hours
    - Preferred schedule patterns
    - Entry duration patterns
    - Project distribution
    """
)
async def calculate_user_baseline(
    request: UserBaselineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Calculate user behavioral baseline."""
    try:
        service = await get_ml_anomaly_service(db)
        
        # Permission check
        target_id = request.user_id or current_user.id
        if target_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot calculate baseline for other users"
            )
        
        baseline = await service.calculate_user_baseline(
            user_id=target_id,
            period_days=request.period_days
        )
        
        return UserBaselineResponse(
            success=True,
            user_id=baseline.user_id,
            avg_daily_hours=baseline.avg_daily_hours,
            std_daily_hours=baseline.std_daily_hours,
            avg_weekly_hours=baseline.avg_weekly_hours,
            typical_start_hour=baseline.typical_start_hour,
            typical_end_hour=baseline.typical_end_hour,
            preferred_days=baseline.preferred_days,
            avg_entry_duration=baseline.avg_entry_duration,
            entries_per_day=baseline.entries_per_day,
            data_points=baseline.data_points,
            calculated_at=baseline.calculated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating baseline: {e}")
        return UserBaselineResponse(
            success=False,
            error=str(e)
        )


# ============================================
# TASK DURATION ESTIMATION ENDPOINTS (Phase 4)
# ============================================

@router.post(
    "/estimation/task",
    response_model=TaskEstimationResponse,
    summary="Estimate task duration",
    description="""
    Estimate duration for a task using ML.
    
    Uses XGBoost regression with features:
    - Task description (TF-IDF)
    - Project context
    - User historical performance
    - Time of day patterns
    
    Returns estimate with confidence range.
    """
)
async def estimate_task_duration(
    request: TaskEstimationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Estimate task duration."""
    try:
        service = await get_task_estimation_service(db)
        estimate = await service.estimate_duration(
            description=request.description,
            project_id=request.project_id,
            user_id=current_user.id,
            scheduled_hour=request.scheduled_hour
        )
        
        return TaskEstimationResponse(
            success=True,
            estimated_minutes=estimate.estimated_minutes,
            estimated_hours=estimate.estimated_minutes / 60,
            confidence=estimate.confidence,
            range_min_minutes=estimate.range_min,
            range_max_minutes=estimate.range_max,
            method=estimate.method,
            factors=estimate.factors,  # type: ignore
            similar_tasks=estimate.similar_tasks,  # type: ignore
            recommendation=estimate.recommendation
        )
    except Exception as e:
        logger.error(f"Error estimating duration: {e}")
        return TaskEstimationResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/estimation/batch",
    response_model=BatchTaskEstimationResponse,
    summary="Estimate duration for multiple tasks",
    description="""
    Estimate durations for multiple tasks at once.
    
    Useful for sprint planning and workload assessment.
    """
)
async def estimate_batch_tasks(
    request: BatchTaskEstimationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Estimate durations for multiple tasks."""
    try:
        service = await get_task_estimation_service(db)
        
        tasks = [
            {
                "description": t.description,
                "project_id": t.project_id,
                "scheduled_hour": t.scheduled_hour
            }
            for t in request.tasks
        ]
        
        estimates = await service.estimate_batch(
            tasks=tasks,
            user_id=current_user.id
        )
        
        items = []
        total_minutes = 0
        for task, estimate in zip(request.tasks, estimates):
            items.append({
                "description": task.description,
                "estimated_minutes": estimate.estimated_minutes,
                "estimated_hours": estimate.estimated_minutes / 60,
                "confidence": estimate.confidence
            })
            total_minutes += estimate.estimated_minutes
        
        return BatchTaskEstimationResponse(
            success=True,
            estimates=items,
            total_minutes=total_minutes,
            total_hours=total_minutes / 60
        )
    except Exception as e:
        logger.error(f"Error in batch estimation: {e}")
        return BatchTaskEstimationResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/estimation/train",
    response_model=ModelTrainingResponse,
    summary="Train estimation model",
    description="""
    Train the XGBoost duration estimation model.
    
    Requires admin access and sufficient historical data.
    Uses completed tasks for training.
    """
)
async def train_estimation_model(
    request: ModelTrainingRequest,
    current_user: User = Depends(require_role(["admin", "superadmin"])),
    db: AsyncSession = Depends(get_db)
):
    """Train the estimation model."""
    try:
        service = await get_task_estimation_service(db)
        result = await service.train_model(
            team_id=request.team_id,
            period_days=request.period_days
        )
        
        if result.get("success"):
            return ModelTrainingResponse(
                success=True,
                samples_used=result.get("samples_used"),
                mae_minutes=result.get("mae_minutes"),
                rmse_minutes=result.get("rmse_minutes"),
                trained_at=result.get("trained_at")
            )
        else:
            return ModelTrainingResponse(
                success=False,
                error=result.get("error")
            )
    except Exception as e:
        logger.error(f"Error training model: {e}")
        return ModelTrainingResponse(
            success=False,
            error=str(e)
        )


@router.get(
    "/estimation/profile",
    response_model=UserPerformanceProfileResponse,
    summary="Get user performance profile",
    description="""
    Get the user's performance profile for estimation.
    
    Shows historical task completion patterns
    and performance characteristics.
    """
)
async def get_user_performance_profile(
    user_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user performance profile."""
    try:
        service = await get_task_estimation_service(db)
        
        # Permission check
        target_id = user_id or current_user.id
        if target_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view other users' profiles"
            )
        
        profile = await service.get_user_profile(target_id)
        
        return UserPerformanceProfileResponse(
            success=True,
            user_id=profile.user_id,
            avg_task_duration=profile.avg_task_duration,
            task_completion_rate=profile.task_completion_rate,
            speed_factor=profile.speed_factor,
            preferred_task_types=profile.preferred_task_types,
            peak_performance_hours=profile.peak_performance_hours,
            task_count=profile.task_count,
            calculated_at=profile.calculated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return UserPerformanceProfileResponse(
            success=False,
            error=str(e)
        )


@router.get(
    "/estimation/stats",
    response_model=EstimationStatsResponse,
    summary="Get estimation service statistics",
    description="Get status of the task estimation service."
)
async def get_estimation_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get estimation service stats."""
    try:
        service = await get_task_estimation_service(db)
        stats = await service.get_estimation_stats()
        
        return EstimationStatsResponse(
            success=True,
            model_trained=stats.get("model_trained", False),
            ml_available=stats.get("ml_available", False),
            cached_profiles=stats.get("cached_profiles", 0),
            min_samples_required=stats.get("min_samples_required", 50),
            tfidf_features=stats.get("tfidf_features", 0)
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return EstimationStatsResponse(
            success=False,
            model_trained=False,
            ml_available=False
        )


# ============================================
# PHASE 5: SEMANTIC SEARCH ENDPOINTS
# ============================================

@router.post(
    "/search/similar-tasks",
    response_model=SemanticSearchResponse,
    summary="Search for similar tasks",
    description="""
    Search for tasks semantically similar to the query.
    
    Uses hybrid search combining:
    - Keyword matching for exact terms
    - Semantic similarity for meaning
    - User history for relevance ranking
    
    Requires 'ai_semantic_search' feature to be enabled.
    """
)
async def search_similar_tasks(
    request: SemanticSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Search for similar tasks."""
    from app.ai.services.semantic_search_service import get_semantic_search_service
    from app.ai.schemas import SemanticSearchResponse, SimilarTaskResult
    
    try:
        service = await get_semantic_search_service(db)
        result = await service.search_similar_tasks(
            query=request.query,
            user_id=current_user.id,
            team_id=request.team_id,
            project_id=request.project_id,
            limit=request.limit
        )
        
        return SemanticSearchResponse(
            success=True,
            query=result.query,
            results=[
                SimilarTaskResult(
                    task_id=r.task_id,
                    task_name=r.task_name,
                    project_id=r.project_id,
                    project_name=r.project_name,
                    description=r.description,
                    similarity_score=r.similarity_score,
                    avg_duration_minutes=r.avg_duration_minutes,
                    times_used=r.times_used,
                    last_used=r.last_used
                )
                for r in result.results
            ],
            search_time_ms=result.search_time_ms,
            method=result.method
        )
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return SemanticSearchResponse(
            success=False,
            query=request.query,
            results=[],
            search_time_ms=0,
            method="error",
            error=str(e)
        )


@router.post(
    "/search/time-suggestions",
    response_model=SemanticSearchResponse,
    summary="Get time-based task suggestions",
    description="Get task suggestions based on the current time of day and day of week."
)
async def get_time_suggestions(
    request: TimeSuggestionsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get time-based task suggestions."""
    from app.ai.services.semantic_search_service import get_semantic_search_service
    from app.ai.schemas import SemanticSearchResponse, SimilarTaskResult
    
    try:
        service = await get_semantic_search_service(db)
        results = await service.get_task_suggestions_for_time(
            user_id=current_user.id,
            hour=request.hour,
            day_of_week=request.day_of_week,
            team_id=request.team_id,
            limit=request.limit
        )
        
        return SemanticSearchResponse(
            success=True,
            query=f"Time: {request.hour}:00, Day: {request.day_of_week}",
            results=[
                SimilarTaskResult(
                    task_id=r.task_id,
                    task_name=r.task_name,
                    project_id=r.project_id,
                    project_name=r.project_name,
                    description=r.description,
                    similarity_score=r.similarity_score,
                    avg_duration_minutes=r.avg_duration_minutes,
                    times_used=r.times_used,
                    last_used=r.last_used
                )
                for r in results
            ],
            search_time_ms=0,
            method="time_pattern"
        )
    except Exception as e:
        logger.error(f"Time suggestions error: {e}")
        return SemanticSearchResponse(
            success=False,
            query="",
            results=[],
            search_time_ms=0,
            method="error",
            error=str(e)
        )


# ============================================
# PHASE 5: TEAM ANALYTICS ENDPOINTS
# ============================================

@router.post(
    "/analytics/team",
    response_model=TeamAnalyticsResponse,
    summary="Generate team analytics report",
    description="""
    Generate comprehensive team analytics report including:
    - Individual member performance metrics
    - Team velocity tracking
    - Collaboration network analysis
    - Workload distribution
    - AI-generated insights and recommendations
    
    Requires admin role.
    """
)
async def generate_team_analytics(
    request: TeamAnalyticsRequest,
    current_user: User = Depends(require_role(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Generate team analytics report."""
    from app.ai.services.team_analytics_service import get_team_analytics_service
    from app.ai.schemas import (
        TeamAnalyticsResponse, TeamMemberMetricsSchema,
        TeamVelocitySchema, CollaborationEdgeSchema
    )
    
    try:
        service = await get_team_analytics_service(db)
        report = await service.generate_team_report(
            team_id=request.team_id,
            period_days=request.period_days,
            include_ai_insights=request.include_ai_insights
        )
        
        return TeamAnalyticsResponse(
            success=True,
            team_id=report.team_id,
            team_name=report.team_name,
            period_days=report.period_days,
            total_members=report.total_members,
            active_members=report.active_members,
            total_hours=report.total_hours,
            avg_hours_per_member=report.avg_hours_per_member,
            total_projects=report.total_projects,
            total_tasks=report.total_tasks,
            member_metrics=[
                TeamMemberMetricsSchema(
                    user_id=m.user_id,
                    user_name=m.user_name,
                    total_hours=m.total_hours,
                    avg_daily_hours=m.avg_daily_hours,
                    productive_hours_ratio=m.productive_hours_ratio,
                    projects_worked=m.projects_worked,
                    tasks_completed=m.tasks_completed,
                    consistency_score=m.consistency_score,
                    overtime_hours=m.overtime_hours,
                    weekend_hours=m.weekend_hours
                )
                for m in report.member_metrics
            ],
            velocity_history=[
                TeamVelocitySchema(
                    period_start=v.period_start,
                    period_end=v.period_end,
                    total_hours=v.total_hours,
                    hours_per_member=v.hours_per_member,
                    tasks_completed=v.tasks_completed,
                    projects_active=v.projects_active,
                    avg_task_duration_hours=v.avg_task_duration_hours,
                    velocity_trend=v.velocity_trend,
                    change_percent=v.change_percent
                )
                for v in report.velocity_history
            ],
            current_velocity_trend=report.current_velocity_trend,
            collaboration_edges=[
                CollaborationEdgeSchema(
                    user1_id=e.user1_id,
                    user1_name=e.user1_name,
                    user2_id=e.user2_id,
                    user2_name=e.user2_name,
                    shared_projects=e.shared_projects,
                    interaction_score=e.interaction_score
                )
                for e in report.collaboration_edges
            ],
            collaboration_density=report.collaboration_density,
            workload_gini=report.workload_gini,
            top_contributors=report.top_contributors,
            underutilized_members=report.underutilized_members,
            ai_insights=report.ai_insights,
            recommendations=report.recommendations,
            generated_at=report.generated_at
        )
    except ValueError as ve:
        return TeamAnalyticsResponse(
            success=False,
            team_id=request.team_id,
            team_name="Unknown",
            period_days=request.period_days,
            total_members=0,
            active_members=0,
            total_hours=0,
            avg_hours_per_member=0,
            total_projects=0,
            total_tasks=0,
            current_velocity_trend="unknown",
            collaboration_density=0,
            workload_gini=0,
            generated_at=datetime.now(),
            error=str(ve)
        )
    except Exception as e:
        logger.error(f"Team analytics error: {e}")
        return TeamAnalyticsResponse(
            success=False,
            team_id=request.team_id,
            team_name="Unknown",
            period_days=request.period_days,
            total_members=0,
            active_members=0,
            total_hours=0,
            avg_hours_per_member=0,
            total_projects=0,
            total_tasks=0,
            current_velocity_trend="unknown",
            collaboration_density=0,
            workload_gini=0,
            generated_at=datetime.now(),
            error=str(e)
        )


@router.post(
    "/analytics/compare-teams",
    response_model=TeamComparisonResponse,
    summary="Compare multiple teams",
    description="Compare performance metrics across multiple teams. Requires admin role."
)
async def compare_teams(
    request: TeamComparisonRequest,
    current_user: User = Depends(require_role(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Compare multiple teams."""
    from app.ai.services.team_analytics_service import get_team_analytics_service
    
    try:
        service = await get_team_analytics_service(db)
        comparison = await service.compare_teams(
            team_ids=request.team_ids,
            period_days=request.period_days
        )
        
        return TeamComparisonResponse(
            success=True,
            period_days=comparison["period_days"],
            teams_compared=comparison["teams_compared"],
            comparisons=comparison["comparisons"],
            generated_at=comparison["generated_at"]
        )
    except Exception as e:
        logger.error(f"Team comparison error: {e}")
        return TeamComparisonResponse(
            success=False,
            period_days=request.period_days,
            teams_compared=0,
            comparisons=[],
            generated_at=datetime.now().isoformat(),
            error=str(e)
        )
