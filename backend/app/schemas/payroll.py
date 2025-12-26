"""
Pydantic schemas for Payroll-related models
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================
# ENUMS
# ============================================

class RateTypeEnum(str, Enum):
    """Pay rate type enumeration"""
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    PROJECT_BASED = "project_based"


class PeriodTypeEnum(str, Enum):
    """Payroll period type enumeration"""
    WEEKLY = "weekly"
    BI_WEEKLY = "bi_weekly"
    SEMI_MONTHLY = "semi_monthly"
    MONTHLY = "monthly"


class PeriodStatusEnum(str, Enum):
    """Payroll period status enumeration"""
    DRAFT = "draft"
    PROCESSING = "processing"
    APPROVED = "approved"
    PAID = "paid"
    VOID = "void"


class EntryStatusEnum(str, Enum):
    """Payroll entry status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"


class AdjustmentTypeEnum(str, Enum):
    """Payroll adjustment type enumeration"""
    BONUS = "bonus"
    DEDUCTION = "deduction"
    REIMBURSEMENT = "reimbursement"
    TAX = "tax"
    OTHER = "other"


# ============================================
# PAY RATE SCHEMAS
# ============================================

class PayRateBase(BaseModel):
    """Base schema for pay rate"""
    rate_type: RateTypeEnum = RateTypeEnum.HOURLY
    base_rate: Decimal = Field(..., ge=0, decimal_places=2)
    currency: str = Field(default="USD", max_length=3)
    overtime_multiplier: Decimal = Field(default=Decimal("1.5"), ge=1, decimal_places=2)
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = True


class PayRateCreate(PayRateBase):
    """Schema for creating a pay rate"""
    user_id: int


class PayRateUpdate(BaseModel):
    """Schema for updating a pay rate"""
    rate_type: Optional[RateTypeEnum] = None
    base_rate: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    overtime_multiplier: Optional[Decimal] = Field(None, ge=1)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_active: Optional[bool] = None
    change_reason: Optional[str] = None  # For history tracking


class PayRateResponse(PayRateBase):
    """Schema for pay rate response"""
    id: int
    user_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PayRateWithUser(PayRateResponse):
    """Schema for pay rate with user details"""
    user_name: Optional[str] = None
    user_email: Optional[str] = None


# ============================================
# PAY RATE HISTORY SCHEMAS
# ============================================

class PayRateHistoryBase(BaseModel):
    """Base schema for pay rate history"""
    previous_rate: Decimal
    new_rate: Decimal
    previous_overtime_multiplier: Optional[Decimal] = None
    new_overtime_multiplier: Optional[Decimal] = None
    change_reason: Optional[str] = None


class PayRateHistoryResponse(PayRateHistoryBase):
    """Schema for pay rate history response"""
    id: int
    pay_rate_id: int
    changed_by: int
    changed_at: datetime
    changed_by_name: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================
# PAYROLL PERIOD SCHEMAS
# ============================================

