"""
Forecasting Service

Provides predictive analytics for:
- Payroll forecasting (next period cost predictions)
- Project budget predictions
- Overtime risk alerts
- Cash flow planning

Uses time-series analysis and pattern detection for predictions.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import statistics
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.services.ai_feature_service import AIFeatureManager

logger = logging.getLogger(__name__)


class ForecastType(str, Enum):
    """Types of forecasts available."""
    PAYROLL = "payroll"
    PROJECT_BUDGET = "project_budget"
    OVERTIME_RISK = "overtime_risk"
    CASH_FLOW = "cash_flow"


class RiskLevel(str, Enum):
    """Risk levels for predictions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PayrollForecast:
    """Payroll forecast result."""
    period_start: date
    period_end: date
    predicted_total: Decimal
    predicted_regular: Decimal
    predicted_overtime: Decimal
    confidence: float
    lower_bound: Decimal
    upper_bound: Decimal
    trend: str  # "increasing", "decreasing", "stable"
    factors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "predicted_total": float(self.predicted_total),
            "predicted_regular": float(self.predicted_regular),
            "predicted_overtime": float(self.predicted_overtime),
            "confidence": round(self.confidence, 3),
            "lower_bound": float(self.lower_bound),
            "upper_bound": float(self.upper_bound),
            "trend": self.trend,
            "factors": self.factors
        }


@dataclass
class OvertimeRisk:
    """Overtime risk assessment for a user."""
    user_id: int
    user_name: str
    current_hours: float
    projected_hours: float
    overtime_threshold: float
    risk_level: RiskLevel
    projected_overtime: float
    estimated_cost: Decimal
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "current_hours": round(self.current_hours, 2),
            "projected_hours": round(self.projected_hours, 2),
            "overtime_threshold": self.overtime_threshold,
            "risk_level": self.risk_level.value,
            "projected_overtime": round(self.projected_overtime, 2),
            "estimated_cost": float(self.estimated_cost),
            "recommendation": self.recommendation
        }


@dataclass
class ProjectBudgetForecast:
    """Budget forecast for a project."""
    project_id: int
    project_name: str
    budget_total: Decimal
    spent_to_date: Decimal
    projected_total: Decimal
    burn_rate_daily: Decimal
    days_remaining: int
    projected_completion: date
    risk_level: RiskLevel
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "budget_total": float(self.budget_total),
            "spent_to_date": float(self.spent_to_date),
            "projected_total": float(self.projected_total),
            "burn_rate_daily": float(self.burn_rate_daily),
            "days_remaining": self.days_remaining,
            "projected_completion": self.projected_completion.isoformat() if self.projected_completion else None,
            "risk_level": self.risk_level.value,
            "budget_utilization_pct": round(float(self.spent_to_date / self.budget_total * 100), 1) if self.budget_total > 0 else 0,
            "recommendations": self.recommendations
        }


