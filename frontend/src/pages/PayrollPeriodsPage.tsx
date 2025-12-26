/**
 * Payroll Periods Management Page
 * Admin-only page for managing payroll periods and entries
 */

import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useStaffNotifications } from '../hooks/useStaffNotifications';
import { 
  Calendar, 
  Plus, 
  Edit2, 
  Trash2, 
  Play, 
  CheckCircle, 
  DollarSign,
  AlertCircle,
  ChevronRight,
  Eye,
  Users,
  Filter,
  UserCheck
} from 'lucide-react';
import { payrollPeriodsApi, payRatesApi } from '../api/payroll';
import { 
  PayrollPeriod, 
  PayrollPeriodCreate, 
  PayrollPeriodUpdate, 
  PeriodType, 
  PeriodStatus,
  PayrollEntry,
  RateType,
  PayRate
} from '../types/payroll';

// Rate Type Labels
const RATE_TYPE_LABELS: Record<RateType, string> = {
  hourly: 'Hourly',
  daily: 'Daily',
  monthly: 'Monthly',
  project_based: 'Project Based',
};

// Period Type Labels
const PERIOD_TYPE_LABELS: Record<PeriodType, string> = {
  weekly: 'Weekly',
  bi_weekly: 'Bi-Weekly',
  semi_monthly: 'Semi-Monthly',
  monthly: 'Monthly',
};

// Period Status Colors
const STATUS_COLORS: Record<PeriodStatus, { bg: string; text: string; icon: React.ReactNode }> = {
  draft: { bg: 'bg-gray-100', text: 'text-gray-800', icon: <Edit2 className="w-3 h-3" /> },
  processing: { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: <Play className="w-3 h-3" /> },
  approved: { bg: 'bg-green-100', text: 'text-green-800', icon: <CheckCircle className="w-3 h-3" /> },
  paid: { bg: 'bg-blue-100', text: 'text-blue-800', icon: <DollarSign className="w-3 h-3" /> },
  void: { bg: 'bg-red-100', text: 'text-red-800', icon: <AlertCircle className="w-3 h-3" /> },
};

interface PayrollPeriodFormData {
  name: string;
  period_type: PeriodType;
  start_date: string;
  end_date: string;
  // Employee selection
  user_ids: number[];
  rate_type_filter: RateType | '';
}

const initialFormData: PayrollPeriodFormData = {
  name: '',
  period_type: 'monthly',
  start_date: '',
  end_date: '',
  user_ids: [],
  rate_type_filter: '',
};

export const PayrollPeriodsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const notifications = useStaffNotifications();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState<PayrollPeriod | null>(null);
  const [viewingPeriod, setViewingPeriod] = useState<PayrollPeriod | null>(null);
  const [formData, setFormData] = useState<PayrollPeriodFormData>(initialFormData);
  const [statusFilter, setStatusFilter] = useState<PeriodStatus | ''>('');
  const [selectAll, setSelectAll] = useState(true);

  // Fetch payroll periods
  const { data: periodsData, isLoading, error } = useQuery({
    queryKey: ['payrollPeriods', statusFilter],
    queryFn: () => payrollPeriodsApi.list(0, 100, statusFilter || undefined),
  });

  // Fetch employees with pay rates for selection
  const { data: employeesData } = useQuery({
    queryKey: ['payRatesForSelection'],
    queryFn: () => payRatesApi.list(0, 500, true),
    enabled: showCreateModal || !!editingPeriod,
  });

  // Filter employees based on rate type filter
  const filteredEmployees = useMemo(() => {
    if (!employeesData?.items) return [];
    if (!formData.rate_type_filter) return employeesData.items;
    return employeesData.items.filter(
      (pr: PayRate) => pr.rate_type === formData.rate_type_filter
    );
  }, [employeesData?.items, formData.rate_type_filter]);

  // Fetch payroll periods
  const { data: periodsData, isLoading, error } = useQuery({
    queryKey: ['payrollPeriods', statusFilter],
    queryFn: () => payrollPeriodsApi.list(0, 100, statusFilter || undefined),
  });

  // Fetch period details with entries when viewing
  const { data: periodDetails } = useQuery({
    queryKey: ['payrollPeriodDetails', viewingPeriod?.id],
    queryFn: () => viewingPeriod ? payrollPeriodsApi.get(viewingPeriod.id) : Promise.resolve(null),
    enabled: !!viewingPeriod,
  });

  // Helper to extract error message from various error formats
  const extractErrorMessage = (error: unknown, fallback: string): string => {
    if (error instanceof Error) {
      return error.message;
    }
    const axiosError = error as { response?: { data?: { detail?: string | Array<{ msg?: string; loc?: string[] }> } } };
    const detail = axiosError?.response?.data?.detail;
    
    // Handle Pydantic validation errors (array of error objects)
    if (Array.isArray(detail)) {
      const messages = detail.map(err => {
        const field = err.loc?.slice(-1)[0] || 'field';
        const msg = err.msg || 'Invalid value';
        // Make the message more user-friendly
        if (msg.includes('end_date must be after start_date')) {
          return 'End date must be after start date';
        }
        return `${field}: ${msg}`;
      });
      return messages.join('. ');
    }
    
    // Handle string detail
    if (typeof detail === 'string') {
      return detail;
    }
    
    return fallback;
  };

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: PayrollPeriodCreate) => payrollPeriodsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payrollPeriods'] });
      setShowCreateModal(false);
      setFormData(initialFormData);
      notifications.notifySuccess('Period Created', 'Payroll period created successfully');
    },
    onError: (error: unknown) => {
      const errorMessage = extractErrorMessage(error, 'Failed to create payroll period');
      notifications.notifyError('Create Failed', errorMessage);
      console.error('Create period error:', error);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: PayrollPeriodUpdate }) =>
      payrollPeriodsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payrollPeriods'] });
      setEditingPeriod(null);
      setFormData(initialFormData);
      notifications.notifySuccess('Period Updated', 'Payroll period updated successfully');
    },
    onError: (error: unknown) => {
      const errorMessage = extractErrorMessage(error, 'Failed to update payroll period');
      notifications.notifyError('Update Failed', errorMessage);
      console.error('Update period error:', error);
    },
  });

  // Process mutation
  const processMutation = useMutation({
    mutationFn: (id: number) => payrollPeriodsApi.process(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payrollPeriods'] });
      queryClient.invalidateQueries({ queryKey: ['payrollPeriodDetails'] });
      notifications.notifySuccess('Period Processed', 'Payroll period processed successfully');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error 
        ? error.message 
        : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to process payroll period';
      notifications.notifyError('Process Failed', errorMessage);
    },
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (id: number) => payrollPeriodsApi.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payrollPeriods'] });
      queryClient.invalidateQueries({ queryKey: ['payrollPeriodDetails'] });
      notifications.notifySuccess('Period Approved', 'Payroll period approved successfully');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error 
        ? error.message 
        : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to approve payroll period';
      notifications.notifyError('Approve Failed', errorMessage);
    },
  });

  // Mark paid mutation
  const markPaidMutation = useMutation({
    mutationFn: (id: number) => payrollPeriodsApi.markPaid(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payrollPeriods'] });
      queryClient.invalidateQueries({ queryKey: ['payrollPeriodDetails'] });
      notifications.notifySuccess('Period Paid', 'Payroll period marked as paid');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error 
        ? error.message 
        : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to mark payroll period as paid';
      notifications.notifyError('Mark Paid Failed', errorMessage);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => payrollPeriodsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payrollPeriods'] });
      notifications.notifySuccess('Period Deleted', 'Payroll period deleted');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error 
        ? error.message 
        : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete payroll period';
      notifications.notifyError('Delete Failed', errorMessage);
    },
  });

  // Handle form submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate dates before submission
    if (formData.start_date && formData.end_date) {
      if (new Date(formData.end_date) < new Date(formData.start_date)) {
        notifications.notifyError('Invalid Dates', 'End date must be after start date');
        return;
      }
    }
    
    if (editingPeriod) {
      const updateData: PayrollPeriodUpdate = {
        name: formData.name,
        period_type: formData.period_type,
        start_date: formData.start_date,
        end_date: formData.end_date,
      };
      updateMutation.mutate({ id: editingPeriod.id, data: updateData });
    } else {
      // Determine which user IDs to include
      const userIdsToInclude = selectAll 
        ? [] // Empty array means "all employees"
        : formData.user_ids;
      
      const createData: PayrollPeriodCreate = {
        name: formData.name,
        period_type: formData.period_type,
        start_date: formData.start_date,
        end_date: formData.end_date,
        user_ids: userIdsToInclude.length > 0 ? userIdsToInclude : undefined,
        rate_type_filter: formData.rate_type_filter || undefined,
      };
      createMutation.mutate(createData);
    }
  };

  // Toggle employee selection
  const toggleEmployeeSelection = (userId: number) => {
    setFormData(prev => ({
      ...prev,
      user_ids: prev.user_ids.includes(userId)
        ? prev.user_ids.filter(id => id !== userId)
        : [...prev.user_ids, userId]
    }));
    setSelectAll(false);
  };

  // Select all employees (based on current filter)
  const handleSelectAll = () => {
    if (selectAll) {
      // Deselect all - switch to manual selection
      setSelectAll(false);
      setFormData(prev => ({ ...prev, user_ids: [] }));
    } else {
      // Select all - switch back to "all employees" mode
      setSelectAll(true);
      setFormData(prev => ({ ...prev, user_ids: [] }));
    }
  };

  // Handle rate type filter change
  const handleRateTypeFilterChange = (rateType: RateType | '') => {
    setFormData(prev => ({
      ...prev,
      rate_type_filter: rateType,
      user_ids: [] // Reset selections when filter changes
    }));
    setSelectAll(true); // Reset to "all employees" in the filtered group
  };

  // Open edit modal
  const handleEdit = (period: PayrollPeriod) => {
    setEditingPeriod(period);
    setFormData({
      name: period.name,
      period_type: period.period_type as PeriodType,
      start_date: period.start_date,
      end_date: period.end_date,
    });
  };

  // English month names (always English regardless of browser locale)
  const ENGLISH_MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  // Generate period name (always in English)
  const generatePeriodName = (type: PeriodType, startDate: string, endDate?: string) => {
    if (!startDate) return '';
    // Parse as local date to avoid timezone issues
    const [startYear, startMonth] = startDate.split('-').map(Number);
    const startMonthName = ENGLISH_MONTHS[startMonth - 1];
    
    if (endDate) {
      const [endYear, endMonth] = endDate.split('-').map(Number);
      const endMonthName = ENGLISH_MONTHS[endMonth - 1];
      
      // If same month, just use single month
      if (startYear === endYear && startMonth === endMonth) {
        return `${startMonthName} ${startYear} - ${PERIOD_TYPE_LABELS[type]}`;
      }
      // If different months but same year
      if (startYear === endYear) {
        return `${startMonthName}-${endMonthName} ${startYear} - ${PERIOD_TYPE_LABELS[type]}`;
      }
      // Different years
      return `${startMonthName} ${startYear} - ${endMonthName} ${endYear} - ${PERIOD_TYPE_LABELS[type]}`;
    }
    
    return `${startMonthName} ${startYear} - ${PERIOD_TYPE_LABELS[type]}`;
  };

  // Auto-generate name when dates change
  const handleDateChange = (field: 'start_date' | 'end_date', value: string) => {
    const newFormData = { ...formData, [field]: value };
    // Auto-generate name when start_date changes OR when we have both dates
    if (field === 'start_date' && value) {
      newFormData.name = generatePeriodName(newFormData.period_type, value, newFormData.end_date);
    } else if (field === 'end_date' && newFormData.start_date && value) {
      newFormData.name = generatePeriodName(newFormData.period_type, newFormData.start_date, value);
    }
    setFormData(newFormData);
  };

  // Regenerate name when period type changes
  const handlePeriodTypeChange = (type: PeriodType) => {
    const newFormData = { ...formData, period_type: type };
    if (formData.start_date) {
      newFormData.name = generatePeriodName(type, formData.start_date, formData.end_date);
    }
    setFormData(newFormData);
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Format date for display (always in English)
  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const [year, month, day] = dateStr.split('-').map(Number);
    const monthName = ENGLISH_MONTHS[month - 1];
    return `${monthName} ${day}, ${year}`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 text-red-600 rounded-lg flex items-center gap-2">
        <AlertCircle className="w-5 h-5" />
        Error loading payroll periods
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Payroll Periods</h1>
          <p className="text-gray-600">Manage payroll processing cycles</p>
        </div>
        <button
          onClick={() => {
            setFormData(initialFormData);
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <Plus className="w-4 h-4" />
          New Period
        </button>
      </div>

      {/* Status Filter */}
      <div className="flex gap-2">
        <button
          onClick={() => setStatusFilter('')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
            statusFilter === '' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          All
        </button>
        {(Object.keys(STATUS_COLORS) as PeriodStatus[]).map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              statusFilter === status 
                ? 'bg-blue-600 text-white' 
                : `${STATUS_COLORS[status].bg} ${STATUS_COLORS[status].text} hover:opacity-80`
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Periods Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {periodsData?.items.map((period) => (
          <div
            key={period.id}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition"
          >
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-semibold text-gray-900">{period.name}</h3>
                <p className="text-sm text-gray-500">
                  {PERIOD_TYPE_LABELS[period.period_type as PeriodType]}
                </p>
              </div>
              <span className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[period.status as PeriodStatus].bg} ${STATUS_COLORS[period.status as PeriodStatus].text}`}>
                {STATUS_COLORS[period.status as PeriodStatus].icon}
                {period.status.charAt(0).toUpperCase() + period.status.slice(1)}
              </span>
            </div>
            
            <div className="space-y-2 mb-4">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Calendar className="w-4 h-4" />
                {formatDate(period.start_date)} - {formatDate(period.end_date)}
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Users className="w-4 h-4" />
                {period.entries_count} entries
              </div>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                <DollarSign className="w-4 h-4" />
                {formatCurrency(period.total_amount)}
              </div>
            </div>
            
            <div className="flex justify-between items-center pt-3 border-t border-gray-100">
              <div className="flex gap-1">
                {period.status === 'draft' && (
                  <>
                    <button
                      onClick={() => processMutation.mutate(period.id)}
                      disabled={processMutation.isPending}
                      className="p-1.5 text-blue-600 hover:bg-blue-50 rounded transition"
                      title="Process Period"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleEdit(period)}
                      className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded transition"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                  </>
                )}
                {/* Delete button - always available */}
                <button
                  onClick={() => {
                    const warning = period.status === 'paid' 
                      ? `⚠️ WARNING: This period has been marked as PAID.\n\nAre you sure you want to delete "${period.name}"? This cannot be undone.`
                      : `Are you sure you want to delete "${period.name}"?`;
                    if (confirm(warning)) {
                      deleteMutation.mutate(period.id);
                    }
                  }}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                {(period.status === 'draft' || period.status === 'processing') && (
                  <button
                    onClick={() => approveMutation.mutate(period.id)}
                    disabled={approveMutation.isPending}
                    className="p-1.5 text-green-600 hover:bg-green-50 rounded transition"
                    title="Approve Period"
                  >
                    <CheckCircle className="w-4 h-4" />
                  </button>
                )}
                {period.status === 'approved' && (
                  <button
                    onClick={() => markPaidMutation.mutate(period.id)}
                    disabled={markPaidMutation.isPending}
                    className="p-1.5 text-blue-600 hover:bg-blue-50 rounded transition"
                    title="Mark as Paid"
                  >
                    <DollarSign className="w-4 h-4" />
                  </button>
                )}
              </div>
              <button
                onClick={() => setViewingPeriod(period)}
                className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 transition"
              >
                <Eye className="w-4 h-4" />
                View Details
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {periodsData?.items.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm">
          <Calendar className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p className="text-gray-500">No payroll periods found</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 text-blue-600 hover:text-blue-700"
          >
            Create your first period
          </button>
        </div>
      )}

      {/* Create/Edit Modal */}
      {(showCreateModal || editingPeriod) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold">
                {editingPeriod ? 'Edit Payroll Period' : 'Create New Payroll Period'}
              </h2>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 overflow-y-auto max-h-[calc(90vh-160px)] space-y-4">
              {/* Period Settings */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Period Type
                  </label>
                  <select
                    value={formData.period_type}
                    onChange={(e) => handlePeriodTypeChange(e.target.value as PeriodType)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {Object.entries(PERIOD_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Period Name
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., January 2025 - Monthly"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={formData.start_date}
                    onChange={(e) => handleDateChange('start_date', e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    End Date
                  </label>
                  <input
                    type="date"
                    value={formData.end_date}
                    onChange={(e) => handleDateChange('end_date', e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              
              {/* Employee Selection Section (only for new periods) */}
              {!editingPeriod && (
                <div className="border-t pt-4 mt-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Users className="w-5 h-5 text-gray-600" />
                      <h3 className="font-medium text-gray-900">Employee Selection</h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <Filter className="w-4 h-4 text-gray-400" />
                      <select
                        value={formData.rate_type_filter}
                        onChange={(e) => handleRateTypeFilterChange(e.target.value as RateType | '')}
                        className="text-sm px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">All Rate Types</option>
                        {Object.entries(RATE_TYPE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  
                  {/* Select All Toggle */}
                  <div className="mb-3 p-3 bg-gray-50 rounded-lg">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectAll}
                        onChange={handleSelectAll}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <div className="flex items-center gap-2">
                        <UserCheck className="w-4 h-4 text-blue-600" />
                        <span className="font-medium text-gray-700">
                          {selectAll 
                            ? `Include all ${formData.rate_type_filter ? RATE_TYPE_LABELS[formData.rate_type_filter] : ''} employees (${filteredEmployees.length})`
                            : 'Select specific employees'}
                        </span>
                      </div>
                    </label>
                    {selectAll && formData.rate_type_filter && (
                      <p className="mt-2 text-sm text-blue-600 ml-7">
                        ✓ Only {RATE_TYPE_LABELS[formData.rate_type_filter].toLowerCase()} rate employees will be included
                      </p>
                    )}
                  </div>
                  
                  {/* Employee List (only show when not "select all") */}
                  {!selectAll && (
                    <div className="border rounded-lg max-h-48 overflow-y-auto">
                      {filteredEmployees.length === 0 ? (
                        <p className="p-4 text-center text-gray-500">
                          No employees found{formData.rate_type_filter ? ` with ${RATE_TYPE_LABELS[formData.rate_type_filter].toLowerCase()} rate` : ''}
                        </p>
                      ) : (
                        <div className="divide-y divide-gray-100">
                          {filteredEmployees.map((payRate: PayRate) => (
                            <label
                              key={payRate.user_id}
                              className="flex items-center gap-3 p-3 hover:bg-gray-50 cursor-pointer transition"
                            >
                              <input
                                type="checkbox"
                                checked={formData.user_ids.includes(payRate.user_id)}
                                onChange={() => toggleEmployeeSelection(payRate.user_id)}
                                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                              />
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-gray-900 truncate">
                                  {payRate.user_name || `User #${payRate.user_id}`}
                                </p>
                                <p className="text-xs text-gray-500 truncate">
                                  {payRate.user_email}
                                </p>
                              </div>
                              <div className="text-right">
                                <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                                  payRate.rate_type === 'hourly' ? 'bg-green-100 text-green-700' :
                                  payRate.rate_type === 'monthly' ? 'bg-blue-100 text-blue-700' :
                                  payRate.rate_type === 'daily' ? 'bg-yellow-100 text-yellow-700' :
                                  'bg-purple-100 text-purple-700'
                                }`}>
                                  {RATE_TYPE_LABELS[payRate.rate_type as RateType]}
                                </span>
                                <p className="text-xs text-gray-500 mt-0.5">
                                  ${payRate.base_rate.toFixed(2)}/{payRate.rate_type === 'hourly' ? 'hr' : payRate.rate_type === 'daily' ? 'day' : 'mo'}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Selection Summary */}
                  {!selectAll && formData.user_ids.length > 0 && (
                    <p className="mt-2 text-sm text-gray-600">
                      {formData.user_ids.length} employee{formData.user_ids.length !== 1 ? 's' : ''} selected
                    </p>
                  )}
                  {!selectAll && formData.user_ids.length === 0 && (
                    <p className="mt-2 text-sm text-amber-600">
                      ⚠️ No employees selected. Select at least one employee or choose "Include all employees".
                    </p>
                  )}
                </div>
              )}
              
              {/* Form Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setEditingPeriod(null);
                    setFormData(initialFormData);
                    setSelectAll(true);
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    createMutation.isPending || 
                    updateMutation.isPending ||
                    (!editingPeriod && !selectAll && formData.user_ids.length === 0)
                  }
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
                >
                  {createMutation.isPending || updateMutation.isPending 
                    ? 'Saving...' 
                    : editingPeriod ? 'Update' : 'Create Period'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Period Details Modal */}
      {viewingPeriod && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-lg font-semibold">{viewingPeriod.name}</h2>
                  <p className="text-sm text-gray-500">
                    {formatDate(viewingPeriod.start_date)} - {formatDate(viewingPeriod.end_date)}
                  </p>
                </div>
                <span className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[viewingPeriod.status as PeriodStatus].bg} ${STATUS_COLORS[viewingPeriod.status as PeriodStatus].text}`}>
                  {viewingPeriod.status.charAt(0).toUpperCase() + viewingPeriod.status.slice(1)}
                </span>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[calc(80vh-200px)]">
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm text-blue-600 font-medium">Total Employees</p>
                  <p className="text-2xl font-bold text-blue-700">
                    {periodDetails?.entries?.length || 0}
                  </p>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <p className="text-sm text-green-600 font-medium">Gross Amount</p>
                  <p className="text-2xl font-bold text-green-700">
                    {formatCurrency(viewingPeriod.total_amount)}
                  </p>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <p className="text-sm text-purple-600 font-medium">Period Type</p>
                  <p className="text-2xl font-bold text-purple-700">
                    {PERIOD_TYPE_LABELS[viewingPeriod.period_type as PeriodType]}
                  </p>
                </div>
              </div>
              
              <h3 className="font-semibold mb-3">Payroll Entries</h3>
              {periodDetails?.entries && periodDetails.entries.length > 0 ? (
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Employee</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Rate Type</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Hours/Base</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">OT Hours</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Gross</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Adjustments</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Net</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {periodDetails.entries.map((entry: PayrollEntry) => {
                      const rateType = entry.rate_type || 'hourly';
                      const isSalaried = rateType === 'monthly' || rateType === 'project_based';
                      
                      return (
                        <tr key={entry.id}>
                          <td className="px-4 py-2">
                            <div className="text-sm font-medium text-gray-900">
                              {entry.user_name || `User #${entry.user_id}`}
                            </div>
                            <div className="text-xs text-gray-500">{entry.user_email}</div>
                          </td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-1 text-xs rounded-full ${
                              rateType === 'monthly' ? 'bg-purple-100 text-purple-700' :
                              rateType === 'daily' ? 'bg-blue-100 text-blue-700' :
                              rateType === 'project_based' ? 'bg-green-100 text-green-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {rateType === 'monthly' ? 'Monthly' :
                               rateType === 'daily' ? 'Daily' :
                               rateType === 'project_based' ? 'Project' :
                               'Hourly'}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-sm">
                            {isSalaried ? (
                              <span className="text-gray-400">—</span>
                            ) : (
                              Number(entry.regular_hours).toFixed(2)
                            )}
                          </td>
                          <td className="px-4 py-2 text-sm">
                            {isSalaried ? (
                              <span className="text-gray-400">—</span>
                            ) : (
                              Number(entry.overtime_hours).toFixed(2)
                            )}
                          </td>
                          <td className="px-4 py-2 text-sm">{formatCurrency(entry.gross_amount)}</td>
                          <td className="px-4 py-2 text-sm">{formatCurrency(entry.adjustments_amount)}</td>
                          <td className="px-4 py-2 text-sm font-medium">{formatCurrency(entry.net_amount)}</td>
                          <td className="px-4 py-2">
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-600">
                              {entry.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <p className="text-center text-gray-500 py-4">No entries yet. Process the period to generate entries.</p>
              )}
            </div>
            
            <div className="p-6 border-t border-gray-200 flex justify-between">
              {/* Delete button - always available */}
              <button
                onClick={() => {
                  const warning = viewingPeriod.status === 'paid' 
                    ? `⚠️ WARNING: This period has been marked as PAID.\n\nAre you sure you want to delete "${viewingPeriod.name}"? This action cannot be undone.`
                    : `Are you sure you want to delete "${viewingPeriod.name}"? This action cannot be undone.`;
                  if (confirm(warning)) {
                    deleteMutation.mutate(viewingPeriod.id);
                    setViewingPeriod(null);
                  }
                }}
                disabled={deleteMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition disabled:opacity-50"
              >
                <Trash2 className="w-4 h-4" />
                Delete Period
              </button>
              <button
                onClick={() => setViewingPeriod(null)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PayrollPeriodsPage;
