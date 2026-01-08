"""
API Router for Payroll Reports
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas.payroll import (
    PayrollReportFilters,
    PayrollSummaryReport,
    UserPayrollReport,
    PayablesDepartmentReport,
    PeriodStatusEnum,
    PeriodTypeEnum
)
from app.services.payroll_report_service import PayrollReportService


router = APIRouter(prefix="/api/payroll/reports", tags=["Payroll Reports"])


@router.get("/summary/{period_id}", response_model=PayrollSummaryReport)
async def get_period_summary(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get summary report for a specific payroll period.
    Admin only.
    """
    service = PayrollReportService(db)
    summary = await service.get_period_summary(period_id)
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll period not found"
        )
    
    return summary


@router.get("/user/{user_id}", response_model=list)
async def get_user_report(
    user_id: int,
    period_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get payroll report for a specific user.
    Users can view their own report, admins can view anyone's.
    """
    if current_user.role not in ["super_admin", "admin", "company_admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own payroll report"
        )
    
    service = PayrollReportService(db)
    reports = await service.get_user_payroll_report(user_id, period_id, start_date, end_date)
    return reports


@router.post("/payables", response_model=PayablesDepartmentReport)
async def get_payables_report(
    filters: PayrollReportFilters,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Generate comprehensive report for payables department.
    Admin only. Filtered by company for non-super admins.
    """
    # Set company_id filter for non-super admins
    if current_user.role != 'super_admin':
        filters.company_id = current_user.company_id
    
    service = PayrollReportService(db)
    report = await service.get_payables_report(filters)
    return report


@router.get("/payables", response_model=PayablesDepartmentReport)
async def get_payables_report_query(
    period_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    status: Optional[PeriodStatusEnum] = Query(None),
    period_type: Optional[PeriodTypeEnum] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Generate comprehensive report for payables department using query parameters.
    Admin only. Filtered by company for non-super admins.
    """
    # Set company_id filter for non-super admins
    company_id = None if current_user.role == 'super_admin' else current_user.company_id
    
    filters = PayrollReportFilters(
        period_id=period_id,
        user_id=user_id,
        status=status,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
        company_id=company_id
    )
    
    service = PayrollReportService(db)
    report = await service.get_payables_report(filters)
    return report


@router.get("/payables/export/csv")
async def export_payables_csv(
    period_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    status: Optional[PeriodStatusEnum] = Query(None),
    period_type: Optional[PeriodTypeEnum] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Export payables report as CSV.
    Admin only. Filtered by company for non-super admins.
    """
    # Set company_id filter for non-super admins
    company_id = None if current_user.role == 'super_admin' else current_user.company_id
    
    filters = PayrollReportFilters(
        period_id=period_id,
        user_id=user_id,
        status=status,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
        company_id=company_id
    )
    
    service = PayrollReportService(db)
    report = await service.get_payables_report(filters)
    csv_content = await service.export_to_csv(report)
    
    filename = f"payroll_report_{date.today().isoformat()}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/payables/export/excel")
async def export_payables_excel(
    period_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    status: Optional[PeriodStatusEnum] = Query(None),
    period_type: Optional[PeriodTypeEnum] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Export payables report as Excel file.
    Admin only. Filtered by company for non-super admins.
    """
    # Set company_id filter for non-super admins
    company_id = None if current_user.role == 'super_admin' else current_user.company_id
    
    filters = PayrollReportFilters(
        period_id=period_id,
        user_id=user_id,
        status=status,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
        company_id=company_id
    )
    
    service = PayrollReportService(db)
    
    try:
        report = await service.get_payables_report(filters)
        excel_content = await service.export_to_excel(report)
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Excel export not available. Install openpyxl: pip install openpyxl"
        )
    
    filename = f"payroll_report_{date.today().isoformat()}.xlsx"
    
    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/my-payroll", response_model=list)
async def get_my_payroll_report(
    period_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's own payroll report.
    Available to all authenticated users.
    """
    service = PayrollReportService(db)
    reports = await service.get_user_payroll_report(current_user.id, period_id, start_date, end_date)
    return reports





