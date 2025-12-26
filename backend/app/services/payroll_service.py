"""
Service layer for Payroll operations
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    User, PayRate, PayRateHistory, PayrollPeriod, 
    PayrollEntry, PayrollAdjustment, TimeEntry
)
from app.schemas.payroll import (
    PayRateCreate, PayRateUpdate,
    PayrollPeriodCreate, PayrollPeriodUpdate,
    PayrollEntryCreate, PayrollEntryUpdate,
    PayrollAdjustmentCreate, PayrollAdjustmentUpdate,
    PayrollReportFilters, PeriodStatusEnum, EntryStatusEnum
)


class PayRateService:
    """Service for managing pay rates"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_pay_rate(
        self, 
        pay_rate_data: PayRateCreate, 
        created_by_id: int
    ) -> PayRate:
        """Create a new pay rate for a user"""
        # Deactivate existing active rates for this user
        stmt = select(PayRate).where(
            and_(
                PayRate.user_id == pay_rate_data.user_id,
                PayRate.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        existing_rates = result.scalars().all()
        
        for rate in existing_rates:
            if rate.effective_to is None:
                rate.effective_to = pay_rate_data.effective_from
        
        pay_rate = PayRate(
            user_id=pay_rate_data.user_id,
            rate_type=pay_rate_data.rate_type.value,
            base_rate=pay_rate_data.base_rate,
            currency=pay_rate_data.currency,
            overtime_multiplier=pay_rate_data.overtime_multiplier,
            effective_from=pay_rate_data.effective_from,
            effective_to=pay_rate_data.effective_to,
            is_active=pay_rate_data.is_active,
            created_by=created_by_id
        )
        self.db.add(pay_rate)
        await self.db.commit()
        await self.db.refresh(pay_rate)
        return pay_rate
    
    async def get_pay_rate(self, pay_rate_id: int) -> Optional[PayRate]:
        """Get a pay rate by ID"""
        stmt = select(PayRate).where(PayRate.id == pay_rate_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_active_rate(
        self, 
        user_id: int, 
        as_of_date: Optional[date] = None
    ) -> Optional[PayRate]:
        """Get the active pay rate for a user as of a specific date"""
        if as_of_date is None:
            as_of_date = date.today()
        
        stmt = select(PayRate).where(
            and_(
                PayRate.user_id == user_id,
                PayRate.is_active == True,
                PayRate.effective_from <= as_of_date,
                (PayRate.effective_to.is_(None) | (PayRate.effective_to >= as_of_date))
            )
        ).order_by(PayRate.effective_from.desc()).limit(1)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_pay_rates(
        self, 
        user_id: int,
        include_inactive: bool = False
    ) -> List[PayRate]:
        """Get all pay rates for a user"""
        conditions = [PayRate.user_id == user_id]
        if not include_inactive:
            conditions.append(PayRate.is_active == True)
        
        stmt = select(PayRate).where(and_(*conditions)).order_by(PayRate.effective_from.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_all_pay_rates(
        self, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = True
    ) -> Tuple[List[PayRate], int]:
        """Get all pay rates with pagination"""
        conditions = []
        if active_only:
            conditions.append(PayRate.is_active == True)
        
        # Get total count
        count_stmt = select(func.count(PayRate.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        # Get paginated results
        stmt = select(PayRate).options(selectinload(PayRate.user))
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(PayRate.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
    
    async def update_pay_rate(
        self,
        pay_rate_id: int,
        pay_rate_data: PayRateUpdate,
        changed_by_id: int
    ) -> Optional[PayRate]:
        """Update a pay rate and create history record"""
        pay_rate = await self.get_pay_rate(pay_rate_id)
        if not pay_rate:
            return None
        
        # Create history record if rate changed
        if pay_rate_data.base_rate is not None or pay_rate_data.overtime_multiplier is not None:
            history = PayRateHistory(
                pay_rate_id=pay_rate_id,
                previous_rate=pay_rate.base_rate,
                new_rate=pay_rate_data.base_rate or pay_rate.base_rate,
                previous_overtime_multiplier=pay_rate.overtime_multiplier,
                new_overtime_multiplier=pay_rate_data.overtime_multiplier or pay_rate.overtime_multiplier,
                changed_by=changed_by_id,
                change_reason=pay_rate_data.change_reason
            )
            self.db.add(history)
        
        # Update fields
        update_data = pay_rate_data.model_dump(exclude_unset=True, exclude={'change_reason'})
        for field, value in update_data.items():
            if value is not None:
                if field == 'rate_type':
                    setattr(pay_rate, field, value.value)
                else:
                    setattr(pay_rate, field, value)
        
        await self.db.commit()
        await self.db.refresh(pay_rate)
        return pay_rate
    
    async def delete_pay_rate(self, pay_rate_id: int) -> bool:
        """Soft delete a pay rate"""
        pay_rate = await self.get_pay_rate(pay_rate_id)
        if not pay_rate:
            return False
        
        pay_rate.is_active = False
        pay_rate.effective_to = date.today()
        await self.db.commit()
        return True
    
    async def get_pay_rate_history(self, pay_rate_id: int) -> List[PayRateHistory]:
        """Get history for a pay rate"""
        stmt = select(PayRateHistory).where(
            PayRateHistory.pay_rate_id == pay_rate_id
        ).order_by(PayRateHistory.changed_at.desc())
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class PayrollPeriodService:
    """Service for managing payroll periods"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pay_rate_service = PayRateService(db)
    
    async def create_period(self, period_data: PayrollPeriodCreate) -> PayrollPeriod:
        """Create a new payroll period with optional employee selection criteria"""
        # Convert user_ids list to comma-separated string for storage
        selected_user_ids = None
        if period_data.user_ids and len(period_data.user_ids) > 0:
            selected_user_ids = ','.join(str(uid) for uid in period_data.user_ids)
        
        # Get rate type filter value
        rate_type_filter = None
        if period_data.rate_type_filter:
            rate_type_filter = period_data.rate_type_filter.value
        
        period = PayrollPeriod(
            name=period_data.name,
            period_type=period_data.period_type.value,
            start_date=period_data.start_date,
            end_date=period_data.end_date,
            status=PeriodStatusEnum.DRAFT.value,
            selected_user_ids=selected_user_ids,
            rate_type_filter=rate_type_filter
        )
        self.db.add(period)
        await self.db.commit()
        await self.db.refresh(period)
        return period
    
    async def get_period(self, period_id: int) -> Optional[PayrollPeriod]:
        """Get a payroll period by ID"""
        stmt = select(PayrollPeriod).where(PayrollPeriod.id == period_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_period_with_entries(self, period_id: int) -> Optional[PayrollPeriod]:
        """Get a payroll period with all entries"""
        stmt = select(PayrollPeriod).options(
            selectinload(PayrollPeriod.entries).selectinload(PayrollEntry.user),
            selectinload(PayrollPeriod.entries).selectinload(PayrollEntry.adjustments)
        ).where(PayrollPeriod.id == period_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_periods(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[PeriodStatusEnum] = None
    ) -> Tuple[List[PayrollPeriod], int]:
        """Get all payroll periods with pagination"""
        conditions = []
        if status:
            conditions.append(PayrollPeriod.status == status.value)
        
        # Get total count
        count_stmt = select(func.count(PayrollPeriod.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        # Get paginated results
        stmt = select(PayrollPeriod)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(PayrollPeriod.start_date.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
    
    async def update_period(
        self,
        period_id: int,
        period_data: PayrollPeriodUpdate
    ) -> Optional[PayrollPeriod]:
        """Update a payroll period"""
        period = await self.get_period(period_id)
        if not period:
            return None
        
        update_data = period_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if field in ('status', 'period_type'):
                    setattr(period, field, value.value)
                else:
                    setattr(period, field, value)
        
        await self.db.commit()
        await self.db.refresh(period)
        return period
    
    async def process_period(self, period_id: int) -> Optional[PayrollPeriod]:
        """Process a payroll period - calculate all entries based on pay rate type and selection criteria"""
        period = await self.get_period_with_entries(period_id)
        if not period or period.status != PeriodStatusEnum.DRAFT.value:
            return None
        
        period.status = PeriodStatusEnum.PROCESSING.value
        
        # Calculate period duration for prorating
        period_days = (period.end_date - period.start_date).days + 1
        
        # Calculate overtime threshold based on period type (for hourly workers)
        # Standard is 40 hours/week
        period_weeks = {
            'weekly': Decimal("1"),
            'bi_weekly': Decimal("2"),
            'semi_monthly': Decimal("2.17"),  # ~2.17 weeks in semi-monthly
            'monthly': Decimal("4.33"),  # ~4.33 weeks in a month
        }
        weeks_in_period = period_weeks.get(period.period_type, Decimal("2"))
        overtime_threshold = Decimal("40") * weeks_in_period
        
        # Parse selection criteria from the period
        selected_user_ids = None
        if period.selected_user_ids:
            selected_user_ids = [int(uid.strip()) for uid in period.selected_user_ids.split(',') if uid.strip()]
        
        rate_type_filter = period.rate_type_filter  # e.g., 'hourly', 'monthly', etc.
        
        # Build query for users with active pay rates
        conditions = [PayRate.is_active == True, User.is_active == True]
        
        # Filter by specific user IDs if provided
        if selected_user_ids:
            conditions.append(User.id.in_(selected_user_ids))
        
        # Filter by rate type if provided
        if rate_type_filter:
            conditions.append(PayRate.rate_type == rate_type_filter)
        
        stmt = select(User).join(PayRate, User.id == PayRate.user_id).where(
            and_(*conditions)
        ).distinct()
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        total_amount = Decimal("0.00")
        entries_processed = 0
        
        for user in users:
            # Get active pay rate for the period end date
            pay_rate = await self.pay_rate_service.get_user_active_rate(user.id, period.end_date)
            if not pay_rate:
                continue
            
            # Double-check rate type filter (in case user has multiple rates)
            if rate_type_filter and pay_rate.rate_type != rate_type_filter:
                continue
            
            # Get user's time entries for this period (needed for hourly/daily calculations)
            time_stmt = select(TimeEntry).where(
                and_(
                    TimeEntry.user_id == user.id,
                    TimeEntry.start_time >= datetime.combine(period.start_date, datetime.min.time()),
                    TimeEntry.start_time <= datetime.combine(period.end_date, datetime.max.time()),
                    TimeEntry.is_running == False
                )
            )
            time_result = await self.db.execute(time_stmt)
            time_entries = time_result.scalars().all()
            
            # Calculate based on rate type
            rate_type = pay_rate.rate_type.lower() if pay_rate.rate_type else 'hourly'
            
            if rate_type == 'monthly':
                # MONTHLY SALARY CALCULATION
                # =========================
                # Monthly rate = base salary per month
                # To calculate per-period pay, we convert to annual then divide by periods/year
                # This ensures the annual total is always correct regardless of period type
                #
                # Period Types and their frequencies:
                # - weekly:       52 periods/year  → Annual ÷ 52 per paycheck
                # - bi_weekly:    26 periods/year  → Annual ÷ 26 per paycheck (every 2 weeks)
                # - semi_monthly: 24 periods/year  → Annual ÷ 24 per paycheck (twice per month, e.g., 1st & 15th)
                # - monthly:      12 periods/year  → Annual ÷ 12 per paycheck (full monthly salary)
                #
                # Example: $1,200/month salary = $14,400/year
                # - Weekly:       $14,400 ÷ 52 = $276.92/paycheck
                # - Bi-Weekly:    $14,400 ÷ 26 = $553.85/paycheck  
                # - Semi-Monthly: $14,400 ÷ 24 = $600.00/paycheck
                # - Monthly:      $14,400 ÷ 12 = $1,200.00/paycheck
                
                periods_per_year = {
                    'weekly': Decimal("52"),        # Paid every week
                    'bi_weekly': Decimal("26"),     # Paid every 2 weeks
                    'semi_monthly': Decimal("24"),  # Paid twice per month (fixed dates)
                    'monthly': Decimal("12"),       # Paid once per month
                }
                
                annual_salary = pay_rate.base_rate * Decimal("12")
                periods = periods_per_year.get(period.period_type, Decimal("12"))
                gross_amount = (annual_salary / periods).quantize(Decimal("0.01"))
                
                regular_hours = Decimal("0")  # Hours not tracked for salaried employees
                overtime_hours = Decimal("0")
                regular_rate = pay_rate.base_rate
                overtime_rate = pay_rate.base_rate  # No overtime for monthly salary
                    
            elif rate_type == 'daily':
                # Daily rate - calculate based on days worked (time entries)
                # Count unique days with time entries
                worked_days = set()
                for te in time_entries:
                    worked_days.add(te.start_time.date())
                days_worked = Decimal(len(worked_days))
                
                gross_amount = days_worked * pay_rate.base_rate
                regular_hours = days_worked * Decimal("8")  # Assume 8 hours/day for display
                overtime_hours = Decimal("0")
                regular_rate = pay_rate.base_rate / Decimal("8")  # Convert to hourly for display
                overtime_rate = regular_rate * pay_rate.overtime_multiplier
                
            elif rate_type == 'project_based':
                # Project-based - pay the agreed amount
                gross_amount = pay_rate.base_rate
                regular_hours = Decimal("0")
                overtime_hours = Decimal("0")
                regular_rate = pay_rate.base_rate
                overtime_rate = pay_rate.base_rate
                
            else:  # hourly (default)
                # Hourly rate - calculate based on actual hours worked
                total_seconds = sum(te.duration_seconds or 0 for te in time_entries)
                total_hours = Decimal(total_seconds) / Decimal("3600")
                
                # Calculate regular and overtime hours
                regular_hours = min(total_hours, overtime_threshold)
                overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))
                
                regular_rate = pay_rate.base_rate
                overtime_rate = pay_rate.base_rate * pay_rate.overtime_multiplier
                gross_amount = (regular_hours * regular_rate) + (overtime_hours * overtime_rate)
            
            # Round to 2 decimal places
            regular_hours = regular_hours.quantize(Decimal("0.01"))
            overtime_hours = overtime_hours.quantize(Decimal("0.01"))
            gross_amount = gross_amount.quantize(Decimal("0.01"))
            
            # Check if entry exists
            existing_entry_stmt = select(PayrollEntry).where(
                and_(
                    PayrollEntry.payroll_period_id == period_id,
                    PayrollEntry.user_id == user.id
                )
            )
            existing_result = await self.db.execute(existing_entry_stmt)
            entry = existing_result.scalar_one_or_none()
            
            if entry:
                entry.regular_hours = regular_hours
                entry.overtime_hours = overtime_hours
                entry.regular_rate = regular_rate
                entry.overtime_rate = overtime_rate
                entry.gross_amount = gross_amount
                entry.net_amount = (gross_amount + entry.adjustments_amount).quantize(Decimal("0.01"))
            else:
                entry = PayrollEntry(
                    payroll_period_id=period_id,
                    user_id=user.id,
                    regular_hours=regular_hours,
                    overtime_hours=overtime_hours,
                    regular_rate=regular_rate,
                    overtime_rate=overtime_rate,
                    gross_amount=gross_amount,
                    net_amount=gross_amount
                )
                self.db.add(entry)
            
            total_amount += entry.net_amount
            entries_processed += 1
        
        period.total_amount = total_amount.quantize(Decimal("0.01"))
        period.status = PeriodStatusEnum.DRAFT.value  # Back to draft for review
        
        await self.db.commit()
        await self.db.refresh(period)
        return period
    
    async def approve_period(
        self, 
        period_id: int, 
        approved_by_id: int
    ) -> Optional[PayrollPeriod]:
        """Approve a payroll period"""
        period = await self.get_period(period_id)
        if not period or period.status not in (PeriodStatusEnum.DRAFT.value, PeriodStatusEnum.PROCESSING.value):
            return None
        
        period.status = PeriodStatusEnum.APPROVED.value
        period.approved_by = approved_by_id
        period.approved_at = datetime.utcnow()
        
        # Approve all entries
        stmt = select(PayrollEntry).where(PayrollEntry.payroll_period_id == period_id)
        result = await self.db.execute(stmt)
        entries = result.scalars().all()
        
        for entry in entries:
            entry.status = EntryStatusEnum.APPROVED.value
        
        await self.db.commit()
        await self.db.refresh(period)
        return period
    
    async def mark_as_paid(self, period_id: int) -> Optional[PayrollPeriod]:
        """Mark a payroll period as paid"""
        period = await self.get_period(period_id)
        if not period or period.status != PeriodStatusEnum.APPROVED.value:
            return None
        
        period.status = PeriodStatusEnum.PAID.value
        
        # Mark all entries as paid
        stmt = select(PayrollEntry).where(PayrollEntry.payroll_period_id == period_id)
        result = await self.db.execute(stmt)
        entries = result.scalars().all()
        
        for entry in entries:
            entry.status = EntryStatusEnum.PAID.value
        
        await self.db.commit()
        await self.db.refresh(period)
        return period
    
    async def delete_period(self, period_id: int) -> bool:
        """Delete a payroll period (any status - admin responsibility)"""
        period = await self.get_period(period_id)
        if not period:
            return False
        
        await self.db.delete(period)
        await self.db.commit()
        return True


class PayrollEntryService:
    """Service for managing payroll entries"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_entry(self, entry_data: PayrollEntryCreate) -> PayrollEntry:
        """Create a new payroll entry"""
        entry = PayrollEntry(
            payroll_period_id=entry_data.payroll_period_id,
            user_id=entry_data.user_id,
            regular_hours=entry_data.regular_hours,
            overtime_hours=entry_data.overtime_hours,
            notes=entry_data.notes
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry
    
    async def get_entry(self, entry_id: int) -> Optional[PayrollEntry]:
        """Get a payroll entry by ID"""
        stmt = select(PayrollEntry).options(
            selectinload(PayrollEntry.user),
            selectinload(PayrollEntry.adjustments)
        ).where(PayrollEntry.id == entry_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_entries_by_period(
        self, 
        period_id: int
    ) -> List[PayrollEntry]:
        """Get all entries for a payroll period"""
        stmt = select(PayrollEntry).options(
            selectinload(PayrollEntry.user),
            selectinload(PayrollEntry.adjustments)
        ).where(
            PayrollEntry.payroll_period_id == period_id
        ).order_by(PayrollEntry.user_id)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_user_entries(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[PayrollEntry], int]:
        """Get all entries for a user"""
        count_stmt = select(func.count(PayrollEntry.id)).where(
            PayrollEntry.user_id == user_id
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        stmt = select(PayrollEntry).options(
            selectinload(PayrollEntry.period),
            selectinload(PayrollEntry.adjustments)
        ).where(
            PayrollEntry.user_id == user_id
        ).order_by(PayrollEntry.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
    
    async def update_entry(
        self,
        entry_id: int,
        entry_data: PayrollEntryUpdate
    ) -> Optional[PayrollEntry]:
        """Update a payroll entry"""
        entry = await self.get_entry(entry_id)
        if not entry:
            return None
        
        update_data = entry_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if field == 'status':
                    setattr(entry, field, value.value)
                else:
                    setattr(entry, field, value)
        
        # Recalculate amounts if hours changed
        if entry_data.regular_hours is not None or entry_data.overtime_hours is not None:
            entry.gross_amount = (
                entry.regular_hours * entry.regular_rate +
                entry.overtime_hours * entry.overtime_rate
            )
            entry.net_amount = entry.gross_amount + entry.adjustments_amount
        
        await self.db.commit()
        await self.db.refresh(entry)
        return entry
    
    async def recalculate_entry_totals(self, entry_id: int) -> Optional[PayrollEntry]:
        """Recalculate entry totals after adjustment changes"""
        entry = await self.get_entry(entry_id)
        if not entry:
            return None
        
        # Sum all adjustments
        adjustments_total = sum(adj.amount for adj in entry.adjustments)
        entry.adjustments_amount = adjustments_total
        entry.net_amount = entry.gross_amount + adjustments_total
        
        await self.db.commit()
        await self.db.refresh(entry)
        return entry


class PayrollAdjustmentService:
    """Service for managing payroll adjustments"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.entry_service = PayrollEntryService(db)
    
    async def create_adjustment(
        self,
        adjustment_data: PayrollAdjustmentCreate,
        created_by_id: int
    ) -> PayrollAdjustment:
        """Create a new payroll adjustment"""
        adjustment = PayrollAdjustment(
            payroll_entry_id=adjustment_data.payroll_entry_id,
            adjustment_type=adjustment_data.adjustment_type.value,
            description=adjustment_data.description,
            amount=adjustment_data.amount,
            created_by=created_by_id
        )
        self.db.add(adjustment)
        await self.db.commit()
        
        # Recalculate entry totals
        await self.entry_service.recalculate_entry_totals(adjustment_data.payroll_entry_id)
        
        await self.db.refresh(adjustment)
        return adjustment
    
    async def get_adjustment(self, adjustment_id: int) -> Optional[PayrollAdjustment]:
        """Get an adjustment by ID"""
        stmt = select(PayrollAdjustment).where(PayrollAdjustment.id == adjustment_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_entry_adjustments(self, entry_id: int) -> List[PayrollAdjustment]:
        """Get all adjustments for an entry"""
        stmt = select(PayrollAdjustment).where(
            PayrollAdjustment.payroll_entry_id == entry_id
        ).order_by(PayrollAdjustment.created_at.desc())
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_adjustment(
        self,
        adjustment_id: int,
        adjustment_data: PayrollAdjustmentUpdate
    ) -> Optional[PayrollAdjustment]:
        """Update a payroll adjustment"""
        adjustment = await self.get_adjustment(adjustment_id)
        if not adjustment:
            return None
        
        update_data = adjustment_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if field == 'adjustment_type':
                    setattr(adjustment, field, value.value)
                else:
                    setattr(adjustment, field, value)
        
        await self.db.commit()
        
        # Recalculate entry totals
        await self.entry_service.recalculate_entry_totals(adjustment.payroll_entry_id)
        
        await self.db.refresh(adjustment)
        return adjustment
    
    async def delete_adjustment(self, adjustment_id: int) -> bool:
        """Delete a payroll adjustment"""
        adjustment = await self.get_adjustment(adjustment_id)
        if not adjustment:
            return False
        
        entry_id = adjustment.payroll_entry_id
        await self.db.delete(adjustment)
        await self.db.commit()
        
        # Recalculate entry totals
        await self.entry_service.recalculate_entry_totals(entry_id)
        
        return True

