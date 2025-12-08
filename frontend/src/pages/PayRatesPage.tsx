/**
 * Pay Rates Management Page
 * Admin-only page for managing user pay rates
 */

import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  DollarSign, 
  Plus, 
  Edit2, 
  Trash2, 
  History, 
  Search,
  AlertCircle,
  CheckCircle,
  User
} from 'lucide-react';
import { payRatesApi } from '../api/payroll';
import { 
  PayRate, 
  PayRateCreate, 
  PayRateUpdate, 
  RateType,
  PayRateHistory 
} from '../types/payroll';

// Rate Type Labels
const RATE_TYPE_LABELS: Record<RateType, string> = {
  hourly: 'Hourly',
  daily: 'Daily',
  monthly: 'Monthly',
  project_based: 'Project Based',
};

// Currency Options
const CURRENCY_OPTIONS = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'MXN'];

interface PayRateFormData {
  user_id: string;
  rate_type: RateType;
  base_rate: string;
  currency: string;
  overtime_multiplier: string;
  effective_from: string;
  effective_to: string;
  change_reason: string;
}

const initialFormData: PayRateFormData = {
  user_id: '',
  rate_type: 'hourly',
  base_rate: '',
  currency: 'USD',
  overtime_multiplier: '1.5',
  effective_from: new Date().toISOString().split('T')[0],
  effective_to: '',
  change_reason: '',
};

