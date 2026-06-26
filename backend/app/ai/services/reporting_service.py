"""
AI Reporting Service

Generates AI-powered report summaries and insights:
- Weekly productivity summaries
- Project health assessments
- Team performance insights
- Personalized recommendations

Uses AI (Gemini/OpenAI) to transform data into actionable insights.
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.services.ai_client import AIClient, get_ai_client
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.ai.utils.tenant_time import resolve_tenant_timezone_for_user
from app.services.ai_feature_service import AIFeatureManager
from app.utils.timewindow import local_today, now_utc, range_bounds

logger = logging.getLogger(__name__)


class InsightType(str, Enum):
    """Types of insights generated."""
    PRODUCTIVITY = "productivity"
    PROJECT_HEALTH = "project_health"
    TEAM_PERFORMANCE = "team_performance"
    WORKLOAD = "workload"
    TREND = "trend"
    RECOMMENDATION = "recommendation"
    ALERT = "alert"


class InsightSeverity(str, Enum):
    """Severity levels for insights."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Insight:
    """A single insight from analysis."""
    type: InsightType
    title: str
    description: str
    severity: InsightSeverity = InsightSeverity.INFO
    metric_value: Optional[float] = None
    metric_label: Optional[str] = None
    action_items: List[str] = field(default_factory=list)
    related_entity: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "metric_value": self.metric_value,
            "metric_label": self.metric_label,
            "action_items": self.action_items,
            "related_entity": self.related_entity
        }


@dataclass
class ReportSummary:
    """AI-generated report summary."""
    period_start: date
    period_end: date
    summary_text: str
    highlights: List[str]
    attention_needed: List[Dict[str, Any]]
    recommendations: List[str]
    insights: List[Insight]
    metrics: Dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        # Preserve canonical project fields for frontend contracts.
        # Include both project_name and name aliases for compatibility.
        raw_top_projects = self.metrics.get("top_projects", [])
        formatted_top_projects = [
            {
                "project_id": p.get("project_id"),
                "project_name": p.get("project_name", p.get("name", "Unknown")),
                "name": p.get("project_name", p.get("name", "Unknown")),
                "hours": p.get("hours", 0),
                "percentage": p.get("percentage", 0),
            }
            for p in raw_top_projects
        ]

        # Format attention_needed to match AttentionItem schema
        formatted_attention = [
            {
                "title": item.get("title", "Attention needed"),
                "description": item.get("description", ""),
                "severity": item.get("severity", "warning"),
                "actions": item.get("actions", item.get("action_items", []))
            }
            for item in self.attention_needed
        ]

        # Find most productive day
        daily_hours = self.metrics.get("daily_hours", [])
        most_productive_day = ""
        if daily_hours:
            max_day = max(daily_hours, key=lambda x: x.get("hours", 0), default={"date": ""})
            most_productive_day = max_day.get("date", "")

        # Build metrics to match SummaryMetrics schema + frontend aliases
        formatted_metrics = {
            # Core schema fields
            "week_start": self.metrics.get("week_start", self.period_start.isoformat()),
            "week_end": self.metrics.get("week_end", self.period_end.isoformat()),
            "user_count": self.metrics.get("user_count", 1),
            "total_hours": self.metrics.get("total_hours", 0),
            "last_week_hours": self.metrics.get("last_week_hours", 0),
            "hours_change_pct": self.metrics.get("hours_change_pct"),
            "projects_count": self.metrics.get("projects_count", 0),
            "top_projects": formatted_top_projects,
            "daily_hours": daily_hours,
            "avg_daily_hours": self.metrics.get("avg_daily_hours", 0),
            "max_daily_hours": self.metrics.get("max_daily_hours", 0),
            "min_daily_hours": self.metrics.get("min_daily_hours", 0),
            # Frontend compatibility aliases
            "projects_worked": self.metrics.get("projects_count", 0),
            "tasks_completed": self.metrics.get("tasks_completed", 0),
            "trend_vs_previous": self.metrics.get("hours_change_pct", 0) or 0,
            "daily_average": self.metrics.get("avg_daily_hours", 0),
            "most_productive_day": most_productive_day,
            "entry_count": self.metrics.get("entry_count", 0),
            "trend": self.metrics.get("trend", "stable"),
        }

        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "summary_text": self.summary_text,
            "ai_generated_summary": self.summary_text,  # Frontend alias
            "highlights": self.highlights,
            "attention_needed": formatted_attention,
            "attention_items": formatted_attention,  # Frontend alias
            "recommendations": self.recommendations,
            "insights": [i.to_dict() for i in self.insights],
            "metrics": formatted_metrics,
            "generated_at": self.generated_at.isoformat()
        }


