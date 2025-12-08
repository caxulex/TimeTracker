"""
Report Templates Service - TASK-030
Pre-defined report templates (weekly, monthly, project-based, productivity)
"""

import json
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timedelta
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models import TimeEntry, Project, Task, User


class ReportType(str, Enum):
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    PROJECT_BREAKDOWN = "project_breakdown"
    PRODUCTIVITY_ANALYSIS = "productivity_analysis"
    USER_ACTIVITY = "user_activity"
    TEAM_COMPARISON = "team_comparison"
    BILLABLE_HOURS = "billable_hours"


@dataclass
class ReportTemplate:
    """Report template definition"""
    id: str
    name: str
    description: str
    report_type: ReportType
    default_params: Dict[str, Any]


# Pre-defined templates
REPORT_TEMPLATES = {
    "weekly_summary": ReportTemplate(
        id="weekly_summary",
        name="Weekly Summary",
        description="Summary of hours worked by day for the current/past week",
        report_type=ReportType.WEEKLY_SUMMARY,
        default_params={"include_projects": True, "include_tasks": True}
    ),
    "monthly_summary": ReportTemplate(
        id="monthly_summary",
        name="Monthly Summary",
        description="Complete monthly breakdown by project and user",
        report_type=ReportType.MONTHLY_SUMMARY,
        default_params={"group_by_project": True, "include_trends": True}
    ),
    "project_breakdown": ReportTemplate(
        id="project_breakdown",
        name="Project Breakdown",
        description="Detailed hours breakdown for a specific project",
        report_type=ReportType.PROJECT_BREAKDOWN,
        default_params={"include_tasks": True, "include_users": True}
    ),
    "productivity_analysis": ReportTemplate(
        id="productivity_analysis",
        name="Productivity Analysis",
        description="Analysis of productive hours, trends, and patterns",
        report_type=ReportType.PRODUCTIVITY_ANALYSIS,
        default_params={"compare_periods": True, "show_averages": True}
    ),
    "user_activity": ReportTemplate(
        id="user_activity",
        name="User Activity Report",
        description="Individual user time tracking activity",
        report_type=ReportType.USER_ACTIVITY,
        default_params={"include_breakdown": True}
    ),
    "team_comparison": ReportTemplate(
        id="team_comparison",
        name="Team Comparison",
        description="Compare time tracking across team members",
        report_type=ReportType.TEAM_COMPARISON,
        default_params={"include_averages": True}
    ),
    "billable_hours": ReportTemplate(
        id="billable_hours",
        name="Billable Hours Report",
        description="Summary of billable vs non-billable hours",
        report_type=ReportType.BILLABLE_HOURS,
        default_params={"include_rates": True}
    )
}