export const PayRatesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRate, setEditingRate] = useState<PayRate | null>(null);
  const [viewingHistory, setViewingHistory] = useState<PayRate | null>(null);
  const [formData, setFormData] = useState<PayRateFormData>(initialFormData);
  const [searchTerm, setSearchTerm] = useState('');
  const [showInactive, setShowInactive] = useState(false);

  // Fetch pay rates
  const { data: ratesData, isLoading, error } = useQuery({
    queryKey: ['payRates', showInactive],
    queryFn: () => payRatesApi.list(0, 500, !showInactive),
  });

  // Fetch history when viewing
  const { data: historyData } = useQuery({
    queryKey: ['payRateHistory', viewingHistory?.id],
    queryFn: () => viewingHistory ? payRatesApi.getHistory(viewingHistory.id) : Promise.resolve([]),
    enabled: !!viewingHistory,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: PayRateCreate) => payRatesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payRates'] });
      setShowCreateModal(false);
      setFormData(initialFormData);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: PayRateUpdate }) =>
      payRatesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payRates'] });
      setEditingRate(null);
      setFormData(initialFormData);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => payRatesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payRates'] });
    },
  });

  // Handle form submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (editingRate) {
      const updateData: PayRateUpdate = {
        rate_type: formData.rate_type,
        base_rate: parseFloat(formData.base_rate),
        currency: formData.currency,
        overtime_multiplier: parseFloat(formData.overtime_multiplier),
        effective_from: formData.effective_from,
        effective_to: formData.effective_to || undefined,
        change_reason: formData.change_reason || undefined,
      };
      updateMutation.mutate({ id: editingRate.id, data: updateData });
    } else {
      const createData: PayRateCreate = {
        user_id: parseInt(formData.user_id),
        rate_type: formData.rate_type,
        base_rate: parseFloat(formData.base_rate),
        currency: formData.currency,
        overtime_multiplier: parseFloat(formData.overtime_multiplier),
        effective_from: formData.effective_from,
        effective_to: formData.effective_to || undefined,
      };
      createMutation.mutate(createData);
    }
  };

  // Open edit modal
  const handleEdit = (rate: PayRate) => {
    setEditingRate(rate);
    setFormData({
      user_id: rate.user_id.toString(),
      rate_type: rate.rate_type as RateType,
      base_rate: rate.base_rate.toString(),
      currency: rate.currency,
      overtime_multiplier: rate.overtime_multiplier.toString(),
      effective_from: rate.effective_from,
      effective_to: rate.effective_to || '',
      change_reason: '',
    });
  };

  // Filter rates
  const filteredRates = ratesData?.items.filter(rate => {
    const searchLower = searchTerm.toLowerCase();
    return (
      rate.user_name?.toLowerCase().includes(searchLower) ||
      rate.user_email?.toLowerCase().includes(searchLower) ||
      rate.rate_type.toLowerCase().includes(searchLower)
    );
  }) || [];

  // Format currency
  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount);
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
        Error loading pay rates
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pay Rates</h1>
          <p className="text-gray-600">Manage employee pay rates and compensation</p>
        </div>
        <button
          onClick={() => {
            setFormData(initialFormData);
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <Plus className="w-4 h-4" />
          Add Pay Rate
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-600">Show Inactive</span>
        </label>
      </div>

      {/* Pay Rates Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Employee
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Rate Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Base Rate
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Overtime
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Effective Period
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredRates.map((rate) => (
              <tr key={rate.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                      <User className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="ml-3">
                      <div className="text-sm font-medium text-gray-900">
                        {rate.user_name || `User #${rate.user_id}`}
                      </div>
                      <div className="text-sm text-gray-500">{rate.user_email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                    {RATE_TYPE_LABELS[rate.rate_type as RateType]}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {formatCurrency(rate.base_rate, rate.currency)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {rate.overtime_multiplier}x
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {rate.effective_from}
                  {rate.effective_to && ` - ${rate.effective_to}`}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {rate.is_active ? (
                    <span className="flex items-center gap-1 text-green-600 text-sm">
                      <CheckCircle className="w-4 h-4" />
                      Active
                    </span>
                  ) : (
                    <span className="text-gray-400 text-sm">Inactive</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setViewingHistory(rate)}
                      className="p-1 text-gray-400 hover:text-blue-600 transition"
                      title="View History"
                    >
                      <History className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleEdit(rate)}
                      className="p-1 text-gray-400 hover:text-blue-600 transition"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    {rate.is_active && (
                      <button
                        onClick={() => {
                          if (confirm('Are you sure you want to deactivate this pay rate?')) {
                            deleteMutation.mutate(rate.id);
                          }
                        }}
                        className="p-1 text-gray-400 hover:text-red-600 transition"
                        title="Deactivate"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {filteredRates.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            <DollarSign className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No pay rates found</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingRate) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">
              {editingRate ? 'Edit Pay Rate' : 'Add New Pay Rate'}
            </h2>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              {!editingRate && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    User ID
                  </label>
                  <input
                    type="number"
                    value={formData.user_id}
                    onChange={(e) => setFormData({ ...formData, user_id: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter user ID"
                  />
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Rate Type
                </label>
                <select
                  value={formData.rate_type}
                  onChange={(e) => setFormData({ ...formData, rate_type: e.target.value as RateType })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {Object.entries(RATE_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Base Rate
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.base_rate}
                    onChange={(e) => setFormData({ ...formData, base_rate: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Currency
                  </label>
                  <select
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {CURRENCY_OPTIONS.map(currency => (
                      <option key={currency} value={currency}>{currency}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Overtime Multiplier
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="1"
                  value={formData.overtime_multiplier}
                  onChange={(e) => setFormData({ ...formData, overtime_multiplier: e.target.value })}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Effective From
                  </label>
                  <input
                    type="date"
                    value={formData.effective_from}
                    onChange={(e) => setFormData({ ...formData, effective_from: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Effective To (Optional)
                  </label>
                  <input
                    type="date"
                    value={formData.effective_to}
                    onChange={(e) => setFormData({ ...formData, effective_to: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              
              {editingRate && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Change Reason (Optional)
                  </label>
                  <textarea
                    value={formData.change_reason}
                    onChange={(e) => setFormData({ ...formData, change_reason: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="Reason for this change..."
                  />
                </div>
              )}
              
              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setEditingRate(null);
                    setFormData(initialFormData);
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
                >
                  {createMutation.isPending || updateMutation.isPending 
                    ? 'Saving...' 
                    : editingRate ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* History Modal */}
      {viewingHistory && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold mb-4">
              Rate History - {viewingHistory.user_name || `User #${viewingHistory.user_id}`}
            </h2>
            
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {historyData && historyData.length > 0 ? (
                historyData.map((history: PayRateHistory) => (
                  <div key={history.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {formatCurrency(history.previous_rate, viewingHistory.currency)} → {formatCurrency(history.new_rate, viewingHistory.currency)}
                        </p>
                        {history.change_reason && (
                          <p className="text-sm text-gray-600 mt-1">{history.change_reason}</p>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(history.changed_at).toLocaleDateString()}
                      </span>
                    </div>
                    {history.changed_by_name && (
                      <p className="text-xs text-gray-500 mt-1">
                        Changed by: {history.changed_by_name}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-center text-gray-500 py-4">No history available</p>
              )}
            </div>
            
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setViewingHistory(null)}
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

export default PayRatesPage;
