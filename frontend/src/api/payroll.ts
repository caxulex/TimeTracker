/**
 * Payroll API Client
 * Handles all payroll-related API calls
 */

import api from './client';
import {
  PayRate,
  PayRateCreate,
  PayRateUpdate,
  PayRateHistory,
  PayRateListResponse,
  PayrollPeriod,
  PayrollPeriodCreate,
  PayrollPeriodUpdate,
  PayrollPeriodListResponse,
  PayrollEntry,
  PayrollEntryCreate,
  PayrollEntryUpdate,
  PayrollEntryListResponse,
  PayrollAdjustment,
  PayrollAdjustmentCreate,
  PayrollAdjustmentUpdate,
  PayrollSummaryReport,
  UserPayrollReport,
  PayrollReportFilters,
  PayablesDepartmentReport,
  PeriodStatus,
} from '../types/payroll';

// ============================================
// PAY RATES API
// ============================================

export const payRatesApi = {
  /**
   * Create a new pay rate for a user
   */
  create: async (data: PayRateCreate): Promise<PayRate> => {
    const response = await api.post('/api/pay-rates', data);
    return response.data;
  },

  /**
   * List all pay rates with pagination
   */
  list: async (
    skip: number = 0,
    limit: number = 100,
    activeOnly: boolean = true
  ): Promise<PayRateListResponse> => {
    const response = await api.get('/api/pay-rates', {
      params: { skip, limit, active_only: activeOnly },
    });
    return response.data;
  },

  /**
   * Get pay rates for a specific user
   */
  getForUser: async (userId: number, includeInactive: boolean = false): Promise<PayRate[]> => {
    const response = await api.get(`/api/pay-rates/user/${userId}`, {
      params: { include_inactive: includeInactive },
    });
    return response.data;
  },

  /**
   * Get current active pay rate for a user
   */
  getCurrentForUser: async (userId: number): Promise<PayRate | null> => {
    const response = await api.get(`/api/pay-rates/user/${userId}/current`);
    return response.data;
  },

  /**
   * Get a specific pay rate by ID
   */
  get: async (payRateId: number): Promise<PayRate> => {
    const response = await api.get(`/api/pay-rates/${payRateId}`);
    return response.data;
  },

  /**
   * Update a pay rate
   */
  update: async (payRateId: number, data: PayRateUpdate): Promise<PayRate> => {
    const response = await api.put(`/api/pay-rates/${payRateId}`, data);
    return response.data;
  },

  /**
   * Delete (deactivate) a pay rate
   */
  delete: async (payRateId: number): Promise<void> => {
    await api.delete(`/api/pay-rates/${payRateId}`);
  },

  /**
   * Get change history for a pay rate
   */
  getHistory: async (payRateId: number): Promise<PayRateHistory[]> => {
    const response = await api.get(`/api/pay-rates/${payRateId}/history`);
    return response.data;
  },
};

// ============================================
// PAYROLL PERIODS API
// ============================================

export const payrollPeriodsApi = {
  /**
   * Create a new payroll period
   */
  create: async (data: PayrollPeriodCreate): Promise<PayrollPeriod> => {
    const response = await api.post('/api/payroll/periods', data);
    return response.data;
  },

  /**
   * List all payroll periods with pagination
   */
  list: async (
    skip: number = 0,
    limit: number = 100,
    status?: PeriodStatus
  ): Promise<PayrollPeriodListResponse> => {
    const response = await api.get('/api/payroll/periods', {
      params: { skip, limit, status },
    });
    return response.data;
  },

  /**
   * Get a specific payroll period with entries
   */
  get: async (periodId: number): Promise<PayrollPeriod> => {
    const response = await api.get(`/api/payroll/periods/${periodId}`);
    return response.data;
  },

  /**
   * Update a payroll period
   */
  update: async (periodId: number, data: PayrollPeriodUpdate): Promise<PayrollPeriod> => {
    const response = await api.put(`/api/payroll/periods/${periodId}`, data);
    return response.data;
  },

  /**
   * Process a payroll period (calculate all entries)
   */
  process: async (periodId: number): Promise<PayrollPeriod> => {
    const response = await api.post(`/api/payroll/periods/${periodId}/process`);
    return response.data;
  },

  /**
   * Approve a payroll period
   */
  approve: async (periodId: number): Promise<PayrollPeriod> => {
    const response = await api.post(`/api/payroll/periods/${periodId}/approve`);
    return response.data;
  },

  /**
   * Mark a payroll period as paid
   */
  markPaid: async (periodId: number): Promise<PayrollPeriod> => {
    const response = await api.post(`/api/payroll/periods/${periodId}/mark-paid`);
    return response.data;
  },

  /**
   * Delete a payroll period (only if draft)
   */
  delete: async (periodId: number): Promise<void> => {
    await api.delete(`/api/payroll/periods/${periodId}`);
  },

  /**
   * Get entries for a specific period
   */
  getEntries: async (periodId: number): Promise<PayrollEntry[]> => {
    const response = await api.get(`/api/payroll/periods/${periodId}/entries`);
    return response.data;
  },
};

