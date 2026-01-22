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
    # Multi-tenancy: ALWAYS filter by user's company (strict isolation)
    company_id = current_user.company_id
    
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
    # Multi-tenancy: ALWAYS filter by user's company (strict isolation)
    company_id = current_user.company_id
    
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
    # Multi-tenancy: ALWAYS filter by user's company (strict isolation)
    company_id = current_user.company_id
    
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


@router.get("/payslip/pdf/{user_id}/{period_id}")
async def generate_payslip_pdf(
    user_id: int,
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a PDF payslip for a specific user and period.
    Users can download their own payslip, admins can download anyone's.
    """
    from app.services.payslip_pdf_service import payslip_generator
    from app.models import PayrollPeriod, Company
    from sqlalchemy import select
    
    # Permission check
    if current_user.role not in ["super_admin", "admin", "company_admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only download your own payslip"
        )
    
    service = PayrollReportService(db)
    reports = await service.get_user_payroll_report(user_id, period_id)
    
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll entry not found for this user and period"
        )
    
    report = reports[0]
    
    # Get company info for the payslip header
    company_name = "Time Tracker"
    company_address = None
    if current_user.company_id:
        stmt = select(Company).where(Company.id == current_user.company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()
        if company:
            company_name = company.name
            # Use custom domain or build address from available info
            company_address = getattr(company, 'address', None)
    
    # Convert adjustments to dict format
    adjustments = [
        {
            'adjustment_type': adj.adjustment_type,
            'description': adj.description,
            'amount': adj.amount
        }
        for adj in report.adjustments
    ]
    
    # Generate PDF
    pdf_bytes = payslip_generator.generate_payslip(
        employee_name=report.user_name,
        employee_email=report.user_email,
        employee_id=report.user_id,
        period_name=report.period_name,
        period_start=report.start_date,
        period_end=report.end_date,
        regular_hours=report.regular_hours,
        overtime_hours=report.overtime_hours,
        regular_rate=report.regular_rate,
        overtime_rate=report.overtime_rate,
        gross_amount=report.gross_amount,
        adjustments=adjustments,
        adjustments_total=report.adjustments_total,
        net_amount=report.net_amount,
        company_name=company_name,
        company_address=company_address,
    )
    
    filename = f"payslip_{report.user_name.replace(' ', '_')}_{report.period_name.replace(' ', '_')}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/my-payslip/pdf/{period_id}")
async def download_my_payslip_pdf(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download current user's own payslip as PDF.
    Available to all authenticated users.
    """
    from app.services.payslip_pdf_service import payslip_generator
    from app.models import Company
    from sqlalchemy import select
    
    service = PayrollReportService(db)
    reports = await service.get_user_payroll_report(current_user.id, period_id)
    
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payroll entry found for this period"
        )
    
    report = reports[0]
    
    # Get company info
    company_name = "Time Tracker"
    company_address = None
    if current_user.company_id:
        stmt = select(Company).where(Company.id == current_user.company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()
        if company:
            company_name = company.name
    
    # Convert adjustments
    adjustments = [
        {
            'adjustment_type': adj.adjustment_type,
            'description': adj.description,
            'amount': adj.amount
        }
        for adj in report.adjustments
    ]
    
    # Generate PDF
    pdf_bytes = payslip_generator.generate_payslip(
        employee_name=report.user_name,
        employee_email=report.user_email,
        employee_id=report.user_id,
        period_name=report.period_name,
        period_start=report.start_date,
        period_end=report.end_date,
        regular_hours=report.regular_hours,
        overtime_hours=report.overtime_hours,
        regular_rate=report.regular_rate,
        overtime_rate=report.overtime_rate,
        gross_amount=report.gross_amount,
        adjustments=adjustments,
        adjustments_total=report.adjustments_total,
        net_amount=report.net_amount,
        company_name=company_name,
        company_address=company_address,
    )
    
    filename = f"payslip_{report.period_name.replace(' ', '_')}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )





