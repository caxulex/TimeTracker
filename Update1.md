# Update 1: Payroll Management & Reporting System

> **Feature:** Internal Admin Payroll Features  
> **Version:** 2.0.0  
> **Created:** December 5, 2025  
> **Status:** Planning Phase  
> **Priority:** High

---

## 📋 Executive Summary

This document outlines a comprehensive development plan for implementing two key internal admin features:

1. **Pay Rate Management System** - Input and manage worker hours and pay rates
2. **Payroll Reports Generator** - Generate detailed reports for the payables department

These features will integrate with the existing time tracking system to provide a complete payroll workflow, from time entry to payment processing reports.

---

## 🎯 Feature Overview

### Feature 1: Pay Rate Management System
- Assign hourly, daily, or monthly pay rates to workers
- Support for multiple rate types (regular, overtime, holiday)
- Effective date tracking for pay rate changes
- Historical pay rate records for audit compliance

### Feature 2: Payroll Reports Generator
- Calculate payable amounts based on hours worked × pay rates
- Generate period-based payroll reports (weekly, bi-weekly, monthly)
- Export reports in multiple formats (PDF, CSV, Excel)
- Support for overtime calculations and deductions
- Approval workflow for payroll processing

---

## 🏗️ High-Level Architecture

### Current System Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        CURRENT STATE                            │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React)          │  Backend (FastAPI)                 │
│  ├── Dashboard             │  ├── /api/auth                     │
│  ├── Time Tracking         │  ├── /api/users                    │
│  ├── Projects              │  ├── /api/time (TimeEntry)         │
│  ├── Reports               │  ├── /api/reports                  │
│  └── Admin Panel           │  └── /api/teams                    │
├─────────────────────────────────────────────────────────────────┤
│  Database: PostgreSQL                                           │
│  ├── users, teams, projects, tasks                              │
│  └── time_entries (hours tracked)                               │
└─────────────────────────────────────────────────────────────────┘
```

### Proposed Architecture Addition
```
┌─────────────────────────────────────────────────────────────────┐
│                       NEW ADDITIONS                             │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React)          │  Backend (FastAPI)                 │
│  ├── PayRatesPage          │  ├── /api/payroll/rates            │
│  ├── PayrollReportsPage    │  ├── /api/payroll/periods          │
│  └── PayrollSettingsPage   │  ├── /api/payroll/reports          │
│                            │  └── /api/payroll/export           │
├─────────────────────────────────────────────────────────────────┤
│  New Database Tables                                            │
│  ├── pay_rates (user pay rate configurations)                   │
│  ├── pay_rate_history (audit trail)                             │
│  ├── payroll_periods (pay period definitions)                   │
│  ├── payroll_entries (calculated payroll per user/period)       │
│  └── payroll_adjustments (overtime, deductions, bonuses)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Detailed Task Breakdown

### Phase 1: Database Schema Design (3-4 days)

#### Task 1.1: Design Pay Rate Tables
**Description:** Create database models for storing pay rate information

**New Models Required:**
```
PayRate:
  - id (PK)
  - user_id (FK -> users.id)
  - rate_type: enum('hourly', 'daily', 'monthly', 'project_based')
  - base_rate: Decimal(10, 2)
  - currency: String(3) - default 'USD'
  - overtime_multiplier: Decimal(4, 2) - default 1.5
  - effective_from: Date
  - effective_to: Date (nullable - null means current)
  - is_active: Boolean
  - created_by: FK -> users.id
  - created_at, updated_at

PayRateHistory:
  - id (PK)
  - pay_rate_id (FK -> pay_rates.id)
  - previous_rate: Decimal
  - new_rate: Decimal
  - changed_by: FK -> users.id
  - change_reason: Text
  - changed_at: DateTime
```

**Integration Points:**
- Links to existing `users` table via foreign key
- Must support multiple active rates (different projects/teams)
- Audit trail requirement for compliance

**Testing Strategy:**
- Unit tests for model creation and validation
- Test effective date logic (overlapping periods)
- Test currency handling and decimal precision

**Potential Challenges:**
- Handling pay rate changes mid-pay-period
- Supporting multiple currencies
- **Mitigation:** Implement proration logic, default to single currency initially

---

#### Task 1.2: Design Payroll Period Tables
**Description:** Create models for payroll period management

**New Models Required:**
```
PayrollPeriod:
  - id (PK)
  - name: String (e.g., "January 2025 - Week 1")
  - period_type: enum('weekly', 'bi_weekly', 'semi_monthly', 'monthly')
  - start_date: Date
  - end_date: Date
  - status: enum('draft', 'processing', 'approved', 'paid', 'void')
  - approved_by: FK -> users.id (nullable)
  - approved_at: DateTime (nullable)
  - total_amount: Decimal
  - created_at, updated_at

PayrollEntry:
  - id (PK)
  - payroll_period_id (FK -> payroll_periods.id)
  - user_id (FK -> users.id)
  - regular_hours: Decimal(6, 2)
  - overtime_hours: Decimal(6, 2)
  - regular_rate: Decimal(10, 2)
  - overtime_rate: Decimal(10, 2)
  - gross_amount: Decimal(10, 2)
  - adjustments_amount: Decimal(10, 2)
  - net_amount: Decimal(10, 2)
  - status: enum('pending', 'approved', 'paid')
  - notes: Text
  - created_at, updated_at

PayrollAdjustment:
  - id (PK)
  - payroll_entry_id (FK -> payroll_entries.id)
  - adjustment_type: enum('bonus', 'deduction', 'reimbursement', 'tax')
  - description: String
  - amount: Decimal(10, 2) (positive or negative)
  - created_by: FK -> users.id
  - created_at
```

**Integration Points:**
- Links payroll to existing `time_entries` table
- Uses date ranges to aggregate time entries
- Must respect team/project hierarchies

**Testing Strategy:**
- Test period creation with various types
- Test status transitions (state machine logic)
- Test amount calculations

**Potential Challenges:**
- Timezone handling for period boundaries
- Handling entries that span period boundaries
- **Mitigation:** Use UTC internally, provide clear period cutoff rules

---

#### Task 1.3: Create Database Migrations
**Description:** Generate Alembic migrations for new tables

**Files to Create:**
- `alembic/versions/xxx_add_payroll_tables.py`

**Steps:**
1. Create migration file with all new tables
2. Add indexes for common query patterns
3. Add foreign key constraints
4. Include rollback (downgrade) logic

**Testing Strategy:**
- Test migration up/down on fresh database
- Test migration on database with existing data
- Verify index creation

**Potential Challenges:**
- Migration on production with large dataset
- **Mitigation:** Use transactional DDL, test on staging first

---

### Phase 2: Backend API Development (5-6 days)

#### Task 2.1: Create Pydantic Schemas
**Description:** Define request/response schemas for payroll APIs

**Files to Create:**
- `backend/app/schemas/payroll.py`