// ============================================
// PAYROLL ENTRIES API
// ============================================

export const payrollEntriesApi = {
  /**
   * Create a new payroll entry
   */
  create: async (data: PayrollEntryCreate): Promise<PayrollEntry> => {
    const response = await api.post('/api/payroll/entries', data);
    return response.data;
  },

  /**
   * Get a specific payroll entry
   */
  get: async (entryId: number): Promise<PayrollEntry> => {
    const response = await api.get(`/api/payroll/entries/${entryId}`);
    return response.data;
  },

  /**
   * Get payroll entries for a user
   */
  getForUser: async (
    userId: number,
    skip: number = 0,
    limit: number = 100
  ): Promise<PayrollEntryListResponse> => {
    const response = await api.get(`/api/payroll/user/${userId}/entries`, {
      params: { skip, limit },
    });
    return response.data;
  },

  /**
   * Update a payroll entry
   */
  update: async (entryId: number, data: PayrollEntryUpdate): Promise<PayrollEntry> => {
    const response = await api.put(`/api/payroll/entries/${entryId}`, data);
    return response.data;
  },
};

// ============================================
// PAYROLL ADJUSTMENTS API
// ============================================

export const payrollAdjustmentsApi = {
  /**
   * Create a new payroll adjustment
   */
  create: async (data: PayrollAdjustmentCreate): Promise<PayrollAdjustment> => {
    const response = await api.post('/api/payroll/adjustments', data);
    return response.data;
  },

  /**
   * Get adjustments for a specific entry
   */
  getForEntry: async (entryId: number): Promise<PayrollAdjustment[]> => {
    const response = await api.get(`/api/payroll/entries/${entryId}/adjustments`);
    return response.data;
  },

  /**
   * Update a payroll adjustment
   */
  update: async (adjustmentId: number, data: PayrollAdjustmentUpdate): Promise<PayrollAdjustment> => {
    const response = await api.put(`/api/payroll/adjustments/${adjustmentId}`, data);
    return response.data;
  },

  /**
   * Delete a payroll adjustment
   */
  delete: async (adjustmentId: number): Promise<void> => {
    await api.delete(`/api/payroll/adjustments/${adjustmentId}`);
  },
};

// ============================================
// PAYROLL REPORTS API
// ============================================

export const payrollReportsApi = {
  /**
   * Get summary report for a specific period
   */
  getPeriodSummary: async (periodId: number): Promise<PayrollSummaryReport> => {
    const response = await api.get(`/api/payroll/reports/summary/${periodId}`);
    return response.data;
  },

  /**
   * Get payroll report for a specific user
   */
  getUserReport: async (
    userId: number,
    periodId?: number,
    startDate?: string,
    endDate?: string
  ): Promise<UserPayrollReport[]> => {
    const response = await api.get(`/api/payroll/reports/user/${userId}`, {
      params: { period_id: periodId, start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  /**
   * Get payables department report with filters
   */
  getPayablesReport: async (filters: PayrollReportFilters): Promise<PayablesDepartmentReport> => {
    const response = await api.post('/api/payroll/reports/payables', filters);
    return response.data;
  },

  /**
   * Get payables report using query params
   */
  getPayablesReportQuery: async (filters: PayrollReportFilters): Promise<PayablesDepartmentReport> => {
    const response = await api.get('/api/payroll/reports/payables', {
      params: {
        period_id: filters.period_id,
        user_id: filters.user_id,
        status: filters.status,
        period_type: filters.period_type,
        start_date: filters.start_date,
        end_date: filters.end_date,
      },
    });
    return response.data;
  },

  /**
   * Export payables report as CSV
   */
  exportCsv: async (filters: PayrollReportFilters): Promise<Blob> => {
    const response = await api.get('/api/payroll/reports/payables/export/csv', {
      params: {
        period_id: filters.period_id,
        user_id: filters.user_id,
        status: filters.status,
        period_type: filters.period_type,
        start_date: filters.start_date,
        end_date: filters.end_date,
      },
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Export payables report as Excel
   */
  exportExcel: async (filters: PayrollReportFilters): Promise<Blob> => {
    const response = await api.get('/api/payroll/reports/payables/export/excel', {
      params: {
        period_id: filters.period_id,
        user_id: filters.user_id,
        status: filters.status,
        period_type: filters.period_type,
        start_date: filters.start_date,
        end_date: filters.end_date,
      },
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Get current user's own payroll report
   */
  getMyPayroll: async (
    periodId?: number,
    startDate?: string,
    endDate?: string
  ): Promise<UserPayrollReport[]> => {
    const response = await api.get('/api/payroll/reports/my-payroll', {
      params: { period_id: periodId, start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};

// ============================================
// EXPORT ALL
// ============================================

export const payrollApi = {
  payRates: payRatesApi,
  periods: payrollPeriodsApi,
  entries: payrollEntriesApi,
  adjustments: payrollAdjustmentsApi,
  reports: payrollReportsApi,
};

export default payrollApi;