class ForecastingService:
    """
    Service for generating predictive analytics.
    
    Uses historical data analysis with:
    - Moving averages for trend detection
    - Standard deviation for confidence intervals
    - Pattern matching for seasonality
    """
    
    def __init__(
        self,
        db: AsyncSession,
        cache_manager: Optional[AICacheManager] = None
    ):
        self.db = db
        self.cache = cache_manager
        self._feature_manager: Optional[AIFeatureManager] = None

    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get feature manager instance."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager

    # ============================================
    # PAYROLL FORECASTING
    # ============================================

    async def forecast_payroll(
        self,
        user_id: int,
        period_type: str = "bi_weekly",  # weekly, bi_weekly, semi_monthly, monthly
        periods_ahead: int = 1,
        include_overtime: bool = True
    ) -> Dict[str, Any]:
        """
        Forecast payroll for upcoming period(s).
        
        Args:
            user_id: User requesting forecast (for auth/logging)
            period_type: Type of payroll period
            periods_ahead: How many periods to forecast
            include_overtime: Include overtime projections
            
        Returns:
            Dict with forecast data and metadata
        """
        try:
            # Check if feature is enabled
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_payroll_forecast", user_id):
                return {
                    "forecasts": [],
                    "enabled": False,
                    "message": "Payroll forecasting is disabled"
                }

            # Check cache
            cache_key = f"payroll_{period_type}_{periods_ahead}"
            cache_id = abs(hash(cache_key)) % (10**9)  # Convert to positive int
            if self.cache:
                cached = await self.cache.get_forecast_cache("payroll", cache_id)
                if cached:
                    return cached

            # Get historical payroll data
            historical_data = await self._get_payroll_history(period_type)
            
            if len(historical_data) < 3:
                return {
                    "forecasts": [],
                    "enabled": True,
                    "message": "Insufficient historical data (need at least 3 periods)"
                }

            # Generate forecasts
            forecasts = []
            last_period_end = historical_data[-1]["period_end"]
            
            for i in range(periods_ahead):
                period_start, period_end = self._calculate_next_period(
                    last_period_end,
                    period_type,
                    offset=i
                )
                
                forecast = await self._generate_payroll_forecast(
                    historical_data,
                    period_start,
                    period_end,
                    include_overtime
                )
                forecasts.append(forecast.to_dict())
                last_period_end = period_end

            result = {
                "forecasts": forecasts,
                "enabled": True,
                "period_type": period_type,
                "historical_periods_used": len(historical_data),
                "generated_at": datetime.now().isoformat()
            }

            # Cache result (forecast_type, entity_id, forecast)
            if self.cache:
                await self.cache.set_forecast_cache(
                    "payroll",
                    abs(hash(cache_key)) % (10**9),  # Convert to positive int
                    result
                )

            # Log usage
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_payroll_forecast"
            )

            return result

        except Exception as e:
            logger.error(f"Error forecasting payroll: {e}")
            return {
                "forecasts": [],
                "error": str(e),
                "enabled": True
            }

    async def _get_payroll_history(
        self,
        period_type: str,
        limit: int = 12
    ) -> List[Dict[str, Any]]:
        """Get historical payroll data for analysis."""
        from app.models import PayrollPeriod, PayrollEntry
        
        # Get completed payroll periods
        result = await self.db.execute(
            select(PayrollPeriod)
            .where(
                and_(
                    PayrollPeriod.period_type == period_type,
                    PayrollPeriod.status == "paid"
                )
            )
            .order_by(PayrollPeriod.start_date.desc())
            .limit(limit)
        )
        periods = result.scalars().all()
        
        history = []
        for period in reversed(periods):  # Oldest first
            # Get entries for this period
            entries_result = await self.db.execute(
                select(PayrollEntry)
                .where(PayrollEntry.payroll_period_id == period.id)
            )
            entries = entries_result.scalars().all()
            
            total_regular = sum(e.regular_hours or 0 for e in entries)
            total_overtime = sum(e.overtime_hours or 0 for e in entries)
            total_gross = sum(e.gross_amount or Decimal(0) for e in entries)
            
            history.append({
                "period_id": period.id,
                "period_start": period.start_date,
                "period_end": period.end_date,
                "regular_hours": float(total_regular),
                "overtime_hours": float(total_overtime),
                "gross_amount": float(total_gross),
                "employee_count": len(entries)
            })
        
        return history

    def _calculate_next_period(
        self,
        last_end: date,
        period_type: str,
        offset: int = 0
    ) -> Tuple[date, date]:
        """Calculate next payroll period dates."""
        # Move to next day after last period
        period_start = last_end + timedelta(days=1)
        
        # Apply offset
        if period_type == "weekly":
            period_start += timedelta(weeks=offset)
            period_end = period_start + timedelta(days=6)
        elif period_type == "bi_weekly":
            period_start += timedelta(weeks=2 * offset)
            period_end = period_start + timedelta(days=13)
        elif period_type == "semi_monthly":
            # 1-15 or 16-end of month
            if period_start.day <= 15:
                period_end = period_start.replace(day=15)
            else:
                # End of month
                next_month = period_start.replace(day=28) + timedelta(days=4)
                period_end = next_month - timedelta(days=next_month.day)
        else:  # monthly
            period_start += timedelta(days=30 * offset)
            next_month = period_start.replace(day=28) + timedelta(days=4)
            period_end = next_month - timedelta(days=next_month.day)
        
        return period_start, period_end

    async def _generate_payroll_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        period_start: date,
        period_end: date,
        include_overtime: bool
    ) -> PayrollForecast:
        """Generate forecast using statistical analysis."""
        # Extract time series
        amounts = [d["gross_amount"] for d in historical_data]
        regular_hours = [d["regular_hours"] for d in historical_data]
        overtime_hours = [d["overtime_hours"] for d in historical_data]
        
        # Calculate weighted moving average (recent periods weighted more)
        weights = list(range(1, len(amounts) + 1))
        total_weight = sum(weights)
        
        weighted_avg = sum(a * w for a, w in zip(amounts, weights)) / total_weight
        
        # Calculate trend
        if len(amounts) >= 3:
            recent_avg = statistics.mean(amounts[-3:])
            older_avg = statistics.mean(amounts[:-3]) if len(amounts) > 3 else amounts[0]
            
            if recent_avg > older_avg * 1.05:
                trend = "increasing"
                trend_factor = recent_avg / older_avg
            elif recent_avg < older_avg * 0.95:
                trend = "decreasing"
                trend_factor = recent_avg / older_avg
            else:
                trend = "stable"
                trend_factor = 1.0
        else:
            trend = "stable"
            trend_factor = 1.0
        
        # Apply trend adjustment
        predicted_total = Decimal(str(weighted_avg * trend_factor))
        
        # Calculate regular vs overtime split
        avg_regular_pct = sum(regular_hours) / max(sum(regular_hours) + sum(overtime_hours), 1)
        predicted_regular = predicted_total * Decimal(str(avg_regular_pct))
        predicted_overtime = predicted_total - predicted_regular if include_overtime else Decimal(0)
        
        # Confidence interval based on standard deviation
        if len(amounts) >= 3:
            std_dev = statistics.stdev(amounts)
            confidence = max(0.6, 1 - (std_dev / statistics.mean(amounts)) if statistics.mean(amounts) > 0 else 0.5)
        else:
            std_dev = statistics.mean(amounts) * 0.15
            confidence = 0.5
        
        margin = Decimal(str(std_dev * 1.96))  # 95% confidence interval
        lower_bound = max(predicted_total - margin, Decimal(0))
        upper_bound = predicted_total + margin
        
        # Identify contributing factors
        factors = []
        if trend == "increasing":
            factors.append({"factor": "trend", "description": "Payroll costs trending upward", "impact": "positive"})
        elif trend == "decreasing":
            factors.append({"factor": "trend", "description": "Payroll costs trending downward", "impact": "negative"})
        
        if sum(overtime_hours) / len(overtime_hours) > 5:
            factors.append({"factor": "overtime", "description": "Significant overtime observed", "impact": "positive"})
        
        return PayrollForecast(
            period_start=period_start,
            period_end=period_end,
            predicted_total=predicted_total.quantize(Decimal("0.01")),
            predicted_regular=predicted_regular.quantize(Decimal("0.01")),
            predicted_overtime=predicted_overtime.quantize(Decimal("0.01")),
            confidence=confidence,
            lower_bound=lower_bound.quantize(Decimal("0.01")),
            upper_bound=upper_bound.quantize(Decimal("0.01")),
            trend=trend,
            factors=factors
        )

    # ============================================
    # OVERTIME RISK ASSESSMENT
    # ============================================

    async def assess_overtime_risk(
        self,
        user_id: int,
        days_ahead: int = 7,
        team_id: Optional[int] = None,
        company_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Assess overtime risk for employees.
        
        Identifies users likely to exceed overtime thresholds
        based on current hours and historical patterns.
        
        Args:
            user_id: User requesting assessment
            days_ahead: Days to project
            team_id: Optional team filter
            company_id: Optional company filter for multi-tenancy
            
        Returns:
            Dict with risk assessments per user
        """
        try:
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_payroll_forecast", user_id):
                return {
                    "risks": [],
                    "enabled": False,
                    "message": "Overtime risk assessment is disabled"
                }

            from app.models import User, TimeEntry, PayRate, TeamMember
            
            # Get users to assess
            if team_id:
                query = (
                    select(User)
                    .join(TeamMember, User.id == TeamMember.user_id)
                    .where(User.is_active == True)
                    .where(TeamMember.team_id == team_id)
                )
            else:
                query = select(User).where(User.is_active == True)
            
            # Filter by company_id if provided (multi-tenancy)
            if company_id is not None:
                query = query.where(User.company_id == company_id)
            
            result = await self.db.execute(query)
            users = result.scalars().all()
            
            risks = []
            week_start = self._get_week_start()
            week_end = week_start + timedelta(days=6)
            
            for user in users:
                # Get current week hours
                current_hours = await self._get_user_hours(
                    user.id,
                    week_start,
                    date.today()
                )
                
                # Get historical average daily hours
                avg_daily = await self._get_avg_daily_hours(user.id, days=30)
                
                # Get overtime threshold
                expected_weekly = float(user.expected_hours_per_week or 40)
                overtime_threshold = expected_weekly
                
                # Project hours for rest of week
                days_left = (week_end - date.today()).days
                projected_additional = avg_daily * days_left
                projected_total = current_hours + projected_additional
                
                # Calculate risk
                if projected_total > overtime_threshold * 1.2:
                    risk_level = RiskLevel.CRITICAL
                    recommendation = f"Urgent: Reduce workload. Projected {projected_total - overtime_threshold:.1f}h overtime"
                elif projected_total > overtime_threshold * 1.1:
                    risk_level = RiskLevel.HIGH
                    recommendation = f"Review workload distribution. Likely to exceed threshold by {projected_total - overtime_threshold:.1f}h"
                elif projected_total > overtime_threshold:
                    risk_level = RiskLevel.MEDIUM
                    recommendation = "Minor overtime expected. Monitor daily"
                else:
                    risk_level = RiskLevel.LOW
                    recommendation = "On track for normal hours"
                
                # Only include medium+ risks
                if risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    # Estimate overtime cost
                    pay_rate = await self._get_user_pay_rate(user.id)
                    overtime_hours = max(projected_total - overtime_threshold, 0)
                    overtime_cost = Decimal(str(overtime_hours)) * pay_rate * Decimal("1.5")
                    
                    risks.append(OvertimeRisk(
                        user_id=user.id,
                        user_name=user.name,
                        current_hours=current_hours,
                        projected_hours=projected_total,
                        overtime_threshold=overtime_threshold,
                        risk_level=risk_level,
                        projected_overtime=max(projected_total - overtime_threshold, 0),
                        estimated_cost=overtime_cost.quantize(Decimal("0.01")),
                        recommendation=recommendation
                    ).to_dict())
            
            # Sort by risk level
            risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            risks.sort(key=lambda x: risk_order.get(x["risk_level"], 4))
            
            return {
                "risks": risks,
                "enabled": True,
                "period": f"{week_start.isoformat()} to {week_end.isoformat()}",
                "users_assessed": len(users),
                "users_at_risk": len(risks),
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error assessing overtime risk: {e}")
            return {
                "risks": [],
                "error": str(e),
                "enabled": True
            }

    def _get_week_start(self) -> date:
        """Get Monday of current week."""
        today = date.today()
        return today - timedelta(days=today.weekday())

    async def _get_user_hours(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> float:
        """Get total hours for user in date range."""
        from app.models import TimeEntry
        
        result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    func.date(TimeEntry.start_time) >= start_date,
                    func.date(TimeEntry.start_time) <= end_date
                )
            )
        )
        total_seconds = result.scalar() or 0
        return total_seconds / 3600

    async def _get_avg_daily_hours(
        self,
        user_id: int,
        days: int = 30
    ) -> float:
        """Get average daily hours for user."""
        from app.models import TimeEntry
        
        start_date = date.today() - timedelta(days=days)
        
        result = await self.db.execute(
            select(
                func.date(TimeEntry.start_time).label("work_date"),
                func.sum(TimeEntry.duration_seconds).label("total_seconds")
            )
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    func.date(TimeEntry.start_time) >= start_date
                )
            )
            .group_by(func.date(TimeEntry.start_time))
        )
        
        daily_hours = [row.total_seconds / 3600 for row in result.fetchall()]
        
        if not daily_hours:
            return 8.0  # Default assumption
        
        return statistics.mean(daily_hours)

    async def _get_user_pay_rate(self, user_id: int) -> Decimal:
        """Get current hourly pay rate for user."""
        from app.models import PayRate
        
        result = await self.db.execute(
            select(PayRate)
            .where(
                and_(
                    PayRate.user_id == user_id,
                    PayRate.is_active == True,
                    or_(
                        PayRate.effective_to == None,
                        PayRate.effective_to >= date.today()
                    )
                )
            )
            .order_by(PayRate.effective_from.desc())
            .limit(1)
        )
        pay_rate = result.scalar_one_or_none()
        
        if pay_rate:
            return pay_rate.base_rate
        return Decimal("25.00")  # Default rate

    # ============================================
    # PROJECT BUDGET FORECASTING
    # ============================================

    async def forecast_project_budget(
        self,
        user_id: int,
        project_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Forecast project budget consumption.
        
        Args:
            user_id: User requesting forecast
            project_id: Specific project (optional)
            team_id: Team projects (optional)
            
        Returns:
            Dict with budget forecasts per project
        """
        try:
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_payroll_forecast", user_id):
                return {
                    "forecasts": [],
                    "enabled": False,
                    "message": "Budget forecasting is disabled"
                }

            from app.models import Project, TimeEntry, PayRate, TeamMember
            
            # Get projects to analyze
            if project_id:
                query = select(Project).where(Project.id == project_id)
            elif team_id:
                query = select(Project).where(
                    and_(
                        Project.team_id == team_id,
                        Project.is_archived == False
                    )
                )
            else:
                query = select(Project).where(Project.is_archived == False).limit(20)
            
            result = await self.db.execute(query)
            projects = result.scalars().all()
            
            forecasts = []
            for project in projects:
                forecast = await self._analyze_project_budget(project)
                if forecast:
                    forecasts.append(forecast.to_dict())
            
            # Sort by risk
            risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            forecasts.sort(key=lambda x: risk_order.get(x["risk_level"], 4))
            
            return {
                "forecasts": forecasts,
                "enabled": True,
                "projects_analyzed": len(projects),
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error forecasting project budget: {e}")
            return {
                "forecasts": [],
                "error": str(e),
                "enabled": True
            }

    async def _analyze_project_budget(
        self,
        project
    ) -> Optional[ProjectBudgetForecast]:
        """Analyze budget consumption for a project."""
        from app.models import TimeEntry, PayRate
        
        # Calculate labor cost to date
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(TimeEntry.project_id == project.id)
        )
        entries = entries_result.scalars().all()
        
        if not entries:
            return None
        
        # Calculate total hours and approximate cost
        total_hours = sum(e.duration_seconds or 0 for e in entries) / 3600
        
        # Get average pay rate (simplified)
        avg_rate = Decimal("50.00")  # Default blended rate
        spent_to_date = Decimal(str(total_hours)) * avg_rate
        
        # Calculate burn rate
        if entries:
            first_entry = min(entries, key=lambda e: e.start_time)
            days_active = max((date.today() - first_entry.start_time.date()).days, 1)
            burn_rate_daily = spent_to_date / days_active
        else:
            burn_rate_daily = Decimal(0)
        
        # For this implementation, we'll use a hypothetical budget
        # In production, this would come from a project budget field
        budget_total = Decimal("50000.00")  # Placeholder
        
        # Project completion
        if burn_rate_daily > 0:
            remaining_budget = budget_total - spent_to_date
            days_remaining = int(remaining_budget / burn_rate_daily) if burn_rate_daily > 0 else 365
            projected_completion = date.today() + timedelta(days=days_remaining)
            projected_total = spent_to_date + (burn_rate_daily * days_remaining)
        else:
            days_remaining = 365
            projected_completion = date.today() + timedelta(days=365)
            projected_total = spent_to_date
        
        # Determine risk level
        utilization = float(spent_to_date / budget_total * 100) if budget_total > 0 else 0
        
        if utilization > 90:
            risk_level = RiskLevel.CRITICAL
            recommendations = [
                "Project approaching budget limit",
                "Review remaining scope for cuts",
                "Request budget increase if necessary"
            ]
        elif utilization > 75:
            risk_level = RiskLevel.HIGH
            recommendations = [
                "Monitor spending closely",
                "Prioritize critical deliverables"
            ]
        elif utilization > 50:
            risk_level = RiskLevel.MEDIUM
            recommendations = [
                "On track but continue monitoring"
            ]
        else:
            risk_level = RiskLevel.LOW
            recommendations = [
                "Budget utilization healthy"
            ]
        
        return ProjectBudgetForecast(
            project_id=project.id,
            project_name=project.name,
            budget_total=budget_total,
            spent_to_date=spent_to_date.quantize(Decimal("0.01")),
            projected_total=projected_total.quantize(Decimal("0.01")) if isinstance(projected_total, Decimal) else Decimal(str(projected_total)).quantize(Decimal("0.01")),
            burn_rate_daily=burn_rate_daily.quantize(Decimal("0.01")),
            days_remaining=days_remaining,
            projected_completion=projected_completion,
            risk_level=risk_level,
            recommendations=recommendations
        )

    # ============================================
    # CASH FLOW PLANNING
    # ============================================

    async def forecast_cash_flow(
        self,
        user_id: int,
        weeks_ahead: int = 4
    ) -> Dict[str, Any]:
        """
        Forecast weekly cash flow for payroll.
        
        Args:
            user_id: User requesting forecast
            weeks_ahead: Weeks to forecast
            
        Returns:
            Dict with weekly cash flow projections
        """
        try:
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_payroll_forecast", user_id):
                return {
                    "forecast": [],
                    "enabled": False,
                    "message": "Cash flow forecasting is disabled"
                }

            # Get recent payroll averages
            historical = await self._get_payroll_history("bi_weekly", limit=6)
            
            if not historical:
                return {
                    "forecast": [],
                    "enabled": True,
                    "message": "Insufficient payroll history"
                }
            
            avg_payroll = statistics.mean([h["gross_amount"] for h in historical])
            
            # Generate weekly forecast
            forecast = []
            current_week = self._get_week_start()
            
            for i in range(weeks_ahead):
                week_start = current_week + timedelta(weeks=i)
                week_end = week_start + timedelta(days=6)
                
                # Check if payroll falls in this week (assume bi-weekly)
                is_payroll_week = (i % 2 == 0)
                
                forecast.append({
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "is_payroll_week": is_payroll_week,
                    "projected_payroll": round(avg_payroll, 2) if is_payroll_week else 0,
                    "cumulative": round(avg_payroll * ((i // 2) + 1), 2) if is_payroll_week else round(avg_payroll * (i // 2), 2)
                })
            
            return {
                "forecast": forecast,
                "enabled": True,
                "average_payroll": round(avg_payroll, 2),
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error forecasting cash flow: {e}")
            return {
                "forecast": [],
                "error": str(e),
                "enabled": True
            }


# Factory function
async def get_forecasting_service(db: AsyncSession) -> ForecastingService:
    """Create forecasting service instance."""
    cache = await get_cache_manager()
    return ForecastingService(db, cache)