class ReportService:
    """Service for generating reports from templates"""
    
    @staticmethod
    def get_templates() -> List[Dict]:
        """Get all available report templates"""
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "type": t.report_type.value,
                "default_params": t.default_params
            }
            for t in REPORT_TEMPLATES.values()
        ]
    
    @staticmethod
    def get_template(template_id: str) -> Optional[ReportTemplate]:
        """Get a specific template by ID"""
        return REPORT_TEMPLATES.get(template_id)
    
    @staticmethod
    async def generate_weekly_summary(
        db: AsyncSession,
        user_id: Optional[int] = None,
        week_offset: int = 0
    ) -> Dict:
        """Generate weekly summary report"""
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday() + (7 * week_offset))
        end_of_week = start_of_week + timedelta(days=6)
        
        query = select(
            func.date(TimeEntry.start_time).label('day'),
            func.sum(TimeEntry.duration_seconds).label('total_seconds')
        ).where(
            and_(
                func.date(TimeEntry.start_time) >= start_of_week,
                func.date(TimeEntry.start_time) <= end_of_week
            )
        )
        
        if user_id:
            query = query.where(TimeEntry.user_id == user_id)
        
        query = query.group_by(func.date(TimeEntry.start_time))
        
        result = await db.execute(query)
        daily_data = result.all()
        
        return {
            "report_type": "weekly_summary",
            "period": {
                "start": start_of_week.isoformat(),
                "end": end_of_week.isoformat()
            },
            "data": {
                "daily_hours": [
                    {"date": str(row.day), "hours": round((row.total_seconds or 0) / 3600, 2)}
                    for row in daily_data
                ],
                "total_hours": round(sum((row.total_seconds or 0) for row in daily_data) / 3600, 2)
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def generate_monthly_summary(
        db: AsyncSession,
        user_id: Optional[int] = None,
        year: int = None,
        month: int = None
    ) -> Dict:
        """Generate monthly summary report"""
        if not year:
            year = date.today().year
        if not month:
            month = date.today().month
        
        start_of_month = date(year, month, 1)
        if month == 12:
            end_of_month = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = date(year, month + 1, 1) - timedelta(days=1)
        
        # Get project breakdown
        query = select(
            Project.name.label('project_name'),
            func.sum(TimeEntry.duration_seconds).label('total_seconds')
        ).join(
            TimeEntry, TimeEntry.project_id == Project.id
        ).where(
            and_(
                func.date(TimeEntry.start_time) >= start_of_month,
                func.date(TimeEntry.start_time) <= end_of_month
            )
        ).group_by(Project.name)
        
        if user_id:
            query = query.where(TimeEntry.user_id == user_id)
        
        result = await db.execute(query)
        project_data = result.all()
        
        return {
            "report_type": "monthly_summary",
            "period": {
                "year": year,
                "month": month,
                "start": start_of_month.isoformat(),
                "end": end_of_month.isoformat()
            },
            "data": {
                "by_project": [
                    {"project": row.project_name, "hours": round((row.total_seconds or 0) / 3600, 2)}
                    for row in project_data
                ],
                "total_hours": round(sum((row.total_seconds or 0) for row in project_data) / 3600, 2)
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def generate_project_breakdown(
        db: AsyncSession,
        project_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """Generate project breakdown report"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Get project info
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        
        if not project:
            return {"error": "Project not found"}
        
        # Get user breakdown
        query = select(
            User.full_name.label('user_name'),
            func.sum(TimeEntry.duration_seconds).label('total_seconds')
        ).join(
            TimeEntry, TimeEntry.user_id == User.id
        ).where(
            and_(
                TimeEntry.project_id == project_id,
                func.date(TimeEntry.start_time) >= start_date,
                func.date(TimeEntry.start_time) <= end_date
            )
        ).group_by(User.full_name)
        
        result = await db.execute(query)
        user_data = result.all()
        
        return {
            "report_type": "project_breakdown",
            "project": {
                "id": project.id,
                "name": project.name
            },
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "data": {
                "by_user": [
                    {"user": row.user_name or "Unknown", "hours": round((row.total_seconds or 0) / 3600, 2)}
                    for row in user_data
                ],
                "total_hours": round(sum((row.total_seconds or 0) for row in user_data) / 3600, 2)
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def generate_productivity_analysis(
        db: AsyncSession,
        user_id: Optional[int] = None,
        days: int = 30
    ) -> Dict:
        """Generate productivity analysis report"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        query = select(
            func.date(TimeEntry.start_time).label('day'),
            func.sum(TimeEntry.duration_seconds).label('total_seconds'),
            func.count(TimeEntry.id).label('entry_count')
        ).where(
            func.date(TimeEntry.start_time) >= start_date
        ).group_by(func.date(TimeEntry.start_time))
        
        if user_id:
            query = query.where(TimeEntry.user_id == user_id)
        
        result = await db.execute(query)
        daily_data = result.all()
        
        total_hours = sum((row.total_seconds or 0) / 3600 for row in daily_data)
        days_worked = len([d for d in daily_data if (d.total_seconds or 0) > 0])
        
        return {
            "report_type": "productivity_analysis",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            },
            "data": {
                "total_hours": round(total_hours, 2),
                "days_worked": days_worked,
                "avg_hours_per_day": round(total_hours / max(days_worked, 1), 2),
                "total_entries": sum(row.entry_count for row in daily_data),
                "daily_breakdown": [
                    {
                        "date": str(row.day),
                        "hours": round((row.total_seconds or 0) / 3600, 2),
                        "entries": row.entry_count
                    }
                    for row in daily_data
                ]
            },
            "generated_at": datetime.utcnow().isoformat()
        }


