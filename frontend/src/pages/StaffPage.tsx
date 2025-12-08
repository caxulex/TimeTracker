// ============================================
// TIME TRACKER - STAFF MANAGEMENT PAGE
// ============================================
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { usersApi, teamsApi, payRatesApi, timeEntriesApi, projectsApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import type { User, UserCreate, Team, TeamMember, PayRate, TimeEntry, Project } from '../types';

export function StaffPage() {
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showTeamsModal, setShowTeamsModal] = useState(false);
  const [showPayrollModal, setShowPayrollModal] = useState(false);
  const [showTimeModal, setShowTimeModal] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState<User | null>(null);
  const [formStep, setFormStep] = useState(1); // Multi-step form
  
  const [createForm, setCreateForm] = useState({
    // Basic Info
    email: '',
    password: '',
    name: '',
    role: 'regular_user',
    
    // Contact Information
    phone: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    
    // Employment Details
    job_title: '',
    department: '',
    employment_type: 'full_time' as 'full_time' | 'part_time' | 'contractor',
    start_date: new Date().toISOString().split('T')[0],
    expected_hours_per_week: 40,
    manager_id: null as number | null,
    
    // Payroll Information
    pay_rate: 0,
    pay_rate_type: 'hourly' as 'hourly' | 'daily' | 'monthly' | 'project_based',
    overtime_multiplier: 1.5,
    currency: 'USD',
    
    // Team Assignment
    team_ids: [] as number[],
  });
  
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
  });

  const isAdmin = currentUser?.role === 'super_admin';

  // Fetch staff members
  const { data: usersData, isLoading } = useQuery({
    queryKey: ['staff', page, search],
    queryFn: () => usersApi.getAll(page, 20, search),
    enabled: isAdmin,
  });

  // Fetch all teams
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(1, 100),
    enabled: isAdmin,
  });

  // Create staff mutation
  const createStaffMutation = useMutation({
    mutationFn: (data: typeof createForm) => usersApi.create(data as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      setShowCreateModal(false);
      setFormStep(1);
      // Reset form
      setCreateForm({
        email: '',
        password: '',
        name: '',
        role: 'regular_user',
        phone: '',
        address: '',
        emergency_contact_name: '',
        emergency_contact_phone: '',
        job_title: '',
        department: '',
        employment_type: 'full_time',
        start_date: new Date().toISOString().split('T')[0],
        expected_hours_per_week: 40,
        manager_id: null,
        pay_rate: 0,
        pay_rate_type: 'hourly',
        overtime_multiplier: 1.5,
        currency: 'USD',
        team_ids: [],
      });
    },
  });

  // Update staff mutation
  const updateStaffMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<User> }) =>
      usersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      setShowEditModal(false);
      setSelectedStaff(null);
    },
  });

  // Toggle active mutation
  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, isActive }: { id: number; isActive: boolean }) => {
      if (!isActive) {
        return usersApi.delete(id);
      } else {
        return usersApi.update(id, { is_active: true });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
  });

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card>
          <div className="text-center p-8">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h2>
            <p className="text-gray-500">Admin privileges required.</p>
          </div>
        </Card>
      </div>
    );
  }

  if (isLoading) {
    return <LoadingOverlay message="Loading staff..." />;
  }

  const handleCreateStaff = (e: React.FormEvent) => {
    e.preventDefault();
    createStaffMutation.mutate(createForm);
  };

  const handleEditStaff = (staff: User) => {
    setSelectedStaff(staff);
    setEditForm({
      name: staff.name,
      email: staff.email,
    });
    setShowEditModal(true);
  };

  const handleUpdateStaff = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedStaff) {
      updateStaffMutation.mutate({ id: selectedStaff.id, data: editForm });
    }
  };

  const handleToggleActive = (staff: User) => {
    if (staff.id === currentUser?.id) {
      alert("You can't deactivate yourself!");
      return;
    }
    const action = staff.is_active ? 'deactivate' : 'activate';
    if (confirm(`Are you sure you want to ${action} ${staff.name}?`)) {
      toggleActiveMutation.mutate({ id: staff.id, isActive: staff.is_active });
    }
  };

  const handleManageTeams = (staff: User) => {
    setSelectedStaff(staff);
    setShowTeamsModal(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Staff Management</h1>
          <p className="text-gray-500">Create and manage workers, assign teams</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Staff Member
        </Button>
      </div>

      {/* Search */}
      <Card padding="sm">
        <input
          type="text"
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </Card>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <div className="text-center p-4">
            <div className="text-3xl font-bold text-blue-600">{usersData?.total || 0}</div>
            <div className="text-sm text-gray-500">Total Staff</div>
          </div>
        </Card>
        <Card>
          <div className="text-center p-4">
            <div className="text-3xl font-bold text-green-600">
              {usersData?.items.filter((u: User) => u.is_active).length || 0}
            </div>
            <div className="text-sm text-gray-500">Active</div>
          </div>
        </Card>
        <Card>
          <div className="text-center p-4">
            <div className="text-3xl font-bold text-gray-600">
              {teamsData?.total || 0}
            </div>
            <div className="text-sm text-gray-500">Teams</div>
          </div>
        </Card>
      </div>

      {/* Staff List */}
      <Card>
        <CardHeader title="Staff Members" />
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Job Title
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Department
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Employment
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
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
              {usersData?.items.map((staff: User) => (
                <tr key={staff.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="h-10 w-10 flex-shrink-0 bg-blue-500 rounded-full flex items-center justify-center text-white font-semibold">
                        {staff.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">{staff.name}</div>
                        <div className="text-xs text-gray-500">{staff.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{staff.job_title || '—'}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{staff.department || '—'}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {staff.employment_type ? (
                      <span
                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          staff.employment_type === 'full_time'
                            ? 'bg-blue-100 text-blue-800'
                            : staff.employment_type === 'part_time'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-purple-100 text-purple-800'
                        }`}
                      >
                        {staff.employment_type === 'full_time' ? 'Full-time' : 
                         staff.employment_type === 'part_time' ? 'Part-time' : 'Contractor'}
                      </span>
                    ) : (
                      <span className="text-sm text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        staff.role === 'super_admin'
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {staff.role === 'super_admin' ? 'Admin' : 'Worker'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        staff.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {staff.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleEditStaff(staff)}
                        className="text-blue-600 hover:text-blue-900"
                        title="Edit Staff"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => {
                          setSelectedStaff(staff);
                          setShowPayrollModal(true);
                        }}
                        className="text-emerald-600 hover:text-emerald-900"
                        title="View Payroll"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => {
                          setSelectedStaff(staff);
                          setShowTimeModal(true);
                        }}
                        className="text-indigo-600 hover:text-indigo-900"
                        title="View Time Tracking"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleManageTeams(staff)}
                        className="text-green-600 hover:text-green-900"
                        title="Manage Teams"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleToggleActive(staff)}
                        className={`${
                          staff.is_active ? 'text-red-600 hover:text-red-900' : 'text-green-600 hover:text-green-900'
                        }`}
                        title={staff.is_active ? 'Deactivate' : 'Activate'}
                        disabled={staff.id === currentUser?.id}
                      >
                        {staff.is_active ? (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                            />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Create Staff Modal - Multi-Step Wizard */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 overflow-y-auto">
          <Card className="max-w-2xl w-full my-8">
            <CardHeader title="Add New Staff Member" />
            
            {/* Progress Indicator */}
            <div className="px-6 pt-4">
              <div className="flex items-center justify-between mb-8">
                {[1, 2, 3, 4].map((step) => (
                  <div key={step} className="flex items-center flex-1">
                    <div className="flex flex-col items-center flex-1">
                      <div
                        className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                          formStep === step
                            ? 'bg-blue-600 text-white'
                            : formStep > step
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-200 text-gray-500'
                        }`}
                      >
                        {formStep > step ? '✓' : step}
                      </div>
                      <div className="text-xs mt-2 text-center font-medium">
                        {step === 1 && 'Basic Info'}
                        {step === 2 && 'Employment'}
                        {step === 3 && 'Contact'}
                        {step === 4 && 'Payroll & Teams'}
                      </div>
                    </div>
                    {step < 4 && (
                      <div
                        className={`h-1 flex-1 ${
                          formStep > step ? 'bg-green-500' : 'bg-gray-200'
                        }`}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>

            <form onSubmit={handleCreateStaff} className="space-y-4 px-6 pb-6">
              {/* Step 1: Basic Information */}
              {formStep === 1 && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Basic Information</h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Full Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={createForm.name}
                      onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="John Doe"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email Address <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="email"
                      required
                      value={createForm.email}
                      onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="john.doe@company.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Password <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={createForm.password}
                      onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="Minimum 8 characters"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      User can change this after first login
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Role <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={createForm.role}
                      onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="regular_user">Worker</option>
                      <option value="super_admin">Admin</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Step 2: Employment Details */}
              {formStep === 2 && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Employment Details</h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Job Title</label>
                    <input
                      type="text"
                      value={createForm.job_title}
                      onChange={(e) => setCreateForm({ ...createForm, job_title: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="e.g., Software Engineer, Project Manager"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                    <input
                      type="text"
                      value={createForm.department}
                      onChange={(e) => setCreateForm({ ...createForm, department: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="e.g., Engineering, Sales, Operations"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Employment Type <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={createForm.employment_type}
                      onChange={(e) => setCreateForm({ ...createForm, employment_type: e.target.value as any })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="full_time">Full-time</option>
                      <option value="part_time">Part-time</option>
                      <option value="contractor">Contractor</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                    <input
                      type="date"
                      value={createForm.start_date}
                      onChange={(e) => setCreateForm({ ...createForm, start_date: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Expected Hours per Week
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="168"
                      value={createForm.expected_hours_per_week}
                      onChange={(e) => setCreateForm({ ...createForm, expected_hours_per_week: parseInt(e.target.value) || 40 })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Used for time tracking and payroll calculations
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Manager</label>
                    <select
                      value={createForm.manager_id || ''}
                      onChange={(e) => setCreateForm({ ...createForm, manager_id: e.target.value ? parseInt(e.target.value) : null })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">None</option>
                      {usersData?.items.filter((u: User) => u.role === 'super_admin').map((user: User) => (
                        <option key={user.id} value={user.id}>
                          {user.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* Step 3: Contact Information */}
              {formStep === 3 && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Contact Information</h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                    <input
                      type="tel"
                      value={createForm.phone}
                      onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      placeholder="+1 (555) 123-4567"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                    <textarea
                      value={createForm.address}
                      onChange={(e) => setCreateForm({ ...createForm, address: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                      rows={3}
                      placeholder="Street address, City, State, ZIP"
                    />
                  </div>
                  <div className="border-t pt-4">
                    <h4 className="font-medium text-gray-900 mb-3">Emergency Contact</h4>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Contact Name
                        </label>
                        <input
                          type="text"
                          value={createForm.emergency_contact_name}
                          onChange={(e) => setCreateForm({ ...createForm, emergency_contact_name: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                          placeholder="Emergency contact full name"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Contact Phone
                        </label>
                        <input
                          type="tel"
                          value={createForm.emergency_contact_phone}
                          onChange={(e) => setCreateForm({ ...createForm, emergency_contact_phone: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                          placeholder="+1 (555) 987-6543"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 4: Payroll & Teams */}
              {formStep === 4 && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Payroll & Team Assignment</h3>
                  <div className="border-b pb-4">
                    <h4 className="font-medium text-gray-900 mb-3">Payroll Information</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Pay Rate</label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={createForm.pay_rate}
                          onChange={(e) => setCreateForm({ ...createForm, pay_rate: parseFloat(e.target.value) || 0 })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                          placeholder="0.00"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Rate Type</label>
                        <select
                          value={createForm.pay_rate_type}
                          onChange={(e) => setCreateForm({ ...createForm, pay_rate_type: e.target.value as any })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="hourly">Hourly</option>
                          <option value="daily">Daily</option>
                          <option value="monthly">Monthly</option>
                          <option value="project_based">Project-based</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Overtime Multiplier
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="1"
                          max="3"
                          value={createForm.overtime_multiplier}
                          onChange={(e) => setCreateForm({ ...createForm, overtime_multiplier: parseFloat(e.target.value) || 1.5 })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                        />
                        <p className="text-xs text-gray-500 mt-1">1.5 = time and a half</p>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                        <select
                          value={createForm.currency}
                          onChange={(e) => setCreateForm({ ...createForm, currency: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="USD">USD</option>
                          <option value="EUR">EUR</option>
                          <option value="GBP">GBP</option>
                          <option value="MXN">MXN</option>
                        </select>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      💡 PayRate will be automatically created if pay rate is greater than 0
                    </p>
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 mb-3">Team Assignment</h4>
                    <div className="space-y-2 max-h-48 overflow-y-auto border rounded-md p-3">
                      {teamsData?.items.length === 0 ? (
                        <p className="text-sm text-gray-500 text-center py-4">
                          No teams available. Create teams first.
                        </p>
                      ) : (
                        teamsData?.items.map((team: Team) => (
                          <label key={team.id} className="flex items-center space-x-3 p-2 hover:bg-gray-50 rounded cursor-pointer">
                            <input
                              type="checkbox"
                              checked={createForm.team_ids.includes(team.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setCreateForm({ ...createForm, team_ids: [...createForm.team_ids, team.id] });
                                } else {
                                  setCreateForm({ ...createForm, team_ids: createForm.team_ids.filter(id => id !== team.id) });
                                }
                              }}
                              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <div className="flex-1">
                              <div className="text-sm font-medium text-gray-900">{team.name}</div>
                              <div className="text-xs text-gray-500">{team.member_count} members</div>
                            </div>
                          </label>
                        ))
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      Selected teams: {createForm.team_ids.length}
                    </p>
                  </div>
                </div>
              )}

              {/* Navigation Buttons */}
              <div className="flex gap-2 justify-between pt-6 border-t">
                <div>
                  {formStep > 1 && (
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => setFormStep(formStep - 1)}
                    >
                      ← Previous
                    </Button>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setShowCreateModal(false);
                      setFormStep(1);
                    }}
                  >
                    Cancel
                  </Button>
                  {formStep < 4 ? (
                    <Button
                      type="button"
                      onClick={() => setFormStep(formStep + 1)}
                    >
                      Next →
                    </Button>
                  ) : (
                    <Button type="submit" loading={createStaffMutation.isPending}>
                      Create Staff Member
                    </Button>
                  )}
                </div>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Edit Staff Modal */}
      {showEditModal && selectedStaff && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="max-w-md w-full">
            <CardHeader title="Edit Staff Member" />
            <form onSubmit={handleUpdateStaff} className="space-y-4 p-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setShowEditModal(false);
                    setSelectedStaff(null);
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" loading={updateStaffMutation.isPending}>
                  Save Changes
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Manage Teams Modal */}
      {showTeamsModal && selectedStaff && (
        <ManageTeamsModal
          staff={selectedStaff}
          onClose={() => {
            setShowTeamsModal(false);
            setSelectedStaff(null);
          }}
        />
      )}

      {/* Payroll Modal */}
      {showPayrollModal && selectedStaff && (
        <PayrollModal
          staff={selectedStaff}
          onClose={() => {
            setShowPayrollModal(false);
            setSelectedStaff(null);
          }}
        />
      )}

      {/* Time Tracking Modal */}
      {showTimeModal && selectedStaff && (
        <TimeTrackingModal
          staff={selectedStaff}
          onClose={() => {
            setShowTimeModal(false);
            setSelectedStaff(null);
          }}
        />
      )}
    </div>
  );
}

// Manage Teams & Projects Modal Component
function ManageTeamsModal({ staff, onClose }: { staff: User; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'current' | 'add' | 'projects'>('current');

  // Fetch all teams
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(1, 100),
  });

  // Fetch staff's current teams with details
  const { data: staffTeams, isLoading: loadingStaffTeams } = useQuery({
    queryKey: ['staff-teams', staff.id],
    queryFn: async () => {
      if (!teamsData?.items) return [];
      const teams = [];
      for (const team of teamsData.items) {
        try {
          const teamDetail = await teamsApi.getById(team.id);
          const member = teamDetail.members?.find((m: TeamMember) => m.user_id === staff.id);
          if (member) {
            teams.push({
              ...team,
              memberRole: member.role,
              members: teamDetail.members,
            });
          }
        } catch (error) {
          // User doesn't have access to this team or team doesn't exist
        }
      }
      return teams;
    },
    enabled: !!teamsData,
  });

  // Fetch projects accessible through teams
  const { data: projectsData, isLoading: loadingProjects } = useQuery({
    queryKey: ['staff-projects', staff.id],
    queryFn: () => projectsApi.getAll({ page: 1, size: 100 }),
  });

  const addToTeamMutation = useMutation({
    mutationFn: ({ teamId, userId, role }: { teamId: number; userId: number; role: string }) =>
      teamsApi.addMember(teamId, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['staff-teams', staff.id] });
      queryClient.invalidateQueries({ queryKey: ['staff-projects', staff.id] });
      alert('Staff member added to team successfully!');
      setActiveTab('current');
    },
  });

  const removeFromTeamMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      teamsApi.removeMember(teamId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['staff-teams', staff.id] });
      queryClient.invalidateQueries({ queryKey: ['staff-projects', staff.id] });
      alert('Staff member removed from team successfully!');
    },
  });

  const updateMemberRoleMutation = useMutation({
    mutationFn: ({ teamId, userId, role }: { teamId: number; userId: number; role: string }) =>
      teamsApi.updateMember(teamId, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['staff-teams', staff.id] });
      alert('Member role updated successfully!');
    },
  });

  const handleAddToTeam = (teamId: number) => {
    if (confirm(`Add ${staff.name} to this team?`)) {
      addToTeamMutation.mutate({ teamId, userId: staff.id, role: 'member' });
    }
  };

  const handleRemoveFromTeam = (teamId: number, teamName: string) => {
    if (confirm(`Remove ${staff.name} from "${teamName}"? They will lose access to all projects in this team.`)) {
      removeFromTeamMutation.mutate({ teamId, userId: staff.id });
    }
  };

  const handleToggleRole = (teamId: number, currentRole: string) => {
    const newRole = currentRole === 'admin' ? 'member' : 'admin';
    if (confirm(`Change role to ${newRole}?`)) {
      updateMemberRoleMutation.mutate({ teamId, userId: staff.id, role: newRole });
    }
  };

  const availableTeams = teamsData?.items.filter(
    (team: Team) => !staffTeams?.some((st: any) => st.id === team.id)
  ) || [];

  // Filter projects that belong to staff's teams
  const staffProjects = projectsData?.items.filter((project: Project) =>
    staffTeams?.some((team: any) => team.id === project.team_id)
  ) || [];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col">
        <CardHeader title={`Teams & Projects - ${staff.name}`} />
        
        {/* Tabs */}
        <div className="border-b border-gray-200 px-6">
          <div className="flex space-x-8">
            <button
              onClick={() => setActiveTab('current')}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'current'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                Current Teams ({staffTeams?.length || 0})
              </div>
            </button>
            <button
              onClick={() => setActiveTab('add')}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'add'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add to Team ({availableTeams.length})
              </div>
            </button>
            <button
              onClick={() => setActiveTab('projects')}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'projects'
                  ? 'border-purple-500 text-purple-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                Accessible Projects ({staffProjects.length})
              </div>
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Current Teams Tab */}
          {activeTab === 'current' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Teams this staff member belongs to with their roles and permissions.
              </p>
              {loadingStaffTeams ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mx-auto"></div>
                </div>
              ) : staffTeams && staffTeams.length > 0 ? (
                <div className="space-y-3">
                  {staffTeams.map((team: any) => (
                    <div key={team.id} className="border border-gray-200 rounded-lg p-4 hover:border-green-300 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h4 className="font-semibold text-gray-900">{team.name}</h4>
                            <span
                              className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                team.memberRole === 'admin'
                                  ? 'bg-purple-100 text-purple-800'
                                  : 'bg-green-100 text-green-800'
                              }`}
                            >
                              {team.memberRole === 'admin' ? '👑 Admin' : '👤 Member'}
                            </span>
                          </div>
                          <div className="text-sm text-gray-600">
                            {team.members?.length || 0} members • Created {new Date(team.created_at).toLocaleDateString()}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleToggleRole(team.id, team.memberRole)}
                            disabled={updateMemberRoleMutation.isPending}
                            className="px-3 py-1.5 text-sm font-medium text-purple-600 hover:text-purple-700 hover:bg-purple-50 rounded-md transition-colors disabled:opacity-50"
                            title={team.memberRole === 'admin' ? 'Demote to member' : 'Promote to admin'}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleRemoveFromTeam(team.id, team.name)}
                            disabled={removeFromTeamMutation.isPending}
                            className="px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                            title="Remove from team"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50 rounded-lg">
                  <svg className="w-16 h-16 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                  <p className="text-gray-500 font-medium">Not a member of any teams</p>
                  <p className="text-sm text-gray-400 mt-1">Add them to teams using the "Add to Team" tab</p>
                </div>
              )}
            </div>
          )}

          {/* Add to Team Tab */}
          {activeTab === 'add' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Add this staff member to teams. They will immediately see all projects from those teams.
              </p>
              {availableTeams.length > 0 ? (
                <div className="space-y-2">
                  {availableTeams.map((team: Team) => (
                    <div key={team.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-blue-300 transition-colors">
                      <div>
                        <div className="font-medium text-gray-900">{team.name}</div>
                        <div className="text-sm text-gray-500">{team.member_count} members</div>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => handleAddToTeam(team.id)}
                        loading={addToTeamMutation.isPending}
                      >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Add
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50 rounded-lg">
                  <svg className="w-16 h-16 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-gray-500 font-medium">Already in all teams!</p>
                  <p className="text-sm text-gray-400 mt-1">This staff member is part of every team</p>
                </div>
              )}
            </div>
          )}

          {/* Projects Tab */}
          {activeTab === 'projects' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Projects accessible through team memberships. Access is automatically granted based on team assignment.
              </p>
              {loadingProjects ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto"></div>
                </div>
              ) : staffProjects.length > 0 ? (
                <div className="space-y-3">
                  {staffProjects.map((project: Project) => {
                    const team = staffTeams?.find((t: any) => t.id === project.team_id);
                    return (
                      <div key={project.id} className="border border-gray-200 rounded-lg p-4 hover:border-purple-300 transition-colors">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h4 className="font-semibold text-gray-900">{project.name}</h4>
                              <span
                                className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                  project.status === 'active'
                                    ? 'bg-green-100 text-green-800'
                                    : project.status === 'on_hold'
                                    ? 'bg-yellow-100 text-yellow-800'
                                    : 'bg-gray-100 text-gray-800'
                                }`}
                              >
                                {project.status === 'active' && '🟢 Active'}
                                {project.status === 'on_hold' && '⏸️ On Hold'}
                                {project.status === 'completed' && '✅ Completed'}
                              </span>
                            </div>
                            {project.description && (
                              <p className="text-sm text-gray-600 mb-2">{project.description}</p>
                            )}
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <span className="flex items-center">
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                </svg>
                                {team?.name || 'Unknown Team'}
                              </span>
                              <span className="flex items-center">
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                                Created {new Date(project.created_at).toLocaleDateString()}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50 rounded-lg">
                  <svg className="w-16 h-16 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  <p className="text-gray-500 font-medium">No accessible projects</p>
                  <p className="text-sm text-gray-400 mt-1">
                    {staffTeams && staffTeams.length > 0
                      ? 'Teams have no projects yet'
                      : 'Add to teams to grant project access'}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 p-6 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              <span className="font-semibold">{staffTeams?.length || 0}</span> teams • 
              <span className="font-semibold ml-1">{staffProjects.length}</span> projects
            </div>
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Payroll Modal Component
function PayrollModal({ staff, onClose }: { staff: User; onClose: () => void }) {
  const { data: currentRate, isLoading: loadingCurrent } = useQuery({
    queryKey: ['payRate', 'current', staff.id],
    queryFn: () => payRatesApi.getUserCurrentRate(staff.id),
  });

  const { data: payRates, isLoading: loadingHistory } = useQuery({
    queryKey: ['payRates', staff.id],
    queryFn: () => payRatesApi.getUserPayRates(staff.id, true),
  });

  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="max-w-3xl w-full max-h-[80vh] overflow-auto">
        <CardHeader title={`Payroll Information - ${staff.name}`} />
        <div className="p-6 space-y-6">
          {/* Current Pay Rate */}
          <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <svg className="w-5 h-5 mr-2 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Current Pay Rate
            </h3>
            {loadingCurrent ? (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600 mx-auto"></div>
              </div>
            ) : currentRate ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-gray-600">Base Rate</div>
                  <div className="text-2xl font-bold text-emerald-700">
                    {formatCurrency(currentRate.base_rate, currentRate.currency)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {currentRate.rate_type === 'hourly' && 'per hour'}
                    {currentRate.rate_type === 'daily' && 'per day'}
                    {currentRate.rate_type === 'monthly' && 'per month'}
                    {currentRate.rate_type === 'project_based' && 'per project'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Overtime Multiplier</div>
                  <div className="text-2xl font-bold text-gray-900">
                    {currentRate.overtime_multiplier}x
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {formatCurrency(currentRate.base_rate * currentRate.overtime_multiplier, currentRate.currency)} overtime rate
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Effective From</div>
                  <div className="text-lg font-semibold text-gray-900">
                    {formatDate(currentRate.effective_from)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Status</div>
                  <div>
                    <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                      Active
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <svg className="w-16 h-16 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-gray-500 font-medium">No active pay rate</p>
                <p className="text-sm text-gray-400 mt-1">Create a pay rate to get started</p>
              </div>
            )}
          </div>

          {/* Pay Rate History */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <svg className="w-5 h-5 mr-2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Pay Rate History
            </h3>
            {loadingHistory ? (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-600 mx-auto"></div>
              </div>
            ) : payRates && payRates.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rate</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Overtime</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Effective From</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Effective To</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {payRates.map((rate: any) => (
                      <tr key={rate.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">
                          {formatCurrency(rate.base_rate, rate.currency)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600 capitalize">
                          {rate.rate_type.replace('_', ' ')}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                          {rate.overtime_multiplier}x
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                          {formatDate(rate.effective_from)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                          {rate.effective_to ? formatDate(rate.effective_to) : '—'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span
                            className={`px-2 py-1 text-xs font-semibold rounded-full ${
                              rate.is_active
                                ? 'bg-green-100 text-green-800'
                                : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {rate.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 bg-gray-50 rounded-lg">
                <p className="text-gray-500">No pay rate history available</p>
              </div>
            )}
          </div>

          {/* Employment Details */}
          {(staff.job_title || staff.department || staff.employment_type || staff.start_date) && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <svg className="w-5 h-5 mr-2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Employment Details
              </h3>
              <div className="grid grid-cols-2 gap-4 bg-gray-50 rounded-lg p-4">
                {staff.job_title && (
                  <div>
                    <div className="text-xs text-gray-500">Job Title</div>
                    <div className="text-sm font-medium text-gray-900">{staff.job_title}</div>
                  </div>
                )}
                {staff.department && (
                  <div>
                    <div className="text-xs text-gray-500">Department</div>
                    <div className="text-sm font-medium text-gray-900">{staff.department}</div>
                  </div>
                )}
                {staff.employment_type && (
                  <div>
                    <div className="text-xs text-gray-500">Employment Type</div>
                    <div className="text-sm font-medium text-gray-900 capitalize">
                      {staff.employment_type.replace('_', '-')}
                    </div>
                  </div>
                )}
                {staff.start_date && (
                  <div>
                    <div className="text-xs text-gray-500">Start Date</div>
                    <div className="text-sm font-medium text-gray-900">{formatDate(staff.start_date)}</div>
                  </div>
                )}
                {staff.expected_hours_per_week && (
                  <div>
                    <div className="text-xs text-gray-500">Expected Hours/Week</div>
                    <div className="text-sm font-medium text-gray-900">{staff.expected_hours_per_week} hours</div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="flex justify-end pt-4 border-t">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Time Tracking Modal Component
function TimeTrackingModal({ staff, onClose }: { staff: User; onClose: () => void }) {
  const [dateRange, setDateRange] = useState<'week' | 'month' | 'all'>('week');
  
  const getDateRange = () => {
    const end = new Date();
    const start = new Date();
    
    if (dateRange === 'week') {
      start.setDate(end.getDate() - 7);
    } else if (dateRange === 'month') {
      start.setMonth(end.getMonth() - 1);
    } else {
      start.setFullYear(end.getFullYear() - 1);
    }
    
    return {
      start_date: start.toISOString().split('T')[0],
      end_date: end.toISOString().split('T')[0],
    };
  };

  const { data: timeEntries, isLoading } = useQuery({
    queryKey: ['timeEntries', staff.id, dateRange],
    queryFn: () => {
      const dates = getDateRange();
      return timeEntriesApi.getAll(1, 100, {
        user_id: staff.id,
        start_date: dates.start_date,
        end_date: dates.end_date,
      });
    },
  });

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const totalMinutes = timeEntries?.items.reduce((sum: number, entry: any) => {
    return sum + (entry.duration_minutes || 0);
  }, 0) || 0;

  const totalHours = (totalMinutes / 60).toFixed(1);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="max-w-4xl w-full max-h-[80vh] overflow-auto">
        <CardHeader title={`Time Tracking - ${staff.name}`} />
        <div className="p-6 space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-200 rounded-lg p-4">
              <div className="flex items-center">
                <svg className="w-8 h-8 text-indigo-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <div className="text-2xl font-bold text-indigo-700">{totalHours}h</div>
                  <div className="text-xs text-gray-600">Total Hours</div>
                </div>
              </div>
            </div>
            <div className="bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-lg p-4">
              <div className="flex items-center">
                <svg className="w-8 h-8 text-purple-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <div>
                  <div className="text-2xl font-bold text-purple-700">{timeEntries?.total || 0}</div>
                  <div className="text-xs text-gray-600">Entries</div>
                </div>
              </div>
            </div>
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center">
                <svg className="w-8 h-8 text-green-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
                <div>
                  <div className="text-2xl font-bold text-green-700">
                    {staff.expected_hours_per_week || '—'}
                  </div>
                  <div className="text-xs text-gray-600">Expected/Week</div>
                </div>
              </div>
            </div>
          </div>

          {/* Date Range Selector */}
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <svg className="w-5 h-5 mr-2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Recent Time Entries
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => setDateRange('week')}
                className={`px-3 py-1 text-sm rounded-md ${
                  dateRange === 'week'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Last Week
              </button>
              <button
                onClick={() => setDateRange('month')}
                className={`px-3 py-1 text-sm rounded-md ${
                  dateRange === 'month'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Last Month
              </button>
              <button
                onClick={() => setDateRange('all')}
                className={`px-3 py-1 text-sm rounded-md ${
                  dateRange === 'all'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Last Year
              </button>
            </div>
          </div>

          {/* Time Entries Table */}
          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
            </div>
          ) : timeEntries && timeEntries.items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Project</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Task</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {timeEntries.items.map((entry: any) => (
                    <tr key={entry.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {formatDate(entry.start_time)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {entry.project?.name || '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {entry.task?.name || '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-indigo-600">
                        {formatDuration(entry.duration_minutes)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">
                        {entry.description || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <svg className="w-16 h-16 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-gray-500 font-medium">No time entries found</p>
              <p className="text-sm text-gray-400 mt-1">This staff member hasn't logged any time yet</p>
            </div>
          )}

          <div className="flex justify-end pt-4 border-t">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