**Schemas Required:**
```python
# Pay Rate Schemas
PayRateCreate:
  - user_id: int
  - rate_type: RateTypeEnum
  - base_rate: Decimal
  - currency: str = "USD"
  - overtime_multiplier: Decimal = 1.5
  - effective_from: date

PayRateUpdate:
  - base_rate: Optional[Decimal]
  - overtime_multiplier: Optional[Decimal]
  - effective_to: Optional[date]

PayRateResponse:
  - id, user_id, rate_type, base_rate, currency
  - overtime_multiplier, effective_from, effective_to
  - is_active, user (nested UserResponse)

# Payroll Period Schemas
PayrollPeriodCreate:
  - period_type: PeriodTypeEnum
  - start_date: date
  - end_date: date

PayrollPeriodResponse:
  - id, name, period_type, start_date, end_date
  - status, total_amount, entries_count

# Payroll Entry Schemas
PayrollEntryResponse:
  - id, user (nested), regular_hours, overtime_hours
  - regular_rate, overtime_rate, gross_amount
  - adjustments_amount, net_amount, status

# Report Schemas
PayrollReportRequest:
  - period_id: Optional[int]
  - start_date: Optional[date]
  - end_date: Optional[date]
  - user_ids: Optional[List[int]]
  - team_ids: Optional[List[int]]
  - format: ExportFormatEnum

PayrollSummaryResponse:
  - period: PayrollPeriodResponse
  - entries: List[PayrollEntryResponse]
  - totals: PayrollTotals
```

**Testing Strategy:**
- Test schema validation with valid/invalid data
- Test enum handling
- Test decimal precision

---

#### Task 2.2: Implement Pay Rate Router
**Description:** Create API endpoints for pay rate management

**File to Create:**
- `backend/app/routers/payroll_rates.py`

**Endpoints:**
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/payroll/rates` | List all pay rates (paginated) | Admin |
| GET | `/api/payroll/rates/{user_id}` | Get user's pay rates | Admin |
| GET | `/api/payroll/rates/{user_id}/current` | Get user's current rate | Admin |
| POST | `/api/payroll/rates` | Create new pay rate | Admin |
| PUT | `/api/payroll/rates/{rate_id}` | Update pay rate | Admin |
| DELETE | `/api/payroll/rates/{rate_id}` | Deactivate pay rate | Admin |
| GET | `/api/payroll/rates/{rate_id}/history` | Get rate change history | Admin |

**Business Logic:**
- Validate no overlapping effective dates for same user
- Auto-close previous rate when new rate created
- Calculate prorated amounts for mid-period changes
- Log all changes to history table

**Integration Points:**
- Uses existing `get_current_admin_user` dependency
- Integrates with `users` table for validation
- Emits events for WebSocket notifications (optional)

**Testing Strategy:**
- Test CRUD operations
- Test overlapping date validation
- Test history tracking
- Test authorization (admin only)

**Potential Challenges:**
- Complex date range queries
- **Mitigation:** Use database-level date range operators

---

#### Task 2.3: Implement Payroll Period Router
**Description:** Create API endpoints for payroll period management

**File to Create:**
- `backend/app/routers/payroll_periods.py`

**Endpoints:**
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/payroll/periods` | List periods (paginated, filtered) | Admin |
| GET | `/api/payroll/periods/{id}` | Get period details with entries | Admin |
| POST | `/api/payroll/periods` | Create new period | Admin |
| POST | `/api/payroll/periods/{id}/generate` | Generate entries from time data | Admin |
| PUT | `/api/payroll/periods/{id}` | Update period | Admin |
| POST | `/api/payroll/periods/{id}/approve` | Approve period | Admin |
| POST | `/api/payroll/periods/{id}/void` | Void period | Admin |
| DELETE | `/api/payroll/periods/{id}` | Delete draft period | Admin |

**Business Logic:**
- Period generation aggregates time entries within date range
- Applies pay rates effective during the period
- Calculates overtime based on configurable rules (e.g., >40hrs/week)
- Prevents modification of approved/paid periods
- Supports period regeneration (recalculate from time entries)

**Integration Points:**
- Reads from `time_entries` table
- Uses `pay_rates` for rate lookup
- Creates `payroll_entries` records

**Testing Strategy:**
- Test period creation with various types
- Test entry generation from time entries
- Test status transitions
- Test approval workflow

**Potential Challenges:**
- Complex overtime calculation rules
- **Mitigation:** Make overtime rules configurable, start with simple >40hrs/week

---

#### Task 2.4: Implement Payroll Reports Router
**Description:** Create API endpoints for report generation

**File to Create:**
- `backend/app/routers/payroll_reports.py`

**Endpoints:**
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/payroll/reports/summary` | Get payroll summary | Admin |
| GET | `/api/payroll/reports/by-user` | Get report grouped by user | Admin |
| GET | `/api/payroll/reports/by-team` | Get report grouped by team | Admin |
| GET | `/api/payroll/reports/by-project` | Get report grouped by project | Admin |
| POST | `/api/payroll/reports/export` | Export report (PDF/CSV/Excel) | Admin |
| GET | `/api/payroll/reports/comparison` | Compare periods | Admin |

**Report Types:**
1. **Summary Report** - Total hours, amounts, averages
2. **Detailed Report** - Line-by-line breakdown per user
3. **Comparison Report** - Period-over-period comparison
4. **Tax Report** - Deductions and tax-related summary

**Export Formats:**
- CSV (simple, for spreadsheet import)
- Excel (formatted, with multiple sheets)
- PDF (printable, with company letterhead)

**Business Logic:**
- Aggregate data from payroll_entries and adjustments
- Calculate totals, averages, variances
- Format currency according to locale
- Include audit information (generated by, timestamp)

**Integration Points:**
- Uses existing report patterns from `reports.py`
- Integrates with team/project hierarchy
- Uses templating for PDF generation

**Testing Strategy:**
- Test summary calculations
- Test grouping logic
- Test export file generation
- Test large dataset performance

**Potential Challenges:**
- PDF generation complexity
- Large dataset export performance
- **Mitigation:** Use streaming for large exports, async PDF generation

---

#### Task 2.5: Implement Payroll Service Layer
**Description:** Create service classes for complex business logic

**File to Create:**
- `backend/app/services/payroll_service.py`

**Service Methods:**
```python
class PayrollService:
    async def calculate_user_payroll(user_id, start_date, end_date) -> PayrollCalculation
    async def generate_period_entries(period_id) -> List[PayrollEntry]
    async def calculate_overtime(user_id, week_start) -> OvertimeResult
    async def apply_pay_rate(hours, pay_rate, entry_date) -> Decimal
    async def get_effective_rate(user_id, date) -> PayRate
    async def prorate_rate_change(old_rate, new_rate, change_date, period) -> Decimal
```

**Testing Strategy:**
- Unit test each calculation method
- Test edge cases (zero hours, negative adjustments)
- Test proration logic

---

#### Task 2.6: Register Routers in Main App
**Description:** Add new routers to FastAPI application

**File to Modify:**
- `backend/app/main.py`

**Changes:**
```python
from app.routers import payroll_rates, payroll_periods, payroll_reports

app.include_router(payroll_rates.router, prefix="/api/payroll/rates", tags=["Payroll Rates"])
app.include_router(payroll_periods.router, prefix="/api/payroll/periods", tags=["Payroll Periods"])
app.include_router(payroll_reports.router, prefix="/api/payroll/reports", tags=["Payroll Reports"])
```

---

### Phase 3: Frontend Development (6-7 days)

#### Task 3.1: Define TypeScript Types
**Description:** Add TypeScript interfaces for payroll features

**File to Modify:**
- `frontend/src/types/index.ts`

**New Types:**
```typescript
// Pay Rate Types
export type RateType = 'hourly' | 'daily' | 'monthly' | 'project_based';

export interface PayRate {
  id: number;
  user_id: number;
  rate_type: RateType;
  base_rate: number;
  currency: string;
  overtime_multiplier: number;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  user?: User;
  created_at: string;
}

export interface PayRateCreate {
  user_id: number;
  rate_type: RateType;
  base_rate: number;
  currency?: string;
  overtime_multiplier?: number;
  effective_from: string;
}

