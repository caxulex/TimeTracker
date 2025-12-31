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
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
import statistics
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.ai.services.ai_client import get_ai_client, AIClient
from app.ai.utils.cache_manager import AICacheManager, get_cache_manager
from app.services.ai_feature_service import AIFeatureManager

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
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "summary_text": self.summary_text,
            "highlights": self.highlights,
            "attention_needed": self.attention_needed,
            "recommendations": self.recommendations,
            "insights": [i.to_dict() for i in self.insights],
            "metrics": self.metrics,
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
    
    async def _get_feature_manager(self) -> AIFeatureManager:
        """Get or create feature manager."""
        if self._feature_manager is None:
            self._feature_manager = AIFeatureManager(self.db)
        return self._feature_manager
    
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
            
            # Calculate week boundaries
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Gather data
            metrics = await self._gather_weekly_metrics(user_id, week_start, week_end, team_id)
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
            
            # Log usage
            await fm.log_usage(
                user_id=user_id,
                feature_id="ai_report_summaries",
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
            
            from app.models import Project, TimeEntry, Task
            
            # Get project
            project_result = await self.db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                return {"success": False, "error": "Project not found"}
            
            # Gather project metrics
            metrics = await self._gather_project_metrics(project_id)
            
            # Generate health score (0-100)
            health_score = self._calculate_health_score(metrics)
            
            # Generate insights
            insights = []
            
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
            if metrics.get("task_completion_rate", 0) < 0.3:
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
            
            return {
                "success": True,
                "enabled": True,
                "project_id": project_id,
                "project_name": project.name,
                "health_score": health_score,
                "health_status": self._get_health_status(health_score),
                "metrics": metrics,
                "insights": [i.to_dict() for i in insights],
                "generated_at": datetime.now().isoformat()
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
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating user insights: {e}")
            return {"success": False, "error": str(e)}
    
    # ============================================
    # DATA GATHERING
    # ============================================
    
    async def _gather_weekly_metrics(
        self,
        user_id: int,
        week_start: date,
        week_end: date,
        team_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Gather metrics for weekly summary."""
        from app.models import TimeEntry, User, Project, Task, TeamMember
        
        metrics: Dict[str, Any] = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat()
        }
        
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
        
        # Total hours this week
        hours_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    func.date(TimeEntry.start_time) >= week_start,
                    func.date(TimeEntry.start_time) <= week_end
                )
            )
        )
        total_seconds = hours_result.scalar() or 0
        metrics["total_hours"] = round(total_seconds / 3600, 1)
        
        # Compare to last week
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_end - timedelta(days=7)
        
        last_week_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    func.date(TimeEntry.start_time) >= last_week_start,
                    func.date(TimeEntry.start_time) <= last_week_end
                )
            )
        )
        last_week_seconds = last_week_result.scalar() or 0
        metrics["last_week_hours"] = round(last_week_seconds / 3600, 1)
        
        if last_week_seconds > 0:
            change_pct = ((total_seconds - last_week_seconds) / last_week_seconds) * 100
            metrics["hours_change_pct"] = round(change_pct, 1)
        else:
            metrics["hours_change_pct"] = 0
        
        # Projects worked on
        projects_result = await self.db.execute(
            select(func.count(func.distinct(TimeEntry.project_id)))
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    func.date(TimeEntry.start_time) >= week_start,
                    func.date(TimeEntry.start_time) <= week_end
                )
            )
        )
        metrics["projects_count"] = projects_result.scalar() or 0
        
        # Top projects by hours
        top_projects_result = await self.db.execute(
            select(
                Project.name,
                func.sum(TimeEntry.duration_seconds).label("total_seconds")
            )
            .join(Project, TimeEntry.project_id == Project.id)
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    func.date(TimeEntry.start_time) >= week_start,
                    func.date(TimeEntry.start_time) <= week_end
                )
            )
            .group_by(Project.id, Project.name)
            .order_by(func.sum(TimeEntry.duration_seconds).desc())
            .limit(5)
        )
        metrics["top_projects"] = [
            {"name": row.name, "hours": round(row.total_seconds / 3600, 1)}
            for row in top_projects_result.fetchall()
        ]
        
        # Daily breakdown
        daily_result = await self.db.execute(
            select(
                func.date(TimeEntry.start_time).label("work_date"),
                func.sum(TimeEntry.duration_seconds).label("total_seconds")
            )
            .where(
                and_(
                    TimeEntry.user_id.in_(user_ids),
                    func.date(TimeEntry.start_time) >= week_start,
                    func.date(TimeEntry.start_time) <= week_end
                )
            )
            .group_by(func.date(TimeEntry.start_time))
            .order_by(func.date(TimeEntry.start_time))
        )
        daily_data = daily_result.fetchall()
        metrics["daily_hours"] = [
            {"date": str(row.work_date), "hours": round(row.total_seconds / 3600, 1)}
            for row in daily_data
        ]
        
        # Calculate averages
        if daily_data:
            daily_hours = [row.total_seconds / 3600 for row in daily_data]
            metrics["avg_daily_hours"] = round(statistics.mean(daily_hours), 1)
            metrics["max_daily_hours"] = round(max(daily_hours), 1)
            metrics["min_daily_hours"] = round(min(daily_hours), 1)
        else:
            metrics["avg_daily_hours"] = 0
            metrics["max_daily_hours"] = 0
            metrics["min_daily_hours"] = 0
        
        return metrics
    
    async def _gather_project_metrics(self, project_id: int) -> Dict[str, Any]:
        """Gather metrics for project health."""
        from app.models import TimeEntry, Task, User
        
        metrics = {}
        
        # Total hours
        hours_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(TimeEntry.project_id == project_id)
        )
        total_seconds = hours_result.scalar() or 0
        metrics["total_hours"] = round(total_seconds / 3600, 1)
        
        # This week vs last week
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        last_week_start = week_start - timedelta(days=7)
        
        this_week_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    func.date(TimeEntry.start_time) >= week_start
                )
            )
        )
        this_week = this_week_result.scalar() or 0
        
        last_week_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.project_id == project_id,
                    func.date(TimeEntry.start_time) >= last_week_start,
                    func.date(TimeEntry.start_time) < week_start
                )
            )
        )
        last_week = last_week_result.scalar() or 0
        
        metrics["this_week_hours"] = round(this_week / 3600, 1)
        metrics["last_week_hours"] = round(last_week / 3600, 1)
        
        if last_week > 0:
            if this_week > last_week * 1.1:
                metrics["activity_trend"] = "increasing"
            elif this_week < last_week * 0.9:
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
        else:
            metrics["total_tasks"] = 0
            metrics["completed_tasks"] = 0
            metrics["task_completion_rate"] = 0
        
        # Contributors
        contributors_result = await self.db.execute(
            select(func.count(func.distinct(TimeEntry.user_id)))
            .where(TimeEntry.project_id == project_id)
        )
        metrics["contributor_count"] = contributors_result.scalar() or 0
        
        return metrics
    
    async def _gather_user_metrics(self, user_id: int) -> Dict[str, Any]:
        """Gather metrics for user insights."""
        from app.models import TimeEntry, User, Project
        
        metrics = {}
        
        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user:
            metrics["user_name"] = user.name
            metrics["expected_hours"] = user.expected_hours_per_week or 40
        
        # Last 30 days hours
        thirty_days_ago = date.today() - timedelta(days=30)
        
        hours_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    func.date(TimeEntry.start_time) >= thirty_days_ago
                )
            )
        )
        total_seconds = hours_result.scalar() or 0
        metrics["total_hours_30d"] = round(total_seconds / 3600, 1)
        
        # Daily average
        daily_result = await self.db.execute(
            select(func.count(func.distinct(func.date(TimeEntry.start_time))))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    func.date(TimeEntry.start_time) >= thirty_days_ago
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
                    func.date(TimeEntry.start_time) >= thirty_days_ago
                )
            )
        )
        metrics["active_projects"] = projects_result.scalar() or 0
        
        # Productivity trend (compare last 2 weeks)
        two_weeks_ago = date.today() - timedelta(days=14)
        one_week_ago = date.today() - timedelta(days=7)
        
        week1_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    func.date(TimeEntry.start_time) >= two_weeks_ago,
                    func.date(TimeEntry.start_time) < one_week_ago
                )
            )
        )
        week1 = week1_result.scalar() or 0
        
        week2_result = await self.db.execute(
            select(func.sum(TimeEntry.duration_seconds))
            .where(
                and_(
                    TimeEntry.user_id == user_id,
                    func.date(TimeEntry.start_time) >= one_week_ago
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
        change_pct = metrics.get("hours_change_pct", 0)
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
            # Build prompt
            prompt = f"""Generate a brief, professional weekly summary for a time tracking application.

Data:
- Total hours: {metrics.get('total_hours', 0)}
- Change from last week: {metrics.get('hours_change_pct', 0):.0f}%
- Projects worked on: {metrics.get('projects_count', 0)}
- Average daily hours: {metrics.get('avg_daily_hours', 0):.1f}
- Top project: {metrics.get('top_projects', [{}])[0].get('name', 'N/A') if metrics.get('top_projects') else 'N/A'}

Key observations:
{chr(10).join(['- ' + i.description for i in insights[:3]])}

Write 2-3 sentences summarizing this week's activity. Be concise and actionable."""

            response = await self.ai_client.generate(
                system_prompt="You are a professional productivity assistant. Write clear, concise summaries.",
                user_prompt=prompt,
                max_tokens=200,
                temperature=0.7
            )
            
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
        change_pct = metrics.get("hours_change_pct", 0)
        projects = metrics.get("projects_count", 0)
        
        parts = [f"This week you logged {total_hours:.1f} hours across {projects} projects."]
        
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
        
        top_projects = metrics.get("top_projects", [])
        if top_projects:
            top = top_projects[0]
            highlights.append(f"Most time on: {top['name']} ({top['hours']:.1f}h)")
        
        change_pct = metrics.get("hours_change_pct", 0)
        if abs(change_pct) > 10:
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


# Add missing import
from sqlalchemy import Integer

# Factory function
async def get_reporting_service(db: AsyncSession) -> AIReportingService:
    """Create reporting service instance."""
    ai_client = await get_ai_client(db)
    cache = await get_cache_manager()
    return AIReportingService(db, ai_client, cache)