class PayrollPeriodBase(BaseModel):
    """Base schema for payroll period"""
    name: str = Field(..., max_length=255)
    period_type: PeriodTypeEnum = PeriodTypeEnum.MONTHLY
    start_date: date
    end_date: date

    @validator('end_date')
    def end_date_must_be_after_start(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class PayrollPeriodCreate(PayrollPeriodBase):
    """Schema for creating a payroll period"""
    pass


class PayrollPeriodUpdate(BaseModel):
    """Schema for updating a payroll period"""
    name: Optional[str] = Field(None, max_length=255)
    period_type: Optional[PeriodTypeEnum] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[PeriodStatusEnum] = None


class PayrollPeriodResponse(PayrollPeriodBase):
    """Schema for payroll period response"""
    id: int
    status: PeriodStatusEnum
    total_amount: Decimal
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    entries_count: int = 0

    class Config:
        from_attributes = True


class PayrollPeriodWithEntries(PayrollPeriodResponse):
    """Schema for payroll period with entries"""
    entries: List["PayrollEntryWithUser"] = []


# ============================================
# PAYROLL ENTRY SCHEMAS
# ============================================

class PayrollEntryBase(BaseModel):
    """Base schema for payroll entry"""
    regular_hours: Decimal = Field(default=Decimal("0.00"), ge=0)
    overtime_hours: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: Optional[str] = None


class PayrollEntryCreate(PayrollEntryBase):
    """Schema for creating a payroll entry"""
    payroll_period_id: int
    user_id: int


class PayrollEntryUpdate(BaseModel):
    """Schema for updating a payroll entry"""
    regular_hours: Optional[Decimal] = Field(None, ge=0)
    overtime_hours: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    status: Optional[EntryStatusEnum] = None


class PayrollEntryResponse(PayrollEntryBase):
    """Schema for payroll entry response"""
    id: int
    payroll_period_id: int
    user_id: int
    regular_rate: Decimal
    overtime_rate: Decimal
    gross_amount: Decimal
    adjustments_amount: Decimal
    net_amount: Decimal
    status: EntryStatusEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PayrollEntryWithUser(PayrollEntryResponse):
    """Schema for payroll entry with user details"""
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    rate_type: Optional[str] = None  # hourly, daily, monthly, project_based


class PayrollEntryWithAdjustments(PayrollEntryWithUser):
    """Schema for payroll entry with adjustments"""
    adjustments: List["PayrollAdjustmentResponse"] = []


# ============================================
# PAYROLL ADJUSTMENT SCHEMAS
# ============================================

class PayrollAdjustmentBase(BaseModel):
    """Base schema for payroll adjustment"""
    adjustment_type: AdjustmentTypeEnum
    description: str = Field(..., max_length=500)
    amount: Decimal  # Can be positive or negative


class PayrollAdjustmentCreate(PayrollAdjustmentBase):
    """Schema for creating a payroll adjustment"""
    payroll_entry_id: int


class PayrollAdjustmentUpdate(BaseModel):
    """Schema for updating a payroll adjustment"""
    adjustment_type: Optional[AdjustmentTypeEnum] = None
    description: Optional[str] = Field(None, max_length=500)
    amount: Optional[Decimal] = None


class PayrollAdjustmentResponse(PayrollAdjustmentBase):
    """Schema for payroll adjustment response"""
    id: int
    payroll_entry_id: int
    created_by: int
    created_at: datetime
    created_by_name: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================
# REPORT SCHEMAS
# ============================================

class PayrollSummaryReport(BaseModel):
    """Schema for payroll summary report"""
    period_id: int
    period_name: str
    start_date: date
    end_date: date
    status: str
    total_employees: int
    total_regular_hours: Decimal
    total_overtime_hours: Decimal
    total_gross_amount: Decimal
    total_adjustments: Decimal
    total_net_amount: Decimal


class UserPayrollReport(BaseModel):
    """Schema for individual user payroll report"""
    user_id: int
    user_name: str
    user_email: str
    period_name: str
    start_date: date
    end_date: date
    regular_hours: Decimal
    overtime_hours: Decimal
    regular_rate: Decimal
    overtime_rate: Decimal
    gross_amount: Decimal
    adjustments: List[PayrollAdjustmentResponse]
    adjustments_total: Decimal
    net_amount: Decimal


class PayrollReportFilters(BaseModel):
    """Schema for payroll report filters"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    period_id: Optional[int] = None
    user_id: Optional[int] = None
    status: Optional[PeriodStatusEnum] = None
    period_type: Optional[PeriodTypeEnum] = None


class PayablesDepartmentReport(BaseModel):
    """Schema for payables department report"""
    report_generated_at: datetime
    report_period: str
    filters_applied: PayrollReportFilters
    summary: PayrollSummaryReport
    entries: List[UserPayrollReport]


# Update forward references
PayrollPeriodWithEntries.model_rebuild()
PayrollEntryWithAdjustments.model_rebuild()