// Payroll Period Types
export type PeriodType = 'weekly' | 'bi_weekly' | 'semi_monthly' | 'monthly';
export type PeriodStatus = 'draft' | 'processing' | 'approved' | 'paid' | 'void';

export interface PayrollPeriod {
  id: number;
  name: string;
  period_type: PeriodType;
  start_date: string;
  end_date: string;
  status: PeriodStatus;
  total_amount: number;
  entries_count: number;
  approved_by?: User;
  approved_at?: string;
}

export interface PayrollEntry {
  id: number;
  user: User;
  regular_hours: number;
  overtime_hours: number;
  regular_rate: number;
  overtime_rate: number;
  gross_amount: number;
  adjustments_amount: number;
  net_amount: number;
  status: 'pending' | 'approved' | 'paid';
  adjustments?: PayrollAdjustment[];
}

export interface PayrollAdjustment {
  id: number;
  adjustment_type: 'bonus' | 'deduction' | 'reimbursement' | 'tax';
  description: string;
  amount: number;
}

// Report Types
export interface PayrollSummary {
  total_regular_hours: number;
  total_overtime_hours: number;
  total_gross: number;
  total_adjustments: number;
  total_net: number;
  employee_count: number;
}
```

---

#### Task 3.2: Create Payroll API Client
**Description:** Add API client methods for payroll endpoints

**File to Modify:**
- `frontend/src/api/client.ts`

**New API Methods:**
```typescript
// Pay Rates API
export const payRatesApi = {
  getAll: (page?, size?) => api.get('/api/payroll/rates', { params }),
  getByUser: (userId) => api.get(`/api/payroll/rates/${userId}`),
  getCurrentRate: (userId) => api.get(`/api/payroll/rates/${userId}/current`),
  create: (data: PayRateCreate) => api.post('/api/payroll/rates', data),
  update: (rateId, data) => api.put(`/api/payroll/rates/${rateId}`, data),
  delete: (rateId) => api.delete(`/api/payroll/rates/${rateId}`),
  getHistory: (rateId) => api.get(`/api/payroll/rates/${rateId}/history`),
};

// Payroll Periods API
export const payrollPeriodsApi = {
  getAll: (params) => api.get('/api/payroll/periods', { params }),
  getById: (id) => api.get(`/api/payroll/periods/${id}`),
  create: (data) => api.post('/api/payroll/periods', data),
  generate: (id) => api.post(`/api/payroll/periods/${id}/generate`),
  approve: (id) => api.post(`/api/payroll/periods/${id}/approve`),
  void: (id) => api.post(`/api/payroll/periods/${id}/void`),
};

// Payroll Reports API
export const payrollReportsApi = {
  getSummary: (params) => api.get('/api/payroll/reports/summary', { params }),
  getByUser: (params) => api.get('/api/payroll/reports/by-user', { params }),
  getByTeam: (params) => api.get('/api/payroll/reports/by-team', { params }),
  export: (params) => api.post('/api/payroll/reports/export', params, { responseType: 'blob' }),
};
```

---

#### Task 3.3: Create Pay Rates Management Page
**Description:** Build UI for managing employee pay rates

**File to Create:**
- `frontend/src/pages/PayRatesPage.tsx`

**UI Components:**
1. **Pay Rates Table**
   - List all employees with current pay rates
   - Search/filter by name, team, rate type
   - Sortable columns
   - Pagination

2. **Pay Rate Form Modal**
   - User selection (autocomplete)
   - Rate type dropdown
   - Base rate input with currency selector
   - Overtime multiplier input
   - Effective date picker
   - Form validation

3. **Rate History Panel**
   - Timeline view of rate changes
   - Change details (who, when, reason)

**User Flow:**
```
1. Admin navigates to /payroll/rates
2. Sees table of all employees with rates
3. Can search/filter employees
4. Clicks "Add Rate" or row edit button
5. Form modal opens for rate entry
6. Submits form, table updates
7. Can view history of changes
```

**Component Structure:**
```
PayRatesPage/
├── PayRatesTable (main list)
├── PayRateFormModal (create/edit)
├── PayRateHistoryDrawer (change history)
├── UserRateCard (summary card per user)
└── RateTypeSelector (dropdown component)
```

**Testing Strategy:**
- Component render tests
- Form validation tests
- API integration tests (mock)
- User interaction tests

---

#### Task 3.4: Create Payroll Periods Page
**Description:** Build UI for payroll period management

**File to Create:**
- `frontend/src/pages/PayrollPeriodsPage.tsx`

**UI Components:**
1. **Periods List View**
   - Table/Card view of pay periods
   - Status badges (draft, approved, paid)
   - Quick actions (generate, approve)
   - Date range filter

2. **Period Detail View**
   - Header with period info and totals
   - Entries table (per employee)
   - Adjustments section
   - Approval actions

3. **Period Creation Wizard**
   - Step 1: Select period type and dates
   - Step 2: Preview affected employees
   - Step 3: Confirm and create

4. **Entry Edit Modal**
   - Manual hour adjustments
   - Add adjustments (bonus, deduction)
   - Notes field

**User Flow:**
```
1. Admin navigates to /payroll/periods
2. Sees list of pay periods
3. Creates new period or opens existing
4. Clicks "Generate" to calculate from time entries
5. Reviews entries, makes adjustments
6. Approves period for payment
```

**Testing Strategy:**
- Test period creation flow
- Test entry generation
- Test approval workflow
- Test status transitions

---

#### Task 3.5: Create Payroll Reports Page
**Description:** Build UI for payroll report generation

**File to Create:**
- `frontend/src/pages/PayrollReportsPage.tsx`

**UI Components:**
1. **Report Builder**
   - Period selector (dropdown or date range)
   - Filter options (team, department, user)
   - Report type selector
   - Export format dropdown

2. **Summary Dashboard**
   - Total payroll amount (card)
   - Employee count (card)
   - Average hourly rate (card)
   - Overtime percentage (card)

3. **Detailed Report View**
   - Expandable rows per employee
   - Breakdown: regular, overtime, adjustments
   - Subtotals by team/project

4. **Charts Section**
   - Payroll trend (line chart)
   - Distribution by department (pie chart)
   - Overtime analysis (bar chart)

5. **Export Panel**
   - Format selection (CSV, Excel, PDF)
   - Download button
   - Email report option

**Testing Strategy:**
- Test filter combinations
- Test export functionality
- Test chart rendering
- Test responsive layout

---

#### Task 3.6: Add Navigation and Routes
**Description:** Integrate new pages into application routing

**Files to Modify:**
- `frontend/src/App.tsx` - Add routes
- `frontend/src/components/layout/Sidebar.tsx` - Add navigation links
- `frontend/src/pages/index.ts` - Export new pages

**New Routes:**
```typescript
<Route path="/payroll" element={<ProtectedRoute adminOnly />}>
  <Route index element={<PayrollDashboard />} />
  <Route path="rates" element={<PayRatesPage />} />
  <Route path="periods" element={<PayrollPeriodsPage />} />
  <Route path="periods/:id" element={<PayrollPeriodDetailPage />} />
  <Route path="reports" element={<PayrollReportsPage />} />
