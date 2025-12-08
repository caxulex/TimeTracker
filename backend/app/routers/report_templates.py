"""
Reports Templates Router - TASK-030 & TASK-031
Endpoints for report templates and scheduled reports
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from app.database import get_db
from app.models import User
from app.dependencies import get_current_user, require_role
from app.services.report_templates import ReportService, ReportType
from app.services.scheduled_reports import ScheduledReportService, ScheduleFrequency

router = APIRouter()


# Request/Response models
class GenerateReportRequest(BaseModel):
    template_id: str
    params: Optional[dict] = None


class ScheduledReportCreate(BaseModel):
    name: str
    template_id: str
    frequency: str  # daily, weekly, monthly
    recipients: List[str]
    params: Optional[dict] = None


class ScheduledReportUpdate(BaseModel):
    name: Optional[str] = None
    frequency: Optional[str] = None
    recipients: Optional[List[str]] = None
    enabled: Optional[bool] = None
    params: Optional[dict] = None


# Report Templates Endpoints
@router.get("/templates")
async def list_templates(
    current_user: User = Depends(get_current_user)
):
    """Get all available report templates"""
    return ReportService.get_templates()


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific report template"""
    template = ReportService.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "type": template.report_type.value,
        "default_params": template.default_params
    }


@router.post("/generate/weekly")
async def generate_weekly_report(
    user_id: Optional[int] = Query(None),
    week_offset: int = Query(0, description="0 for current week, 1 for last week, etc."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a weekly summary report"""
    # Users can only generate their own reports unless admin/manager
    if user_id and user_id != current_user.id and current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Cannot generate reports for other users")
    
    target_user_id = user_id or current_user.id
    return await ReportService.generate_weekly_summary(db, target_user_id, week_offset)


@router.post("/generate/monthly")
async def generate_monthly_report(
    user_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a monthly summary report"""
    if user_id and user_id != current_user.id and current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Cannot generate reports for other users")
    
    target_user_id = user_id or current_user.id
    return await ReportService.generate_monthly_summary(db, target_user_id, year, month)


@router.post("/generate/project/{project_id}")
async def generate_project_report(
    project_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Generate a project breakdown report"""
    return await ReportService.generate_project_breakdown(db, project_id, start_date, end_date)


@router.post("/generate/productivity")
async def generate_productivity_report(
    user_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a productivity analysis report"""
    if user_id and user_id != current_user.id and current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Cannot generate reports for other users")
    
    target_user_id = user_id or current_user.id
    return await ReportService.generate_productivity_analysis(db, target_user_id, days)


# Scheduled Reports Endpoints
@router.get("/scheduled")
async def list_scheduled_reports(
    current_user: User = Depends(get_current_user)
):
    """Get all scheduled reports for the current user"""
    reports = ScheduledReportService.get_user_scheduled_reports(current_user.id)
    return [r.to_dict() for r in reports]


@router.get("/scheduled/all")
async def list_all_scheduled_reports(
    current_user: User = Depends(require_role(["admin"]))
):
    """Get all scheduled reports (admin only)"""
    reports = ScheduledReportService.get_all_scheduled_reports()
    return [r.to_dict() for r in reports]


@router.post("/scheduled")
async def create_scheduled_report(
    request: ScheduledReportCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new scheduled report"""
    # Validate template exists
    template = ReportService.get_template(request.template_id)
    if not template:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    # Validate frequency
    if request.frequency not in [f.value for f in ScheduleFrequency]:
        raise HTTPException(status_code=400, detail="Invalid frequency")
    
    report = ScheduledReportService.create_scheduled_report(
        name=request.name,
        template_id=request.template_id,
        frequency=request.frequency,
        recipients=request.recipients,
        user_id=current_user.id,
        params=request.params
    )
    
    return report.to_dict()


@router.get("/scheduled/{report_id}")
async def get_scheduled_report(
    report_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a scheduled report by ID"""
    report = ScheduledReportService.get_scheduled_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    
    # Check ownership
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    return report.to_dict()


@router.patch("/scheduled/{report_id}")
async def update_scheduled_report(
    report_id: str,
    request: ScheduledReportUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a scheduled report"""
    report = ScheduledReportService.get_scheduled_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    updated = ScheduledReportService.update_scheduled_report(
        report_id=report_id,
        name=request.name,
        frequency=request.frequency,
        recipients=request.recipients,
        enabled=request.enabled,
        params=request.params
    )
    
    return updated.to_dict()


@router.delete("/scheduled/{report_id}")
async def delete_scheduled_report(
    report_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a scheduled report"""
    report = ScheduledReportService.get_scheduled_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    ScheduledReportService.delete_scheduled_report(report_id)
    return {"message": "Scheduled report deleted"}


@router.post("/scheduled/{report_id}/toggle")
async def toggle_scheduled_report(
    report_id: str,
    current_user: User = Depends(get_current_user)
):
    """Toggle a scheduled report on/off"""
    report = ScheduledReportService.get_scheduled_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    updated = ScheduledReportService.toggle_report(report_id)
    return {"enabled": updated.enabled}


@router.get("/scheduled/history")
async def get_report_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """Get report sending history for the current user"""
    return ScheduledReportService.get_report_history(current_user.id, limit)








