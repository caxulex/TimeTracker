// ============================================
// PAYROLL - TYPE DEFINITIONS
// ============================================

// Enums
export type RateType = 'hourly' | 'daily' | 'monthly' | 'project_based';
export type PeriodType = 'weekly' | 'bi_weekly' | 'semi_monthly' | 'monthly';
export type PeriodStatus = 'draft' | 'processing' | 'approved' | 'paid' | 'void';
export type EntryStatus = 'pending' | 'approved' | 'paid';
export type AdjustmentType = 'bonus' | 'deduction' | 'reimbursement' | 'tax' | 'other';

// Pay Rate Types
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
  created_by: number;
  created_at: string;
  updated_at: string;
  // Extended fields
  user_name?: string;
  user_email?: string;
}

export interface PayRateCreate {
  user_id: number;
  rate_type?: RateType;
  base_rate: number;
  currency?: string;
  overtime_multiplier?: number;
  effective_from: string;
  effective_to?: string | null;
  is_active?: boolean;
}

export interface PayRateUpdate {
  rate_type?: RateType;
  base_rate?: number;
  currency?: string;
  overtime_multiplier?: number;
  effective_from?: string;
  effective_to?: string | null;
  is_active?: boolean;
  change_reason?: string;
}

export interface PayRateHistory {
  id: number;
  pay_rate_id: number;
  previous_rate: number;
  new_rate: number;
  previous_overtime_multiplier: number | null;
  new_overtime_multiplier: number | null;
  changed_by: number;
  change_reason: string | null;
  changed_at: string;
  changed_by_name?: string;
}

// Payroll Period Types
export interface PayrollPeriod {
  id: number;
  name: string;
  period_type: PeriodType;
  start_date: string;
  end_date: string;
  status: PeriodStatus;
  total_amount: number;
  approved_by: number | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  entries_count: number;
  entries?: PayrollEntry[];
}

export interface PayrollPeriodCreate {
  name: string;
  period_type?: PeriodType;
  start_date: string;
  end_date: string;
  // Employee selection options
  user_ids?: number[];           // Specific user IDs to include (empty = all)
  rate_type_filter?: RateType;   // Filter by rate type (hourly, monthly, etc.)
}

export interface PayrollPeriodUpdate {
  name?: string;
  period_type?: PeriodType;
  start_date?: string;
  end_date?: string;
  status?: PeriodStatus;
}

// Payroll Entry Types
export interface PayrollEntry {
  id: number;
  payroll_period_id: number;
  user_id: number;
  regular_hours: number;
  overtime_hours: number;
  regular_rate: number;
  overtime_rate: number;
  gross_amount: number;
  adjustments_amount: number;
  net_amount: number;
  status: EntryStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
  // Extended fields
  user_name?: string;
  user_email?: string;
  rate_type?: RateType;  // hourly, daily, monthly, project_based
  adjustments?: PayrollAdjustment[];
}

export interface PayrollEntryCreate {
  payroll_period_id: number;
  user_id: number;
  regular_hours?: number;
  overtime_hours?: number;
  notes?: string;
}

export interface PayrollEntryUpdate {
  regular_hours?: number;
  overtime_hours?: number;
  notes?: string;
  status?: EntryStatus;
}

// Payroll Adjustment Types
export interface PayrollAdjustment {
  id: number;
  payroll_entry_id: number;
  adjustment_type: AdjustmentType;
  description: string;
  amount: number;
  created_by: number;
  created_at: string;
  created_by_name?: string;
}

export interface PayrollAdjustmentCreate {
  payroll_entry_id: number;
  adjustment_type: AdjustmentType;
  description: string;
  amount: number;
}

export interface PayrollAdjustmentUpdate {
  adjustment_type?: AdjustmentType;
  description?: string;
  amount?: number;
}

// Report Types
export interface PayrollSummaryReport {
  period_id: number;
  period_name: string;
  start_date: string;
  end_date: string;
  status: string;
  total_employees: number;
  total_regular_hours: number;
  total_overtime_hours: number;
  total_gross_amount: number;
  total_adjustments: number;
  total_net_amount: number;
}

export interface UserPayrollReport {
  user_id: number;
  user_name: string;
  user_email: string;
  period_name: string;
  start_date: string;
  end_date: string;
  regular_hours: number;
  overtime_hours: number;
  regular_rate: number;
  overtime_rate: number;
  gross_amount: number;
  adjustments: PayrollAdjustment[];
  adjustments_total: number;
  net_amount: number;
}

export interface PayrollReportFilters {
  start_date?: string;
  end_date?: string;
  period_id?: number;
  user_id?: number;
  status?: PeriodStatus;
  period_type?: PeriodType;
}

export interface PayablesDepartmentReport {
  report_generated_at: string;
  report_period: string;
  filters_applied: PayrollReportFilters;
  summary: PayrollSummaryReport;
  entries: UserPayrollReport[];
}

// Paginated Response Types
export interface PayRateListResponse {
  items: PayRate[];
  total: number;
  skip: number;
  limit: number;
}

export interface PayrollPeriodListResponse {
  items: PayrollPeriod[];
  total: number;
  skip: number;
  limit: number;
}

export interface PayrollEntryListResponse {
  items: PayrollEntry[];
  total: number;
  skip: number;
  limit: number;
}

// Utility types for forms
export interface PayRateFormData {
  user_id: number;
  rate_type: RateType;
  base_rate: string;
  currency: string;
  overtime_multiplier: string;
  effective_from: string;
  effective_to: string;
}

export interface PayrollPeriodFormData {
  name: string;
  period_type: PeriodType;
  start_date: string;
  end_date: string;
}

export interface PayrollAdjustmentFormData {
  adjustment_type: AdjustmentType;
  description: string;
  amount: string;
}