</Route>
```

**Navigation Items:**
```typescript
// Add to Sidebar navItems (admin only)
{
  name: 'Payroll',
  icon: DollarSign,
  adminOnly: true,
  children: [
    { name: 'Dashboard', href: '/payroll' },
    { name: 'Pay Rates', href: '/payroll/rates' },
    { name: 'Pay Periods', href: '/payroll/periods' },
    { name: 'Reports', href: '/payroll/reports' },
  ],
}
```

---

#### Task 3.7: Create Shared Payroll Components
**Description:** Build reusable components for payroll UI

**Components to Create:**
```
frontend/src/components/payroll/
├── CurrencyInput.tsx       # Formatted currency input
├── HoursInput.tsx          # Hours:minutes input
├── RateBadge.tsx           # Display rate type badge
├── StatusBadge.tsx         # Period/entry status
├── PayrollSummaryCard.tsx  # Summary statistics card
├── EntryRow.tsx            # Single payroll entry row
├── AdjustmentForm.tsx      # Add/edit adjustment
└── ExportButton.tsx        # Export dropdown with formats
```

---

### Phase 4: Integration & Testing (4-5 days)

#### Task 4.1: Backend Unit Tests
**Description:** Write comprehensive unit tests for payroll features

**Files to Create:**
- `backend/tests/test_payroll_rates.py`
- `backend/tests/test_payroll_periods.py`
- `backend/tests/test_payroll_reports.py`
- `backend/tests/test_payroll_service.py`

**Test Categories:**

**Pay Rates Tests:**
```python
class TestPayRateCreate:
    test_create_hourly_rate_success
    test_create_rate_duplicate_user_period
    test_create_rate_invalid_effective_date
    test_create_rate_unauthorized

class TestPayRateUpdate:
    test_update_rate_success
    test_update_rate_closes_previous
    test_update_rate_history_created

class TestPayRateQuery:
    test_get_current_rate
    test_get_rate_for_date
    test_list_rates_pagination
```

**Payroll Period Tests:**
```python
class TestPayrollPeriodCreate:
    test_create_weekly_period
    test_create_monthly_period
    test_create_overlapping_period_fails

class TestPayrollGeneration:
    test_generate_entries_from_time
    test_generate_with_overtime
    test_generate_prorated_rates
    test_regenerate_period

class TestPayrollApproval:
    test_approve_period_success
    test_approve_already_approved_fails
    test_void_approved_period
```

**Calculation Tests:**
```python
class TestPayrollCalculations:
    test_calculate_regular_pay
    test_calculate_overtime_pay
    test_calculate_with_adjustments
    test_prorate_rate_change
    test_decimal_precision
```

**Testing Goals:**
- Minimum 80% code coverage
- All edge cases covered
- Regression test for existing features

---

#### Task 4.2: Frontend Unit Tests
**Description:** Write React component and hook tests

**Test Files:**
```
frontend/src/__tests__/
├── pages/
│   ├── PayRatesPage.test.tsx
│   ├── PayrollPeriodsPage.test.tsx
│   └── PayrollReportsPage.test.tsx
├── components/payroll/
│   ├── CurrencyInput.test.tsx
│   ├── PayrollSummaryCard.test.tsx
│   └── EntryRow.test.tsx
└── api/
    └── payrollApi.test.ts