class AIReportingService:
    """
    Service for generating AI-powered report summaries.

    Provides:
    - Weekly executive summaries
    - Project health assessments
    - Team productivity analysis
    - Personalized recommendations
    """

    def __init__(
        self,
        db: AsyncSession,
        ai_client: Optional[AIClient] = None,
        cache_manager: Optional[AICacheManager] = None
    ):
        self.db = db
        self.ai_client = ai_client
        self.cache = cache_manager
        self._feature_manager: Optional[AIFeatureManager] = None
        self._last_tokens_used: int = 0  # Track tokens from last AI call

    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get or create feature manager."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager

    @staticmethod
    def _top_real_project(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return highest-hours non-meeting project row, if any."""
        top_projects = metrics.get("top_projects", []) or []
        real_projects = [
            p for p in top_projects
            if p.get("project_id") not in (None, 0)
        ]
        if not real_projects:
            return None
        return max(real_projects, key=lambda p: float(p.get("hours", 0) or 0))

    async def generate_weekly_summary(
        self,
        user_id: int,
        team_id: Optional[int] = None,
        include_ai: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a weekly summary report.

        Args:
            user_id: User requesting summary
            team_id: Optional team filter
            include_ai: Whether to use AI for text generation

        Returns:
            Dict with weekly summary
        """
        try:
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_report_summaries", user_id):
                return {
                    "success": False,
                    "enabled": False,
                    "message": "AI report summaries are disabled"
                }

            # Build week boundaries in tenant-local calendar, then convert
            # local dates to UTC query instants inside _gather_weekly_metrics.
            tenant_tz = await resolve_tenant_timezone_for_user(self.db, user_id)
            today_local = local_today(tenant_tz)
            week_start = today_local - timedelta(days=today_local.weekday())
            week_end = week_start + timedelta(days=6)

            # Gather data
            metrics = await self._gather_weekly_metrics(user_id, week_start, week_end, team_id, tenant_tz)
            insights = await self._generate_insights(metrics, week_start, week_end)

            # Generate AI summary if enabled
            if include_ai and self.ai_client:
                summary_text = await self._generate_ai_summary(metrics, insights)
            else:
                summary_text = self._generate_rule_based_summary(metrics)

            # Build highlights
            highlights = self._extract_highlights(metrics, insights)

            # Build attention items
            attention_needed = self._extract_attention_items(insights)

            # Build recommendations
            recommendations = self._generate_recommendations(metrics, insights)

            summary = ReportSummary(
                period_start=week_start,
                period_end=week_end,
                summary_text=summary_text,
                highlights=highlights,
                attention_needed=attention_needed,
                recommendations=recommendations,
                insights=insights,
                metrics=metrics
            )

            # Log usage with token count
            tokens_used = self._last_tokens_used if include_ai else 0
            self._last_tokens_used = 0  # Reset for next call
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_report_summaries",
                tokens_used=tokens_used,
                metadata={"period": "weekly", "used_ai": include_ai}
            )

            return {
                "success": True,
                "enabled": True,
                "summary": summary.to_dict()
            }

        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_project_health(
        self,
        user_id: int,
        project_id: int
    ) -> Dict[str, Any]:
        """
        Generate project health assessment.

        Args:
            user_id: User requesting assessment
            project_id: Project to assess

        Returns:
            Dict with project health insights
        """
        try:
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_report_summaries", user_id):
                return {
                    "success": False,
                    "enabled": False,
                    "message": "AI report summaries are disabled"
                }

            from app.models import Project

            # Get project
            project_result = await self.db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = project_result.scalar_one_or_none()

            if not project:
                return {"success": False, "error": "Project not found"}

            # Gather project metrics
            metrics = await self._gather_project_metrics(project_id)

            data_thresholds = {
                "min_hours": 2,
                "min_tasks": 5,
            }

            # Normalize day-activity metric for threshold gating while keeping
            # compatibility with older key names used in tests/callers.
            days_with_activity = metrics.get("days_with_activity")
            if days_with_activity is None:
                days_with_activity = metrics.get("activity_days", 0)

            metrics["days_with_activity"] = days_with_activity
            metrics["activity_days"] = days_with_activity

            has_enough_activity = (
                metrics.get("total_hours", 0) >= data_thresholds["min_hours"]
                or metrics.get("total_tasks", 0) >= data_thresholds["min_tasks"]
            )

            if not has_enough_activity:
                insufficient_recommendation = (
                    f"Need at least {data_thresholds['min_hours']} hours of logged work OR "
                    f"{data_thresholds['min_tasks']} defined tasks to provide a health assessment."
                )

                insufficient_insight = Insight(
                    type=InsightType.PROJECT_HEALTH,
                    title="Not enough activity to assess yet",
                    description="Project doesn't have enough activity yet to assess.",
                    severity=InsightSeverity.INFO,
                    action_items=[insufficient_recommendation],
                )

                return {
                    "success": True,
                    "enabled": True,
                    "project_id": project_id,
                    "project_name": project.name,
                    "health_score": None,
                    "health_status": None,
                    "insufficient_data": True,
                    "data_thresholds": data_thresholds,
                    "metrics": metrics,
                    "insights": [insufficient_insight.to_dict()],
                    "recommendations": [insufficient_recommendation],
                    "generated_at": now_utc().isoformat()
                }

            # Generate health score (0-100)
            health_score = self._calculate_health_score(metrics)
            completion_measured = bool(metrics.get("completion_measured", metrics.get("total_tasks", 0) > 0))
            low_confidence = (not completion_measured) and metrics.get("this_week_hours", 0) < 5

            if low_confidence:
                health_score = min(health_score, 75)

            # Generate insights
            insights = []
            confidence_cap_insight = Insight(
                type=InsightType.PROJECT_HEALTH,
                title="Confidence Cap Applied",
                description="Limited signal — this project has no task tracking and low recent activity, so the health score is capped. Add tasks or log more time for a full assessment.",
                severity=InsightSeverity.INFO,
            )

            # Activity trend
            if metrics.get("activity_trend") == "increasing":
                insights.append(Insight(
                    type=InsightType.TREND,
                    title="Increasing Activity",
                    description="Project activity has increased over the past week",
                    severity=InsightSeverity.INFO
                ))
            elif metrics.get("activity_trend") == "decreasing":
                insights.append(Insight(
                    type=InsightType.TREND,
                    title="Decreasing Activity",
                    description="Project activity has decreased - consider a status check",
                    severity=InsightSeverity.WARNING
                ))

            # Task completion
            if completion_measured and metrics.get("task_completion_rate", 0) < 0.3:
                insights.append(Insight(
                    type=InsightType.PROJECT_HEALTH,
                    title="Low Task Completion",
                    description=f"Only {metrics.get('task_completion_rate', 0)*100:.0f}% of tasks completed",
                    severity=InsightSeverity.WARNING,
                    action_items=["Review blocked tasks", "Reassess task priorities"]
                ))

            # Team distribution
            if metrics.get("contributor_count", 0) == 1:
                insights.append(Insight(
                    type=InsightType.WORKLOAD,
                    title="Single Contributor",
                    description="Only one person is logging time on this project",
                    severity=InsightSeverity.INFO,
                    action_items=["Consider knowledge sharing sessions"]
                ))

            if low_confidence:
                insights.insert(0, confidence_cap_insight)
            elif not insights:
                if completion_measured:
                    insights.append(Insight(
                        type=InsightType.PROJECT_HEALTH,
                        title="Stable Health Signals",
                        description="No major risk signals detected from recent project activity.",
                        severity=InsightSeverity.INFO,
                    ))
                else:
                    insights.append(Insight(
                        type=InsightType.PROJECT_HEALTH,
                        title="Completion Not Tracked",
                        description="Task completion is not tracked for this project yet, so activity and collaboration signals drive the score.",
                        severity=InsightSeverity.INFO,
                    ))

            return {
                "success": True,
                "enabled": True,
                "project_id": project_id,
                "project_name": project.name,
                "health_score": health_score,
                "health_status": self._get_health_status(health_score),
                "insufficient_data": False,
                "data_thresholds": data_thresholds,
                "metrics": metrics,
                "insights": [i.to_dict() for i in insights],
                "generated_at": now_utc().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating project health: {e}")
            return {"success": False, "error": str(e)}

    async def generate_user_insights(
        self,
        user_id: int,
        target_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate insights for a specific user.

        Args:
            user_id: User requesting insights
            target_user_id: User to analyze (defaults to requester)

        Returns:
            Dict with user-specific insights
        """
        try:
            fm = await self._get_feature_manager()
            if not await fm.is_enabled("ai_report_summaries", user_id):
                return {
                    "success": False,
                    "enabled": False,
                    "message": "AI report summaries are disabled"
                }

            target_id = target_user_id or user_id

            # Get user metrics
            metrics = await self._gather_user_metrics(target_id)

            insights = []

            # Work-life balance
            avg_daily = metrics.get("avg_daily_hours", 8)
            if avg_daily > 10:
                insights.append(Insight(
                    type=InsightType.WORKLOAD,
                    title="High Work Hours",
                    description=f"Average {avg_daily:.1f} hours/day - consider workload review",
                    severity=InsightSeverity.WARNING,
                    action_items=["Review task priorities", "Consider delegation"]
                ))
            elif avg_daily < 4 and metrics.get("expected_hours", 40) >= 40:
                insights.append(Insight(
                    type=InsightType.WORKLOAD,
                    title="Low Logged Hours",
                    description=f"Average {avg_daily:.1f} hours/day logged",
                    severity=InsightSeverity.INFO,
                    action_items=["Ensure all time is being logged"]
                ))

            # Productivity trend
            if metrics.get("productivity_trend") == "improving":
                insights.append(Insight(
                    type=InsightType.PRODUCTIVITY,
                    title="Improving Productivity",
                    description="Time logging consistency has improved",
                    severity=InsightSeverity.INFO
                ))

            # Project diversity
            project_count = metrics.get("active_projects", 0)
            if project_count > 5:
                insights.append(Insight(
                    type=InsightType.WORKLOAD,
                    title="Many Active Projects",
                    description=f"Working on {project_count} projects - may impact focus",
                    severity=InsightSeverity.INFO
                ))

            return {
                "success": True,
                "enabled": True,
                "user_id": target_id,
                "metrics": metrics,
                "insights": [i.to_dict() for i in insights],
                "generated_at": now_utc().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating user insights: {e}")
            return {"success": False, "error": str(e)}

    # ============================================
    # DATA GATHERING
    # ============================================

    def _calculate_entry_duration_for_period(
        self,
        entry,
        period_start: datetime,
        period_end: datetime,
        now: datetime
    ) -> int:
        """Thin wrapper around the canonical helper.

        The arithmetic was consolidated into
        ``app.services.duration_service.calculate_entry_duration_for_period``;
        this method is retained as an instance-bound delegate so existing
        ``self._calculate_entry_duration_for_period(...)`` call sites keep
        working without churn.
        """
        from app.services.duration_service import (
            calculate_entry_duration_for_period,
        )
        return calculate_entry_duration_for_period(entry, period_start, period_end, now)

    @staticmethod
    def _build_week_comparison_cutoffs(
        week_start: date,
        week_end: date,
        reference_now: datetime,
        tz: str = "UTC",
    ) -> Dict[str, datetime]:
        """Build aligned current/prior week cutoff windows for fair comparison."""
        week_start_dt, week_end_dt = range_bounds(week_start, week_end, tz)
        this_cutoff_utc = min(max(reference_now, week_start_dt), week_end_dt)
        elapsed_since_week_start = this_cutoff_utc - week_start_dt

        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_end - timedelta(days=7)
        last_week_start_dt, last_week_end_dt = range_bounds(last_week_start, last_week_end, tz)
        last_cutoff_utc = min(last_week_start_dt + elapsed_since_week_start, last_week_end_dt)

        return {
            "week_start_dt": week_start_dt,
            "week_end_dt": week_end_dt,
            "this_cutoff_utc": this_cutoff_utc,
            "last_week_start_dt": last_week_start_dt,
            "last_week_end_dt": last_week_end_dt,
            "last_cutoff_utc": last_cutoff_utc,
        }

    async def _gather_weekly_metrics(
        self,
        user_id: int,
        week_start: date,
        week_end: date,
        team_id: Optional[int] = None,
        tz: str = "UTC",
    ) -> Dict[str, Any]:
        """Gather metrics for weekly summary."""

        from app.models import Project, Task, TeamMember, TimeEntry, User

        metrics: Dict[str, Any] = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat()
        }

        # Convert tenant-local date boundaries to UTC instants for filtering.
        week_start_dt, week_end_dt = range_bounds(week_start, week_end, tz)

        # Get relevant users
        if team_id:
            user_result = await self.db.execute(
                select(User)
                .join(TeamMember, User.id == TeamMember.user_id)
                .where(TeamMember.team_id == team_id)
            )
            users = user_result.scalars().all()
            user_ids = [u.id for u in users]
        else:
            # Just the requesting user
            user_ids = [user_id]

        metrics["user_count"] = len(user_ids)

        # Current time for calculating running timer durations
        now_utc = datetime.now(timezone.utc)

        # Total hours this week - fetch entries that OVERLAP with this week
        # This includes: entries that started this week, entries from before still running,
        # and entries that span multiple days
        # Query: started before week ends AND (ended after week starts OR still running)
        entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    TimeEntry.start_time < week_end_dt,  # Started before week ends
                    or_(
                        TimeEntry.end_time >= week_start_dt,  # Ended after week started
                        TimeEntry.end_time.is_(None)  # OR still running
                    )
                )
            )
        )
        entries = entries_result.scalars().all()

        # Calculate only the portion that falls within this week
        total_seconds = sum(
            self._calculate_entry_duration_for_period(e, week_start_dt, week_end_dt, now_utc)
            for e in entries
        )

        metrics["total_hours"] = round(total_seconds / 3600, 1)

        # Compare this week's elapsed window against the same elapsed window last week.
        comparison_cutoffs = self._build_week_comparison_cutoffs(
            week_start=week_start,
            week_end=week_end,
            reference_now=now_utc,
            tz=tz,
        )
        this_cutoff_utc = comparison_cutoffs["this_cutoff_utc"]
        last_week_start_dt = comparison_cutoffs["last_week_start_dt"]
        last_week_end_dt = comparison_cutoffs["last_week_end_dt"]
        last_cutoff_utc = comparison_cutoffs["last_cutoff_utc"]

        this_through_now_seconds = sum(
            self._calculate_entry_duration_for_period(e, week_start_dt, this_cutoff_utc, now_utc)
            for e in entries
        )

        # Fetch entries that overlapped with last week (same logic as this week)
        last_entries_result = await self.db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    TimeEntry.start_time < last_week_end_dt,
                    or_(
                        TimeEntry.end_time >= last_week_start_dt,
                        TimeEntry.end_time.is_(None)
                    )
                )
            )
        )
        last_entries = last_entries_result.scalars().all()

        # Calculate only the portion that fell within last week
        last_week_seconds = sum(
            self._calculate_entry_duration_for_period(e, last_week_start_dt, last_week_end_dt, now_utc)
            for e in last_entries
        )

        last_through_cutoff_seconds = sum(
            self._calculate_entry_duration_for_period(e, last_week_start_dt, last_cutoff_utc, now_utc)
            for e in last_entries
        )

        metrics["last_week_hours"] = round(last_week_seconds / 3600, 1)

        if last_through_cutoff_seconds > 0:
            change_pct = ((this_through_now_seconds - last_through_cutoff_seconds) / last_through_cutoff_seconds) * 100
            metrics["hours_change_pct"] = round(change_pct, 1)
        else:
            metrics["hours_change_pct"] = None

        # Projects worked on (count from entries that overlap with this week)
        projects_result = await self.db.execute(
            select(func.count(func.distinct(TimeEntry.project_id)))
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    TimeEntry.start_time < week_end_dt,
                    or_(
                        TimeEntry.end_time >= week_start_dt,
                        TimeEntry.end_time.is_(None)
                    )
                )
            )
        )
        metrics["projects_count"] = projects_result.scalar() or 0

        # Tasks completed this week - count distinct tasks the user worked on that are now DONE
        # Since Task doesn't have assignee_id, we count tasks via TimeEntry relationship
        try:
            tasks_result = await self.db.execute(
                select(func.count(func.distinct(TimeEntry.task_id)))
                .join(Task, TimeEntry.task_id == Task.id)
                .where(
                    and_(
                        TimeEntry.user_id.in_(user_ids),
                        TimeEntry.task_id.isnot(None),
                        Task.status == "DONE",
                        Task.updated_at >= week_start_dt,
                        Task.updated_at <= week_end_dt
                    )
                )
            )
            metrics["tasks_completed"] = tasks_result.scalar() or 0
        except Exception as e:
            logger.warning(f"Could not count completed tasks: {e}")
            metrics["tasks_completed"] = 0

        # Top projects by hours - calculate in Python for accuracy
        project_hours: Dict[int, Dict[str, Any]] = {}
        for entry in entries:
            project_bucket_id = entry.project_id or 0
            if project_bucket_id not in project_hours:
                project_hours[project_bucket_id] = {
                    "id": project_bucket_id,
                    "seconds": 0,
                    "project_name": "Meeting" if entry.project_id is None else "Unknown",
                }

            if entry.duration_seconds:
                project_hours[project_bucket_id]["seconds"] += entry.duration_seconds
            elif entry.end_time and entry.start_time:
                project_hours[project_bucket_id]["seconds"] += int((entry.end_time - entry.start_time).total_seconds())

        # Get project names
        if project_hours:
            real_project_ids = [pid for pid in project_hours.keys() if pid != 0]
            proj_names: Dict[int, str] = {}
            if real_project_ids:
                proj_result = await self.db.execute(
                    select(Project.id, Project.name)
                    .where(Project.id.in_(real_project_ids))
                )
                proj_names = {r.id: r.name for r in proj_result.fetchall()}

            for pid, bucket in project_hours.items():
                if pid == 0:
                    bucket["project_name"] = "Meeting"
                else:
                    bucket["project_name"] = proj_names.get(pid, "Unknown")

            top_projects = sorted(project_hours.values(), key=lambda x: x["seconds"], reverse=True)[:5]
            metrics["top_projects"] = [
                {
                    "project_id": p["id"],
                    "project_name": p["project_name"],
                    "hours": round(p["seconds"] / 3600, 1),
                    "percentage": round((p["seconds"] / total_seconds * 100) if total_seconds > 0 else 0, 1)
                }
                for p in top_projects
            ]
        else:
            metrics["top_projects"] = []

        # Daily breakdown - calculate in Python
        daily_hours_map: Dict[str, float] = {}
        for entry in entries:
            day_key = entry.start_time.strftime("%Y-%m-%d")
            if day_key not in daily_hours_map:
                daily_hours_map[day_key] = 0

            if entry.duration_seconds:
                daily_hours_map[day_key] += entry.duration_seconds
            elif entry.end_time and entry.start_time:
                daily_hours_map[day_key] += (entry.end_time - entry.start_time).total_seconds()

        metrics["daily_hours"] = [
            {"date": k, "hours": round(v / 3600, 1)}
            for k, v in sorted(daily_hours_map.items())
        ]

        # Calculate averages
        if daily_hours_map:
            daily_values = [v / 3600 for v in daily_hours_map.values()]
            metrics["avg_daily_hours"] = round(statistics.mean(daily_values), 1)
            metrics["max_daily_hours"] = round(max(daily_values), 1)
            metrics["min_daily_hours"] = round(min(daily_values), 1)
        else:
            metrics["avg_daily_hours"] = 0
            metrics["max_daily_hours"] = 0
            metrics["min_daily_hours"] = 0

        # Entry count
        metrics["entry_count"] = len(entries)

        # Trend indicator
        if metrics["hours_change_pct"] is None:
            metrics["trend"] = "stable"
        elif this_through_now_seconds > last_through_cutoff_seconds:
            metrics["trend"] = "up"
        elif this_through_now_seconds < last_through_cutoff_seconds:
            metrics["trend"] = "down"
        else:
            metrics["trend"] = "stable"

        return metrics

    async def _gather_project_metrics(self, project_id: int) -> Dict[str, Any]:
        """Gather metrics for project health."""
        from app.models import Task, TimeEntry

        metrics = {}

        # Total hours
        hours_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(TimeEntry.project_id == project_id)
        )
        total_seconds = hours_result.scalar() or 0
        metrics["total_hours"] = round(total_seconds / 3600, 1)

        # This week vs last week
        now_utc = datetime.now(timezone.utc)
        today_utc = now_utc.date()
        week_start = today_utc - timedelta(days=today_utc.weekday())
        week_end = week_start + timedelta(days=6)

        comparison_cutoffs = self._build_week_comparison_cutoffs(
            week_start=week_start,
            week_end=week_end,
            reference_now=now_utc,
            tz="UTC",
        )

        # Convert to UTC datetimes for proper comparison
        week_start_dt = comparison_cutoffs["week_start_dt"]
        week_end_dt = comparison_cutoffs["week_end_dt"]
        this_cutoff_utc = comparison_cutoffs["this_cutoff_utc"]
        last_week_start_dt = comparison_cutoffs["last_week_start_dt"]
        last_week_end_dt = comparison_cutoffs["last_week_end_dt"]
        last_cutoff_utc = comparison_cutoffs["last_cutoff_utc"]

        this_week_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    TimeEntry.start_time >= week_start_dt
                )
            )
        )
        this_week = this_week_result.scalar() or 0

        this_week_through_cutoff_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    TimeEntry.start_time >= week_start_dt,
                    TimeEntry.start_time < this_cutoff_utc,
                )
            )
        )
        this_week_through_cutoff = this_week_through_cutoff_result.scalar() or 0

        last_week_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    TimeEntry.start_time >= last_week_start_dt,
                    TimeEntry.start_time < week_start_dt
                )
            )
        )
        last_week = last_week_result.scalar() or 0

        last_week_through_cutoff_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    TimeEntry.start_time >= last_week_start_dt,
                    TimeEntry.start_time < last_cutoff_utc,
                )
            )
        )
        last_week_through_cutoff = last_week_through_cutoff_result.scalar() or 0

        metrics["this_week_hours"] = round(this_week / 3600, 1)
        metrics["last_week_hours"] = round(last_week / 3600, 1)

        if last_week_through_cutoff > 0:
            if this_week_through_cutoff > last_week_through_cutoff * 1.1:
                metrics["activity_trend"] = "increasing"
            elif this_week_through_cutoff < last_week_through_cutoff * 0.9:
                metrics["activity_trend"] = "decreasing"
            else:
                metrics["activity_trend"] = "stable"
        else:
            metrics["activity_trend"] = "new"

        # Task completion
        tasks_result = await self.db.execute(
            select(
                func.count().label("total"),
                func.sum(func.cast(Task.status == "DONE", Integer)).label("completed")
            )
            .where(Task.project_id == project_id)
        )
        task_stats = tasks_result.fetchone()

        if task_stats and task_stats.total > 0:
            metrics["total_tasks"] = task_stats.total
            metrics["completed_tasks"] = task_stats.completed or 0
            metrics["task_completion_rate"] = round((task_stats.completed or 0) / task_stats.total, 2)
            metrics["completion_measured"] = True
        else:
            metrics["total_tasks"] = 0
            metrics["completed_tasks"] = 0
            metrics["task_completion_rate"] = 0
            metrics["completion_measured"] = False

        # Contributors
        contributors_result = await self.db.execute(
            select(func.count(func.distinct(TimeEntry.user_id)))
            .where(TimeEntry.project_id == project_id)
        )
        metrics["contributor_count"] = contributors_result.scalar() or 0

        # Activity days over the trailing 30 days to detect sparse-signal projects.
        thirty_days_ago = now_utc - timedelta(days=30)
        thirty_days_ago_dt = datetime.combine(thirty_days_ago.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        activity_days_result = await self.db.execute(
            select(func.count(func.distinct(func.date(TimeEntry.start_time))))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    TimeEntry.start_time >= thirty_days_ago_dt,
                )
            )
        )
        metrics["days_with_activity"] = activity_days_result.scalar() or 0
        metrics["activity_days"] = metrics["days_with_activity"]

        return metrics

    async def _gather_user_metrics(self, user_id: int) -> Dict[str, Any]:
        """Gather metrics for user insights."""
        from app.models import TimeEntry, User

        metrics = {}

        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if user:
            metrics["user_name"] = user.name
            metrics["expected_hours"] = user.expected_hours_per_week or 40

        # Last 30 days hours - use UTC datetime for consistent timezone handling
        now_utc = datetime.now(timezone.utc)
        today_utc = now_utc.date()
        thirty_days_ago = today_utc - timedelta(days=30)
        thirty_days_ago_dt = datetime.combine(thirty_days_ago, datetime.min.time()).replace(tzinfo=timezone.utc)

        hours_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= thirty_days_ago_dt
                )
            )
        )
        total_seconds = hours_result.scalar() or 0
        metrics["total_hours_30d"] = round(total_seconds / 3600, 1)

        # Daily average - count distinct days with entries
        daily_result = await self.db.execute(
            select(func.count(func.distinct(func.date(TimeEntry.start_time))))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= thirty_days_ago_dt
                )
            )
        )
        work_days = daily_result.scalar() or 1
        metrics["avg_daily_hours"] = round((total_seconds / 3600) / work_days, 1)

        # Active projects
        projects_result = await self.db.execute(
            select(func.count(func.distinct(TimeEntry.project_id)))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= thirty_days_ago_dt
                )
            )
        )
        metrics["active_projects"] = projects_result.scalar() or 0

        # Productivity trend (compare last 2 weeks)
        two_weeks_ago = today_utc - timedelta(days=14)
        one_week_ago = today_utc - timedelta(days=7)
        two_weeks_ago_dt = datetime.combine(two_weeks_ago, datetime.min.time()).replace(tzinfo=timezone.utc)
        one_week_ago_dt = datetime.combine(one_week_ago, datetime.min.time()).replace(tzinfo=timezone.utc)

        week1_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= two_weeks_ago_dt,
                    TimeEntry.start_time < one_week_ago_dt
                )
            )
        )
        week1 = week1_result.scalar() or 0

        week2_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    TimeEntry.start_time >= one_week_ago_dt
                )
            )
        )
        week2 = week2_result.scalar() or 0

        if week1 > 0:
            if week2 > week1 * 1.1:
                metrics["productivity_trend"] = "improving"
            elif week2 < week1 * 0.9:
                metrics["productivity_trend"] = "declining"
            else:
                metrics["productivity_trend"] = "stable"
        else:
            metrics["productivity_trend"] = "new"

        return metrics

    # ============================================
    # INSIGHT GENERATION
    # ============================================

    async def _generate_insights(
        self,
        metrics: Dict[str, Any],
        week_start: date,
        week_end: date
    ) -> List[Insight]:
        """Generate insights from metrics."""
        insights = []

        # Hours trend
        change_pct = metrics.get("hours_change_pct")
        if change_pct is None:
            return insights

        if change_pct > 20:
            insights.append(Insight(
                type=InsightType.TREND,
                title="Hours Increased",
                description=f"Time logged increased {change_pct:.0f}% vs last week",
                severity=InsightSeverity.INFO,
                metric_value=change_pct,
                metric_label="% change"
            ))
        elif change_pct < -20:
            insights.append(Insight(
                type=InsightType.TREND,
                title="Hours Decreased",
                description=f"Time logged decreased {abs(change_pct):.0f}% vs last week",
                severity=InsightSeverity.WARNING,
                metric_value=change_pct,
                metric_label="% change"
            ))

        # High daily hours
        max_hours = metrics.get("max_daily_hours", 0)
        if max_hours > 10:
            insights.append(Insight(
                type=InsightType.WORKLOAD,
                title="Long Work Day",
                description=f"Peak day had {max_hours:.1f} hours logged",
                severity=InsightSeverity.WARNING if max_hours > 12 else InsightSeverity.INFO,
                metric_value=max_hours,
                metric_label="hours"
            ))

        # Project focus
        if metrics.get("projects_count", 0) > 5:
            insights.append(Insight(
                type=InsightType.WORKLOAD,
                title="Multi-Project Week",
                description=f"Work spread across {metrics['projects_count']} projects",
                severity=InsightSeverity.INFO,
                action_items=["Consider focusing on fewer projects for better efficiency"]
            ))

        return insights

    async def _generate_ai_summary(
        self,
        metrics: Dict[str, Any],
        insights: List[Insight]
    ) -> str:
        """Use AI to generate natural language summary."""
        if not self.ai_client:
            return self._generate_rule_based_summary(metrics)

        try:
            top_real = self._top_real_project(metrics)
            top_real_name = "N/A"
            if top_real is not None:
                top_real_name = top_real.get("project_name", top_real.get("name", "Unknown"))

            # Build prompt
            prompt = f"""Generate a brief, professional weekly summary for a time tracking application.

Data:
- Total hours: {metrics.get('total_hours', 0)}
- Change from last week: {f"{metrics.get('hours_change_pct', 0):.0f}%" if metrics.get('hours_change_pct') is not None else "no comparable prior period"}
- Projects worked on: {metrics.get('projects_count', 0)}
- Average daily hours: {metrics.get('avg_daily_hours', 0):.1f}
- Top project: {top_real_name}

Key observations:
{chr(10).join(['- ' + i.description for i in insights[:3]])}

Write 2-3 sentences summarizing this week's activity. Be concise and actionable."""

            response = await self.ai_client.generate(
                system_prompt="You are a professional productivity assistant. Write clear, concise summaries.",
                user_prompt=prompt,
                max_tokens=200,
                temperature=0.7
            )

            # Track token usage
            if response and response.get("usage"):
                usage = response["usage"]
                self._last_tokens_used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

            if response and response.get("data"):
                data = response["data"]
                text = data.get("raw_text", "") if isinstance(data, dict) else str(data)
                return text.strip()

        except Exception as e:
            logger.error(f"AI summary generation failed: {e}")

        return self._generate_rule_based_summary(metrics)

    def _generate_rule_based_summary(self, metrics: Dict[str, Any]) -> str:
        """Generate summary without AI."""
        total_hours = metrics.get("total_hours", 0)
        change_pct = metrics.get("hours_change_pct")
        projects = metrics.get("projects_count", 0)

        parts = [f"This week you logged {total_hours:.1f} hours across {projects} projects."]

        if change_pct is None:
            return " ".join(parts)

        if change_pct > 10:
            parts.append(f"That's {change_pct:.0f}% more than last week.")
        elif change_pct < -10:
            parts.append(f"That's {abs(change_pct):.0f}% less than last week.")

        return " ".join(parts)

    def _extract_highlights(
        self,
        metrics: Dict[str, Any],
        insights: List[Insight]
    ) -> List[str]:
        """Extract key highlights."""
        highlights = []

        total_hours = metrics.get("total_hours", 0)
        if total_hours > 0:
            highlights.append(f"Logged {total_hours:.1f} hours this week")

        top_real = self._top_real_project(metrics)
        if top_real is not None:
            project_name = top_real.get("project_name", top_real.get("name", "Unknown"))
            highlights.append(f"Most time on: {project_name} ({top_real.get('hours', 0):.1f}h)")

        change_pct = metrics.get("hours_change_pct")
        if change_pct is not None and abs(change_pct) > 10:
            direction = "up" if change_pct > 0 else "down"
            highlights.append(f"Productivity {direction} {abs(change_pct):.0f}% vs last week")

        return highlights[:5]

    def _extract_attention_items(self, insights: List[Insight]) -> List[Dict[str, Any]]:
        """Extract items needing attention."""
        return [
            {
                "title": i.title,
                "description": i.description,
                "severity": i.severity.value,
                "actions": i.action_items
            }
            for i in insights
            if i.severity in [InsightSeverity.WARNING, InsightSeverity.CRITICAL]
        ]

    def _generate_recommendations(
        self,
        metrics: Dict[str, Any],
        insights: List[Insight]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # From insights
        for insight in insights:
            if insight.action_items:
                recommendations.extend(insight.action_items)

        # Generic recommendations based on metrics
        avg_hours = metrics.get("avg_daily_hours", 0)
        if avg_hours > 9:
            recommendations.append("Consider reviewing workload distribution")

        if metrics.get("projects_count", 0) > 6:
            recommendations.append("Try to focus on fewer projects for better efficiency")

        return list(set(recommendations))[:5]

    def _calculate_health_score(self, metrics: Dict[str, Any]) -> int:
        """Calculate project health score (0-100)."""
        score = 100

        # Task completion rate impacts score
        completion_measured = bool(metrics.get("completion_measured", metrics.get("total_tasks", 0) > 0))
        if completion_measured:
            completion_rate = metrics.get("task_completion_rate", 0.5)
            score -= max(0, (0.5 - completion_rate) * 40)

        # Activity trend
        trend = metrics.get("activity_trend", "stable")
        if trend == "decreasing":
            score -= 15
        elif trend == "new":
            score -= 5

        # Contributor diversity
        contributors = metrics.get("contributor_count", 1)
        if contributors == 1:
            score -= 10

        return max(0, min(100, int(score)))

    def _get_health_status(self, score: int) -> str:
        """Convert health score to status."""
        if score >= 80:
            return "healthy"
        elif score >= 60:
            return "moderate"
        elif score >= 40:
            return "at_risk"
        else:
            return "critical"

# Factory function
async def get_reporting_service(db: AsyncSession) -> AIReportingService:
    """Create reporting service instance."""
    ai_client = await get_ai_client(db)
    cache = await get_cache_manager()
    return AIReportingService(db, ai_client, cache)