```

**Testing Tools:**
- Jest + React Testing Library
- MSW for API mocking
- Testing user interactions

---

#### Task 4.3: Integration Tests
**Description:** Test full workflows end-to-end

**Scenarios to Test:**
1. **Complete Payroll Cycle**
   - Create pay rates for users
   - Users log time entries
   - Create payroll period
   - Generate entries
   - Add adjustments
   - Approve period
   - Export report

2. **Rate Change Scenario**
   - User has existing rate
   - Admin updates rate mid-period
   - Verify proration in payroll

3. **Multi-Currency Scenario**
   - Different users with different currencies
   - Report totals by currency

---

#### Task 4.4: Performance Testing
**Description:** Ensure payroll features perform at scale

**Tests:**
- Generate payroll for 1000+ employees
- Export large reports (10k+ entries)
- Query performance with date range filters
- Concurrent period generation

**Performance Targets:**
- Period generation: < 5 seconds for 100 employees
- Report export: < 10 seconds for CSV
- Page load: < 2 seconds

---

### Phase 5: Documentation & Deployment (2-3 days)

#### Task 5.1: API Documentation
**Description:** Document all new endpoints

**Documentation to Create:**
- OpenAPI/Swagger annotations (auto-generated)
- Endpoint descriptions and examples
- Request/response schemas
- Error codes and handling

---

#### Task 5.2: User Documentation
**Description:** Create user guides for payroll features

**Documents:**
- Admin Guide: Managing Pay Rates
- Admin Guide: Processing Payroll
- Admin Guide: Generating Reports
- FAQ: Common Payroll Questions

---

#### Task 5.3: Database Backup Procedures
**Description:** Ensure payroll data is properly backed up

**Considerations:**
- Add payroll tables to backup scope
- Document restore procedures
- Test data recovery

---

#### Task 5.4: Deploy to Staging
**Description:** Deploy changes to staging environment

**Steps:**
1. Run database migrations
2. Deploy backend changes
3. Deploy frontend changes
4. Smoke test all features
5. Performance test with realistic data

---

#### Task 5.5: Production Deployment
**Description:** Deploy to production with zero downtime

**Steps:**
1. Schedule maintenance window (if needed)
2. Backup production database
3. Run migrations
4. Deploy backend (rolling update)
5. Deploy frontend
6. Verify all features working
7. Monitor for errors

---

## 🔄 Integration Points with Existing System

### Time Entries Integration
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  time_entries   │────▶│ PayrollService  │────▶│ payroll_entries │
│  (source data)  │     │ (aggregation)   │     │ (calculated)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### User Integration
```
┌─────────────────┐     ┌─────────────────┐
│     users       │◀───▶│   pay_rates     │
│  (employees)    │     │ (compensation)  │
└─────────────────┘     └─────────────────┘
```

### Reports Integration
```
┌─────────────────┐
│ Existing        │
│ Reports Page    │
│                 │
│ + New Payroll   │
│   Reports Tab   │
└─────────────────┘
```

---

## ⚠️ Potential Challenges & Mitigations

| Challenge | Impact | Mitigation Strategy |
|-----------|--------|---------------------|
| Complex overtime rules | High | Start with simple >40hrs/week, make configurable |
| Multi-timezone support | Medium | Use UTC internally, convert for display |
| Pay rate changes mid-period | High | Implement proration logic with clear cutoff rules |
| Large dataset performance | Medium | Use pagination, caching, async exports |
| PDF generation | Medium | Use lightweight library (ReportLab), generate async |
| Decimal precision | High | Use Decimal types, avoid floating point |
| Audit compliance | High | Log all changes, implement soft delete |
| Currency handling | Medium | Single currency initially, add multi-currency later |
| Existing test regression | Medium | Run full test suite before/after each phase |

---

## 📅 Estimated Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Database Schema | 3-4 days | None |
| Phase 2: Backend API | 5-6 days | Phase 1 |
| Phase 3: Frontend UI | 6-7 days | Phase 2 |
| Phase 4: Testing | 4-5 days | Phase 2, 3 |
| Phase 5: Documentation & Deploy | 2-3 days | Phase 4 |
| **Total** | **20-25 days** | |

---

## ✅ Definition of Done

### Feature 1: Pay Rate Management
- [ ] Admin can create pay rates for any user
- [ ] Admin can update existing pay rates
- [ ] Admin can view pay rate history
- [ ] Rate changes are audited
- [ ] Effective dates are enforced
- [ ] All unit tests passing
- [ ] Documentation complete

### Feature 2: Payroll Reports
- [ ] Admin can create payroll periods
- [ ] System generates entries from time data
- [ ] Admin can add adjustments
- [ ] Admin can approve periods
- [ ] Reports can be exported (CSV, Excel, PDF)
- [ ] All calculations are accurate
- [ ] All unit tests passing
- [ ] Documentation complete

### Overall
- [ ] No regression in existing features
- [ ] Performance targets met
- [ ] Security review completed
- [ ] Deployed to production

---

## 📝 Notes

### Security Considerations
- Payroll data is sensitive - ensure proper access control
- All endpoints require admin authentication
- Log access to payroll data for audit
- Encrypt sensitive data at rest (pay rates)

### Future Enhancements (Out of Scope)
- Direct deposit integration
- Tax calculation and filing
- Employee self-service portal
- Benefits management
- Time-off/PTO integration
- Multi-company support

---

**Document Version:** 1.0  
**Author:** Development Team  
**Review Status:** Pending  
**Next Review Date:** Before Phase 1 Start

---

# 📋 IMPLEMENTATION TASK TRACKER

> **Instructions:** Update task status as work progresses  
> **Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Completed | ❌ Blocked | ⚠️ Has Issues

---

## Phase 1: Database Schema Design

### Task 1.1: PayRate Model
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 1.1.1 | Create `PayRate` model in `backend/app/models/__init__.py` | ⬜ | | |
| 1.1.2 | Add fields: id, user_id (FK), rate_type (enum), base_rate (Decimal) | ⬜ | | |
| 1.1.3 | Add fields: currency, overtime_multiplier, effective_from, effective_to | ⬜ | | |
| 1.1.4 | Add fields: is_active, created_by (FK), created_at, updated_at | ⬜ | | |
| 1.1.5 | Create relationship to User model | ⬜ | | |
| 1.1.6 | Add database indexes for user_id and effective_from | ⬜ | | |

### Task 1.2: PayRateHistory Model
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 1.2.1 | Create `PayRateHistory` model | ⬜ | | |
| 1.2.2 | Add fields: id, pay_rate_id (FK), previous_rate, new_rate | ⬜ | | |
| 1.2.3 | Add fields: changed_by (FK), change_reason, changed_at | ⬜ | | |
| 1.2.4 | Create relationships to PayRate and User | ⬜ | | |

### Task 1.3: PayrollPeriod Model
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 1.3.1 | Create `PayrollPeriod` model | ⬜ | | |
| 1.3.2 | Add fields: id, name, period_type (enum), start_date, end_date | ⬜ | | |
| 1.3.3 | Add fields: status (enum), approved_by (FK), approved_at | ⬜ | | |
| 1.3.4 | Add fields: total_amount (Decimal), created_at, updated_at | ⬜ | | |
| 1.3.5 | Add database indexes for start_date, end_date, status | ⬜ | | |

### Task 1.4: PayrollEntry Model
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 1.4.1 | Create `PayrollEntry` model | ⬜ | | |
| 1.4.2 | Add fields: id, payroll_period_id (FK), user_id (FK) | ⬜ | | |
| 1.4.3 | Add fields: regular_hours, overtime_hours (Decimal) | ⬜ | | |
| 1.4.4 | Add fields: regular_rate, overtime_rate (Decimal) | ⬜ | | |
| 1.4.5 | Add fields: gross_amount, adjustments_amount, net_amount (Decimal) | ⬜ | | |
| 1.4.6 | Add fields: status (enum), notes, created_at, updated_at | ⬜ | | |
| 1.4.7 | Create relationships to PayrollPeriod and User | ⬜ | | |

### Task 1.5: PayrollAdjustment Model
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 1.5.1 | Create `PayrollAdjustment` model | ⬜ | | |
| 1.5.2 | Add fields: id, payroll_entry_id (FK), adjustment_type (enum) | ⬜ | | |
| 1.5.3 | Add fields: description, amount (Decimal), created_by (FK) | ⬜ | | |
| 1.5.4 | Add fields: created_at | ⬜ | | |
| 1.5.5 | Create relationship to PayrollEntry | ⬜ | | |

### Task 1.6: Database Migration
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 1.6.1 | Generate Alembic migration file | ⬜ | | |
| 1.6.2 | Add upgrade() with all table creation | ⬜ | | |
| 1.6.3 | Add downgrade() with proper rollback | ⬜ | | |
| 1.6.4 | Test migration on fresh database | ⬜ | | |
| 1.6.5 | Test migration on database with existing data | ⬜ | | |
| 1.6.6 | Verify all indexes created properly | ⬜ | | |

**Phase 1 Summary:**
- Total Tasks: 28
- Completed: 0
- In Progress: 0
- Blocked: 0

---

## Phase 2: Backend API Development

### Task 2.1: Pydantic Schemas
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.1.1 | Create `backend/app/schemas/payroll.py` file | ⬜ | | |
| 2.1.2 | Define RateTypeEnum, PeriodTypeEnum, PeriodStatusEnum | ⬜ | | |
| 2.1.3 | Create PayRateCreate, PayRateUpdate, PayRateResponse schemas | ⬜ | | |
| 2.1.4 | Create PayRateHistoryResponse schema | ⬜ | | |
| 2.1.5 | Create PayrollPeriodCreate, PayrollPeriodUpdate, PayrollPeriodResponse | ⬜ | | |
| 2.1.6 | Create PayrollEntryResponse, PayrollEntryUpdate schemas | ⬜ | | |
| 2.1.7 | Create PayrollAdjustmentCreate, PayrollAdjustmentResponse schemas | ⬜ | | |
| 2.1.8 | Create PayrollSummaryResponse, PayrollTotals schemas | ⬜ | | |
| 2.1.9 | Create PaginatedPayRates, PaginatedPayrollPeriods schemas | ⬜ | | |
| 2.1.10 | Add schema validation tests | ⬜ | | |

### Task 2.2: Pay Rate Router
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.2.1 | Create `backend/app/routers/payroll_rates.py` file | ⬜ | | |
| 2.2.2 | Implement GET `/api/payroll/rates` - List all rates (paginated) | ⬜ | | |
| 2.2.3 | Implement GET `/api/payroll/rates/user/{user_id}` - Get user's rates | ⬜ | | |
| 2.2.4 | Implement GET `/api/payroll/rates/user/{user_id}/current` - Current rate | ⬜ | | |
| 2.2.5 | Implement POST `/api/payroll/rates` - Create new rate | ⬜ | | |
| 2.2.6 | Implement PUT `/api/payroll/rates/{rate_id}` - Update rate | ⬜ | | |
| 2.2.7 | Implement DELETE `/api/payroll/rates/{rate_id}` - Deactivate rate | ⬜ | | |
| 2.2.8 | Implement GET `/api/payroll/rates/{rate_id}/history` - Rate history | ⬜ | | |
| 2.2.9 | Add overlapping date validation logic | ⬜ | | |
| 2.2.10 | Add auto-close previous rate on new rate creation | ⬜ | | |
| 2.2.11 | Add history logging on rate changes | ⬜ | | |

### Task 2.3: Payroll Period Router
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.3.1 | Create `backend/app/routers/payroll_periods.py` file | ⬜ | | |
| 2.3.2 | Implement GET `/api/payroll/periods` - List periods (paginated) | ⬜ | | |
| 2.3.3 | Implement GET `/api/payroll/periods/{id}` - Get period with entries | ⬜ | | |
| 2.3.4 | Implement POST `/api/payroll/periods` - Create new period | ⬜ | | |
| 2.3.5 | Implement POST `/api/payroll/periods/{id}/generate` - Generate entries | ⬜ | | |
| 2.3.6 | Implement PUT `/api/payroll/periods/{id}` - Update period | ⬜ | | |
| 2.3.7 | Implement POST `/api/payroll/periods/{id}/approve` - Approve period | ⬜ | | |
| 2.3.8 | Implement POST `/api/payroll/periods/{id}/void` - Void period | ⬜ | | |
| 2.3.9 | Implement DELETE `/api/payroll/periods/{id}` - Delete draft period | ⬜ | | |
| 2.3.10 | Add status transition validation (state machine) | ⬜ | | |
| 2.3.11 | Prevent modification of approved/paid periods | ⬜ | | |

### Task 2.4: Payroll Entries & Adjustments
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.4.1 | Implement GET `/api/payroll/periods/{id}/entries` - List entries | ⬜ | | |
| 2.4.2 | Implement PUT `/api/payroll/entries/{id}` - Update entry | ⬜ | | |
| 2.4.3 | Implement POST `/api/payroll/entries/{id}/adjustments` - Add adjustment | ⬜ | | |
| 2.4.4 | Implement DELETE `/api/payroll/adjustments/{id}` - Remove adjustment | ⬜ | | |
| 2.4.5 | Auto-recalculate net_amount on adjustment changes | ⬜ | | |

### Task 2.5: Payroll Reports Router
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.5.1 | Create `backend/app/routers/payroll_reports.py` file | ⬜ | | |
| 2.5.2 | Implement GET `/api/payroll/reports/summary` - Summary stats | ⬜ | | |
| 2.5.3 | Implement GET `/api/payroll/reports/by-user` - Grouped by user | ⬜ | | |
| 2.5.4 | Implement GET `/api/payroll/reports/by-team` - Grouped by team | ⬜ | | |
| 2.5.5 | Implement GET `/api/payroll/reports/by-project` - Grouped by project | ⬜ | | |
| 2.5.6 | Implement GET `/api/payroll/reports/comparison` - Period comparison | ⬜ | | |
| 2.5.7 | Implement POST `/api/payroll/reports/export` - Export report | ⬜ | | |
| 2.5.8 | Add CSV export functionality | ⬜ | | |
| 2.5.9 | Add Excel export functionality (openpyxl) | ⬜ | | |
| 2.5.10 | Add PDF export functionality (reportlab) | ⬜ | | |

### Task 2.6: Payroll Service Layer
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.6.1 | Create `backend/app/services/payroll_service.py` file | ⬜ | | |
| 2.6.2 | Implement `get_effective_rate(user_id, date)` method | ⬜ | | |
| 2.6.3 | Implement `calculate_user_payroll(user_id, start, end)` method | ⬜ | | |
| 2.6.4 | Implement `generate_period_entries(period_id)` method | ⬜ | | |
| 2.6.5 | Implement `calculate_overtime(user_id, week_start)` method | ⬜ | | |
| 2.6.6 | Implement `apply_pay_rate(hours, rate, date)` method | ⬜ | | |
| 2.6.7 | Implement `prorate_rate_change(old, new, change_date, period)` method | ⬜ | | |
| 2.6.8 | Add configurable overtime threshold (default 40hrs/week) | ⬜ | | |

### Task 2.7: Router Registration
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.7.1 | Import payroll routers in `backend/app/main.py` | ⬜ | | |
| 2.7.2 | Register payroll_rates router with prefix | ⬜ | | |
| 2.7.3 | Register payroll_periods router with prefix | ⬜ | | |
| 2.7.4 | Register payroll_reports router with prefix | ⬜ | | |
| 2.7.5 | Verify OpenAPI docs include new endpoints | ⬜ | | |

### Task 2.8: Install Dependencies
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 2.8.1 | Add `openpyxl` to requirements.txt (Excel export) | ⬜ | | |
| 2.8.2 | Add `reportlab` to requirements.txt (PDF export) | ⬜ | | |
| 2.8.3 | Verify decimal handling with existing libs | ⬜ | | |

**Phase 2 Summary:**
- Total Tasks: 53
- Completed: 0
- In Progress: 0
- Blocked: 0

---

## Phase 3: Frontend Development

### Task 3.1: TypeScript Types
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.1.1 | Add RateType type ('hourly', 'daily', 'monthly', 'project_based') | ⬜ | | |
| 3.1.2 | Add PayRate interface | ⬜ | | |
| 3.1.3 | Add PayRateCreate, PayRateUpdate interfaces | ⬜ | | |
| 3.1.4 | Add PeriodType, PeriodStatus types | ⬜ | | |
| 3.1.5 | Add PayrollPeriod interface | ⬜ | | |
| 3.1.6 | Add PayrollEntry interface | ⬜ | | |
| 3.1.7 | Add PayrollAdjustment interface | ⬜ | | |
| 3.1.8 | Add PayrollSummary interface | ⬜ | | |
| 3.1.9 | Add PayRateHistory interface | ⬜ | | |

### Task 3.2: API Client Methods
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.2.1 | Create payRatesApi object in client.ts | ⬜ | | |
| 3.2.2 | Add payRatesApi.getAll() method | ⬜ | | |
| 3.2.3 | Add payRatesApi.getByUser() method | ⬜ | | |
| 3.2.4 | Add payRatesApi.getCurrentRate() method | ⬜ | | |
| 3.2.5 | Add payRatesApi.create() method | ⬜ | | |
| 3.2.6 | Add payRatesApi.update() method | ⬜ | | |
| 3.2.7 | Add payRatesApi.delete() method | ⬜ | | |
| 3.2.8 | Add payRatesApi.getHistory() method | ⬜ | | |
| 3.2.9 | Create payrollPeriodsApi object | ⬜ | | |
| 3.2.10 | Add payrollPeriodsApi.getAll() method | ⬜ | | |
| 3.2.11 | Add payrollPeriodsApi.getById() method | ⬜ | | |
| 3.2.12 | Add payrollPeriodsApi.create() method | ⬜ | | |
| 3.2.13 | Add payrollPeriodsApi.generate() method | ⬜ | | |
| 3.2.14 | Add payrollPeriodsApi.approve() method | ⬜ | | |
| 3.2.15 | Add payrollPeriodsApi.void() method | ⬜ | | |
| 3.2.16 | Create payrollReportsApi object | ⬜ | | |
| 3.2.17 | Add payrollReportsApi.getSummary() method | ⬜ | | |
| 3.2.18 | Add payrollReportsApi.getByUser() method | ⬜ | | |
| 3.2.19 | Add payrollReportsApi.getByTeam() method | ⬜ | | |
| 3.2.20 | Add payrollReportsApi.export() method (blob response) | ⬜ | | |

### Task 3.3: Shared Payroll Components
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.3.1 | Create `frontend/src/components/payroll/` directory | ⬜ | | |
| 3.3.2 | Create CurrencyInput.tsx component | ⬜ | | |
| 3.3.3 | Create HoursInput.tsx component | ⬜ | | |
| 3.3.4 | Create RateBadge.tsx component (rate type display) | ⬜ | | |
| 3.3.5 | Create StatusBadge.tsx component (period/entry status) | ⬜ | | |
| 3.3.6 | Create PayrollSummaryCard.tsx component | ⬜ | | |
| 3.3.7 | Create EntryRow.tsx component | ⬜ | | |
| 3.3.8 | Create AdjustmentForm.tsx component | ⬜ | | |
| 3.3.9 | Create ExportButton.tsx component (format dropdown) | ⬜ | | |
| 3.3.10 | Create index.ts exports for payroll components | ⬜ | | |

### Task 3.4: Pay Rates Page
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.4.1 | Create `frontend/src/pages/PayRatesPage.tsx` | ⬜ | | |
| 3.4.2 | Implement pay rates table with pagination | ⬜ | | |
| 3.4.3 | Add search/filter by user name, team, rate type | ⬜ | | |
| 3.4.4 | Add sortable columns (name, rate, effective date) | ⬜ | | |
| 3.4.5 | Create PayRateFormModal component | ⬜ | | |
| 3.4.6 | Add user autocomplete/select in form | ⬜ | | |
| 3.4.7 | Add rate type dropdown in form | ⬜ | | |
| 3.4.8 | Add base rate input with currency selector | ⬜ | | |
| 3.4.9 | Add overtime multiplier input | ⬜ | | |
| 3.4.10 | Add effective date picker | ⬜ | | |
| 3.4.11 | Add form validation (required fields, positive rate) | ⬜ | | |
| 3.4.12 | Create PayRateHistoryDrawer component | ⬜ | | |
| 3.4.13 | Add timeline view for rate changes | ⬜ | | |
| 3.4.14 | Wire up React Query for data fetching | ⬜ | | |
| 3.4.15 | Add success/error toast notifications | ⬜ | | |

### Task 3.5: Payroll Periods Page
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.5.1 | Create `frontend/src/pages/PayrollPeriodsPage.tsx` | ⬜ | | |
| 3.5.2 | Implement periods list with status badges | ⬜ | | |
| 3.5.3 | Add date range filter | ⬜ | | |
| 3.5.4 | Add status filter dropdown | ⬜ | | |
| 3.5.5 | Create PeriodCreateModal component | ⬜ | | |
| 3.5.6 | Add period type selector (weekly/bi-weekly/monthly) | ⬜ | | |
| 3.5.7 | Add date range picker for period | ⬜ | | |
| 3.5.8 | Add preview of affected employees count | ⬜ | | |
| 3.5.9 | Create quick action buttons (generate, approve) | ⬜ | | |
| 3.5.10 | Add confirmation dialogs for approve/void | ⬜ | | |

### Task 3.6: Payroll Period Detail Page
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.6.1 | Create `frontend/src/pages/PayrollPeriodDetailPage.tsx` | ⬜ | | |
| 3.6.2 | Implement period header with summary stats | ⬜ | | |
| 3.6.3 | Create entries table with all columns | ⬜ | | |
| 3.6.4 | Add expandable row for entry details | ⬜ | | |
| 3.6.5 | Create EntryEditModal component | ⬜ | | |
| 3.6.6 | Add manual hour adjustment inputs | ⬜ | | |
| 3.6.7 | Add adjustments section (bonus, deduction) | ⬜ | | |
| 3.6.8 | Create AddAdjustmentModal component | ⬜ | | |
| 3.6.9 | Add approve/void buttons with status checks | ⬜ | | |
| 3.6.10 | Add regenerate button for draft periods | ⬜ | | |
| 3.6.11 | Display total amount prominently | ⬜ | | |

### Task 3.7: Payroll Reports Page
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.7.1 | Create `frontend/src/pages/PayrollReportsPage.tsx` | ⬜ | | |
| 3.7.2 | Create report builder section | ⬜ | | |
| 3.7.3 | Add period selector dropdown | ⬜ | | |
| 3.7.4 | Add date range picker alternative | ⬜ | | |
| 3.7.5 | Add team/user filter multiselect | ⬜ | | |
| 3.7.6 | Create summary dashboard cards | ⬜ | | |
| 3.7.7 | Add total payroll amount card | ⬜ | | |
| 3.7.8 | Add employee count card | ⬜ | | |
| 3.7.9 | Add average hourly rate card | ⬜ | | |
| 3.7.10 | Add overtime percentage card | ⬜ | | |
| 3.7.11 | Create detailed report table | ⬜ | | |
| 3.7.12 | Add expandable rows per employee | ⬜ | | |
| 3.7.13 | Add subtotals by team | ⬜ | | |
| 3.7.14 | Create payroll trend line chart | ⬜ | | |
| 3.7.15 | Create department distribution pie chart | ⬜ | | |
| 3.7.16 | Create overtime analysis bar chart | ⬜ | | |
| 3.7.17 | Add export format selector (CSV, Excel, PDF) | ⬜ | | |
| 3.7.18 | Implement file download on export | ⬜ | | |

### Task 3.8: Navigation & Routing
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 3.8.1 | Add PayRatesPage to pages/index.ts exports | ⬜ | | |
| 3.8.2 | Add PayrollPeriodsPage to exports | ⬜ | | |
| 3.8.3 | Add PayrollPeriodDetailPage to exports | ⬜ | | |
| 3.8.4 | Add PayrollReportsPage to exports | ⬜ | | |
| 3.8.5 | Add /payroll routes to App.tsx | ⬜ | | |
| 3.8.6 | Add /payroll/rates route | ⬜ | | |
| 3.8.7 | Add /payroll/periods route | ⬜ | | |
| 3.8.8 | Add /payroll/periods/:id route | ⬜ | | |
| 3.8.9 | Add /payroll/reports route | ⬜ | | |
| 3.8.10 | Wrap payroll routes with ProtectedRoute (adminOnly) | ⬜ | | |
| 3.8.11 | Add Payroll section to Sidebar navigation | ⬜ | | |
| 3.8.12 | Add DollarSign icon for payroll nav | ⬜ | | |
| 3.8.13 | Add child nav items (Rates, Periods, Reports) | ⬜ | | |
| 3.8.14 | Set adminOnly: true for payroll nav section | ⬜ | | |

**Phase 3 Summary:**
- Total Tasks: 86
- Completed: 0
- In Progress: 0
- Blocked: 0

---

## Phase 4: Testing

### Task 4.1: Backend Unit Tests - Pay Rates
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.1.1 | Create `backend/tests/test_payroll_rates.py` | ⬜ | | |
| 4.1.2 | Test: create hourly rate success | ⬜ | | |
| 4.1.3 | Test: create daily rate success | ⬜ | | |
| 4.1.4 | Test: create rate with overlapping dates fails | ⬜ | | |
| 4.1.5 | Test: create rate for non-existent user fails | ⬜ | | |
| 4.1.6 | Test: create rate unauthorized (non-admin) | ⬜ | | |
| 4.1.7 | Test: update rate success | ⬜ | | |
| 4.1.8 | Test: update rate creates history entry | ⬜ | | |
| 4.1.9 | Test: get current rate returns active rate | ⬜ | | |
| 4.1.10 | Test: get rate for specific date | ⬜ | | |
| 4.1.11 | Test: list rates pagination | ⬜ | | |
| 4.1.12 | Test: deactivate rate success | ⬜ | | |

### Task 4.2: Backend Unit Tests - Payroll Periods
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.2.1 | Create `backend/tests/test_payroll_periods.py` | ⬜ | | |
| 4.2.2 | Test: create weekly period success | ⬜ | | |
| 4.2.3 | Test: create monthly period success | ⬜ | | |
| 4.2.4 | Test: create overlapping period fails | ⬜ | | |
| 4.2.5 | Test: generate entries from time entries | ⬜ | | |
| 4.2.6 | Test: generate entries with overtime calculation | ⬜ | | |
| 4.2.7 | Test: generate entries with prorated rates | ⬜ | | |
| 4.2.8 | Test: approve period changes status | ⬜ | | |
| 4.2.9 | Test: approve already approved fails | ⬜ | | |
| 4.2.10 | Test: void approved period success | ⬜ | | |
| 4.2.11 | Test: delete draft period success | ⬜ | | |
| 4.2.12 | Test: delete approved period fails | ⬜ | | |
| 4.2.13 | Test: modify approved period fails | ⬜ | | |

### Task 4.3: Backend Unit Tests - Payroll Service
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.3.1 | Create `backend/tests/test_payroll_service.py` | ⬜ | | |
| 4.3.2 | Test: calculate regular pay (hours × rate) | ⬜ | | |
| 4.3.3 | Test: calculate overtime pay (hours × rate × multiplier) | ⬜ | | |
| 4.3.4 | Test: calculate with adjustments (bonus, deduction) | ⬜ | | |
| 4.3.5 | Test: prorate rate change mid-period | ⬜ | | |
| 4.3.6 | Test: decimal precision (no floating point errors) | ⬜ | | |
| 4.3.7 | Test: get effective rate for date | ⬜ | | |
| 4.3.8 | Test: overtime threshold calculation | ⬜ | | |
| 4.3.9 | Test: zero hours returns zero amount | ⬜ | | |
| 4.3.10 | Test: negative adjustment reduces net | ⬜ | | |

### Task 4.4: Backend Unit Tests - Payroll Reports
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.4.1 | Create `backend/tests/test_payroll_reports.py` | ⬜ | | |
| 4.4.2 | Test: summary report calculations | ⬜ | | |
| 4.4.3 | Test: group by user report | ⬜ | | |
| 4.4.4 | Test: group by team report | ⬜ | | |
| 4.4.5 | Test: export CSV format | ⬜ | | |
| 4.4.6 | Test: export Excel format | ⬜ | | |
| 4.4.7 | Test: export PDF format | ⬜ | | |
| 4.4.8 | Test: period comparison report | ⬜ | | |
| 4.4.9 | Test: large dataset performance (100+ users) | ⬜ | | |

### Task 4.5: Frontend Component Tests
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.5.1 | Create `frontend/src/__tests__/` directory structure | ⬜ | | |
| 4.5.2 | Test: CurrencyInput renders and formats | ⬜ | | |
| 4.5.3 | Test: PayrollSummaryCard displays data | ⬜ | | |
| 4.5.4 | Test: StatusBadge shows correct colors | ⬜ | | |
| 4.5.5 | Test: PayRatesPage renders table | ⬜ | | |
| 4.5.6 | Test: PayRateFormModal validation | ⬜ | | |
| 4.5.7 | Test: PayrollPeriodsPage renders list | ⬜ | | |
| 4.5.8 | Test: PayrollReportsPage export button | ⬜ | | |

### Task 4.6: Integration Tests
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.6.1 | Test: Complete payroll cycle (rate → time → period → report) | ⬜ | | |
| 4.6.2 | Test: Rate change mid-period proration | ⬜ | | |
| 4.6.3 | Test: Multiple users in same period | ⬜ | | |
| 4.6.4 | Test: Adjustment affects net amount | ⬜ | | |
| 4.6.5 | Test: Export contains correct data | ⬜ | | |

### Task 4.7: Regression Tests
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 4.7.1 | Run existing auth tests - verify passing | ⬜ | | |
| 4.7.2 | Run existing time_entries tests - verify passing | ⬜ | | |
| 4.7.3 | Run existing reports tests - verify passing | ⬜ | | |
| 4.7.4 | Run existing teams tests - verify passing | ⬜ | | |
| 4.7.5 | Run existing projects tests - verify passing | ⬜ | | |
| 4.7.6 | Frontend build - verify no TypeScript errors | ⬜ | | |

**Phase 4 Summary:**
- Total Tasks: 56
- Completed: 0
- In Progress: 0
- Blocked: 0

---

## Phase 5: Documentation & Deployment

### Task 5.1: API Documentation
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 5.1.1 | Add docstrings to all payroll endpoints | ⬜ | | |
| 5.1.2 | Add request/response examples in OpenAPI | ⬜ | | |
| 5.1.3 | Document error codes and handling | ⬜ | | |
| 5.1.4 | Verify Swagger UI displays correctly | ⬜ | | |

### Task 5.2: User Documentation
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 5.2.1 | Create Admin Guide: Managing Pay Rates | ⬜ | | |
| 5.2.2 | Create Admin Guide: Processing Payroll | ⬜ | | |
| 5.2.3 | Create Admin Guide: Generating Reports | ⬜ | | |
| 5.2.4 | Create FAQ document | ⬜ | | |
| 5.2.5 | Add screenshots to documentation | ⬜ | | |

### Task 5.3: Update Project Files
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 5.3.1 | Update README.md with payroll features | ⬜ | | |
| 5.3.2 | Update tasks.md with new phase completion | ⬜ | | |
| 5.3.3 | Document new environment variables (if any) | ⬜ | | |
| 5.3.4 | Update .env.example if needed | ⬜ | | |

### Task 5.4: Deployment Preparation
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 5.4.1 | Backup production database | ⬜ | | |
| 5.4.2 | Test migration on staging | ⬜ | | |
| 5.4.3 | Deploy backend to staging | ⬜ | | |
| 5.4.4 | Deploy frontend to staging | ⬜ | | |
| 5.4.5 | Smoke test all payroll features on staging | ⬜ | | |
| 5.4.6 | Performance test with realistic data | ⬜ | | |

### Task 5.5: Production Deployment
| # | Task | Status | Assignee | Notes |
|---|------|--------|----------|-------|
| 5.5.1 | Schedule deployment window | ⬜ | | |
| 5.5.2 | Run database migration | ⬜ | | |
| 5.5.3 | Deploy backend (rolling update) | ⬜ | | |
| 5.5.4 | Deploy frontend | ⬜ | | |
| 5.5.5 | Verify all features working | ⬜ | | |
| 5.5.6 | Monitor error logs | ⬜ | | |
| 5.5.7 | Announce feature release | ⬜ | | |

**Phase 5 Summary:**
- Total Tasks: 22
- Completed: 0
- In Progress: 0
- Blocked: 0

---

## 📊 OVERALL PROGRESS DASHBOARD

| Phase | Total Tasks | ⬜ Not Started | 🔄 In Progress | ✅ Completed | ❌ Blocked |
|-------|-------------|----------------|----------------|--------------|------------|
| Phase 1: Database | 28 | 28 | 0 | 0 | 0 |
| Phase 2: Backend API | 53 | 53 | 0 | 0 | 0 |
| Phase 3: Frontend | 86 | 86 | 0 | 0 | 0 |
| Phase 4: Testing | 56 | 56 | 0 | 0 | 0 |
| Phase 5: Deployment | 22 | 22 | 0 | 0 | 0 |
| **TOTAL** | **245** | **245** | **0** | **0** | **0** |

**Overall Completion: 0%**

---

## 🚨 ISSUES LOG

| Issue # | Date | Phase | Task | Description | Status | Resolution |
|---------|------|-------|------|-------------|--------|------------|
| | | | | | | |

---

## 📝 DEVELOPMENT NOTES

### Session Log
| Date | Tasks Worked On | Hours | Notes |
|------|-----------------|-------|-------|
| | | | |

### Decisions Made
| Date | Decision | Rationale |
|------|----------|-----------|
| | | |

### Dependencies Discovered
| Task | Depends On | Notes |
|------|------------|-------|
| 2.2.1 | 1.6.6 | Router needs models and migration complete |
| 3.4.1 | 2.2.11 | Frontend needs API endpoints ready |
| 4.1.1 | 2.2.11 | Tests need endpoints implemented |

---

**Last Updated:** December 5, 2025  
**Next Review:** Before starting Phase 1
