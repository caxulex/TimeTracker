// ============================================
// TIME TRACKER - STAFF DETAIL PAGE
// ============================================
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { usersApi, teamsApi, payRatesApi, timeEntriesApi, projectsApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { useStaffNotifications } from '../hooks/useStaffNotifications';
import { usePermissions } from '../hooks/usePermissions';
import { useStaffFormValidation } from '../hooks/useStaffFormValidation';
import type { User, TeamMember, PayRate, TimeEntry, Project } from '../types';

export function StaffDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const notifications = useStaffNotifications();
  const permissions = usePermissions();
  const formValidation = useStaffFormValidation();
  const [activeTab, setActiveTab] = useState<'overview' | 'payroll' | 'time' | 'teams' | 'projects' | 'settings'>('overview');
  const [dateRange, setDateRange] = useState<'week' | 'month' | 'year'>('month');
  const [editMode, setEditMode] = useState(false);
  
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    job_title: '',
    department: '',
    phone: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
  });

  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'super_admin';
  const staffId = parseInt(id || '0', 10);

  // Fetch staff details
  const { data: staff, isLoading: loadingStaff } = useQuery({
    queryKey: ['staff', staffId],
    queryFn: () => usersApi.getById(staffId),
    enabled: !!staffId && isAdmin,
  });

  // Fetch pay rates
  const { data: payRates } = useQuery({
    queryKey: ['payRates', staffId],
    queryFn: () => payRatesApi.getUserPayRates(staffId, true),
    enabled: !!staffId && isAdmin,
  });

  // Fetch current pay rate
  const { data: currentRate } = useQuery({
    queryKey: ['payRate', 'current', staffId],
    queryFn: () => payRatesApi.getUserCurrentRate(staffId),
    enabled: !!staffId && isAdmin,
  });

  // Calculate date range
  const getDateRange = () => {
    const endDate = new Date();
    const startDate = new Date();
    
    if (dateRange === 'week') {
      startDate.setDate(endDate.getDate() - 7);
    } else if (dateRange === 'month') {
      startDate.setDate(endDate.getDate() - 30);
    } else {
      startDate.setDate(endDate.getDate() - 365);
    }
    
    return {
      start: startDate.toISOString().split('T')[0],
      end: endDate.toISOString().split('T')[0],
    };
  };

  const { start, end } = getDateRange();

  // Fetch time entries
  const { data: timeEntries } = useQuery({
    queryKey: ['timeEntries', staffId, start, end],
    queryFn: () => timeEntriesApi.getAll({
      user_id: staffId,
      start_date: start,
      end_date: end,
      page: 1,
      size: 1000,
    }),
    enabled: !!staffId && isAdmin,
  });

  // Fetch all teams
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(1, 100),
    enabled: isAdmin,
  });

  // Fetch staff's current teams
  const { data: staffTeams } = useQuery({
    queryKey: ['staff-teams', staffId],
    queryFn: async () => {
      if (!teamsData?.items) return [];
      const teams = [];
      for (const team of teamsData.items) {
        try {
          const teamDetail = await teamsApi.getById(team.id);
          const member = teamDetail.members?.find((m: TeamMember) => m.user_id === staffId);
          if (member) {
            teams.push({
              ...team,
              memberRole: member.role,
              members: teamDetail.members,
            });
          }
        } catch (error) {
          // User doesn't have access to this team
        }
      }
      return teams;
    },
    enabled: !!teamsData && isAdmin,
  });

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.getAll({ page: 1, size: 100 }),
    enabled: isAdmin,
  });

  // Update staff mutation
  const updateStaffMutation = useMutation({
    mutationFn: async (data: Partial<User>) => {
      // Check permissions
      if (!permissions.canModifyStaff(staff!)) {
        throw new Error('You do not have permission to modify this staff member');
      }

      // Validate and sanitize the data - cast to Partial<User> for API compatibility
      const validationResult = formValidation.secureAndValidate(data, true);
      if (!validationResult.valid) {
        throw new Error('Validation failed');
      }

      return usersApi.update(staffId, validationResult.securedData as Partial<User>);
    },
    onSuccess: (updatedStaff) => {
      queryClient.invalidateQueries({ queryKey: ['staff', staffId] });
      notifications.notifyStaffUpdated(updatedStaff);
      setEditMode(false);
      formValidation.clearErrors();
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = err?.response?.data?.detail || err?.message || 'Unknown error';
      if (errorMessage.includes('permission')) {
        notifications.notifyError('Permission Denied', errorMessage);
      } else if (errorMessage.includes('Validation')) {
        notifications.notifyValidationError('Form', errorMessage);
      } else {
        notifications.notifyStaffUpdateFailed(errorMessage);
      }
    },
  });

  // Toggle active mutation
  const toggleActiveMutation = useMutation({
    mutationFn: async (isActive: boolean) => {
      if (!isActive) {
        await usersApi.delete(staffId);
        return { ...staff!, is_active: false };
      } else {
        const updated = await usersApi.update(staffId, { is_active: true });
        return updated;
      }
    },
    onSuccess: (updatedStaff) => {
      queryClient.invalidateQueries({ queryKey: ['staff', staffId] });
      if (updatedStaff.is_active) {
        notifications.notifyStaffActivated(updatedStaff);
      } else {
        notifications.notifyStaffDeactivated(updatedStaff);
      }
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } }; message?: string };
      notifications.notifyError('Status Change Failed', err?.response?.data?.detail || err?.message || 'Failed to change status');
    },
  });

  // Calculate analytics
  const analytics = {
    totalHours: timeEntries?.items.reduce((sum: number, entry: TimeEntry) => sum + (entry.duration_seconds / 3600), 0) || 0,
    totalEntries: timeEntries?.items.length || 0,
    expectedHours: (staff?.expected_hours_per_week || 40) * (dateRange === 'week' ? 1 : dateRange === 'month' ? 4 : 52),
    projectCount: new Set(timeEntries?.items.map((e: TimeEntry) => e.project_id).filter(Boolean)).size,
    daysWorked: new Set(timeEntries?.items.map((e: TimeEntry) => e.start_time?.split('T')[0]).filter(Boolean)).size,
  };

  const productivityScore = analytics.expectedHours > 0 
    ? Math.min(100, Math.round((analytics.totalHours / analytics.expectedHours) * 100))
    : 0;

  // Filter projects
  const staffProjects = projectsData?.items.filter((project: Project) =>
    staffTeams?.some((team: any) => team.id === project.team_id)
  ) || [];

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

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const handleUpdateStaff = (e: React.FormEvent) => {
    e.preventDefault();
    updateStaffMutation.mutate(editForm);
  };

  const handleToggleActive = () => {
    if (!staff) return;
    
    // Use permission hook for deactivation check
    if (!permissions.canDeactivateStaff(staff)) {
      notifications.notifyWarning("Can't Deactivate Yourself", "You cannot deactivate your own account.");
      return;
    }
    
    const action = staff.is_active ? 'deactivate' : 'activate';
    if (confirm(`Are you sure you want to ${action} ${staff.name}?`)) {
      toggleActiveMutation.mutate(staff.is_active);
    }
  };

  const startEdit = () => {
    if (staff) {
      setEditForm({
        name: staff.name,
        email: staff.email,
        job_title: staff.job_title || '',
        department: staff.department || '',
        phone: staff.phone || '',
        address: staff.address || '',
        emergency_contact_name: staff.emergency_contact_name || '',
        emergency_contact_phone: staff.emergency_contact_phone || '',
      });
      setEditMode(true);
    }
  };

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

  if (loadingStaff) {
    return <LoadingOverlay message="Loading staff details..." />;
  }

  if (!staff) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card>
          <div className="text-center p-8">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Staff Not Found</h2>
            <p className="text-gray-500 mb-4">The requested staff member could not be found.</p>
            <Button onClick={() => navigate('/staff')}>Back to Staff List</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4 md:space-y-6 p-2 md:p-4 lg:p-6">
      {/* Header with Back Button */}
      <div className="flex items-center gap-2 md:gap-4">
        <button
          onClick={() => navigate('/staff')}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="Back to Staff List"
        >
          <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl md:text-2xl font-bold text-gray-900 truncate">Staff Details</h1>
          <p className="text-sm md:text-base text-gray-500 truncate">View and manage {staff.name}'s information</p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {!editMode && (
            <Button onClick={startEdit} className="hidden md:flex">
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit Info
            </Button>
          )}
          {!editMode && (
            <Button onClick={startEdit} size="sm" className="md:hidden">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleToggleActive}
            disabled={staff.id === currentUser?.id}
            className="hidden md:flex"
          >
            {staff.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        </div>
      </div>

      {/* Staff Profile Card */}
      <Card>
        <div className="p-4 md:p-6">
          <div className="flex flex-col sm:flex-row items-start gap-4 md:gap-6">
            <div className="h-20 w-20 md:h-24 md:w-24 flex-shrink-0 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center text-white text-3xl md:text-4xl font-bold shadow-lg mx-auto sm:mx-0">
              {staff.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 w-full text-center sm:text-left">
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 md:gap-3 mb-2">
                <h2 className="text-xl md:text-2xl font-bold text-gray-900">{staff.name}</h2>
                <span
                  className={`px-3 py-1 text-xs md:text-sm font-semibold rounded-full inline-block ${
                    staff.is_active
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {staff.is_active ? 'Active' : 'Inactive'}
                </span>
                <span
                  className={`px-3 py-1 text-sm font-semibold rounded-full ${
                    staff.role === 'super_admin'
                      ? 'bg-purple-100 text-purple-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {staff.role === 'super_admin' ? 'Admin' : 'Worker'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <div className="text-sm text-gray-600">Email</div>
                  <div className="font-semibold text-gray-900">{staff.email}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Job Title</div>
                  <div className="font-semibold text-gray-900">{staff.job_title || '—'}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Department</div>
                  <div className="font-semibold text-gray-900">{staff.department || '—'}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Employment Type</div>
                  <div>
                    {staff.employment_type ? (
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                        staff.employment_type === 'full_time'
                          ? 'bg-blue-100 text-blue-800'
                          : staff.employment_type === 'part_time'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-purple-100 text-purple-800'
                      }`}>
                        {staff.employment_type === 'full_time' ? 'Full-time' : 
                         staff.employment_type === 'part_time' ? 'Part-time' : 'Contractor'}
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-600">Member Since</div>
              <div className="font-semibold text-gray-900">{formatDate(staff.created_at)}</div>
            </div>
          </div>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">{analytics.totalHours.toFixed(1)}h</div>
            <div className="text-sm text-gray-600 mt-1">Hours This {dateRange === 'week' ? 'Week' : dateRange === 'month' ? 'Month' : 'Year'}</div>
          </div>
        </Card>
        <Card>
          <div className="p-4 text-center">
            <div className="text-3xl font-bold text-green-600">{productivityScore}%</div>
            <div className="text-sm text-gray-600 mt-1">Productivity Score</div>
          </div>
        </Card>
        <Card>
          <div className="p-4 text-center">
            <div className="text-3xl font-bold text-purple-600">{staffTeams?.length || 0}</div>
            <div className="text-sm text-gray-600 mt-1">Teams</div>
          </div>
        </Card>
        <Card>
          <div className="p-4 text-center">
            <div className="text-3xl font-bold text-amber-600">{staffProjects.length}</div>
            <div className="text-sm text-gray-600 mt-1">Projects</div>
          </div>
        </Card>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-gray-200 overflow-x-auto">
        <div className="flex space-x-4 md:space-x-8 min-w-max px-2 md:px-0">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3 md:py-4 px-2 md:px-1 border-b-2 font-medium text-xs md:text-sm transition-colors whitespace-nowrap ${
              activeTab === 'overview'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="hidden sm:inline">📋 Overview</span>
            <span className="sm:hidden">📋</span>
          </button>
          <button
            onClick={() => setActiveTab('payroll')}
            className={`py-3 md:py-4 px-2 md:px-1 border-b-2 font-medium text-xs md:text-sm transition-colors whitespace-nowrap ${
              activeTab === 'payroll'
                ? 'border-emerald-500 text-emerald-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="hidden sm:inline">💰 Payroll</span>
            <span className="sm:hidden">💰</span>
          </button>
          <button
            onClick={() => setActiveTab('time')}
            className={`py-3 md:py-4 px-2 md:px-1 border-b-2 font-medium text-xs md:text-sm transition-colors whitespace-nowrap ${
              activeTab === 'time'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="hidden sm:inline">⏱️ Time Tracking</span>
            <span className="sm:hidden">⏱️</span>
          </button>
          <button
            onClick={() => setActiveTab('teams')}
            className={`py-3 md:py-4 px-2 md:px-1 border-b-2 font-medium text-xs md:text-sm transition-colors whitespace-nowrap ${
              activeTab === 'teams'
                ? 'border-green-500 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            👥 Teams
          </button>
          <button
            onClick={() => setActiveTab('projects')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'projects'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            📁 Projects
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'settings'
                ? 'border-gray-500 text-gray-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            ⚙️ Settings
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <>
            <Card>
              <CardHeader title="Contact Information" />
              <div className="p-6">
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-1">Phone</div>
                    <div className="text-gray-900">{staff.phone || '—'}</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-1">Address</div>
                    <div className="text-gray-900">{staff.address || '—'}</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-1">Emergency Contact</div>
                    <div className="text-gray-900">{staff.emergency_contact_name || '—'}</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-1">Emergency Phone</div>
                    <div className="text-gray-900">{staff.emergency_contact_phone || '—'}</div>
                  </div>
                </div>
              </div>
            </Card>

            <Card>
              <CardHeader title="Employment Details" />
              <div className="p-6">
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-1">Start Date</div>
                    <div className="text-gray-900">
                      {staff.start_date ? formatDate(staff.start_date) : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-1">Expected Hours/Week</div>
                    <div className="text-gray-900">{staff.expected_hours_per_week || 40} hours</div>
                  </div>
                  <div className="col-span-2">
                    <div className="text-sm font-medium text-gray-700 mb-1">Manager</div>
                    <div className="text-gray-900">{staff.manager_id ? `Manager ID: ${staff.manager_id}` : 'No manager assigned'}</div>
                  </div>
                </div>
              </div>
            </Card>
          </>
        )}

        {/* Payroll Tab */}
        {activeTab === 'payroll' && (
          <Card>
            <CardHeader title="Payroll Information" />
            <div className="p-6 space-y-6">
              {/* Current Rate */}
              {currentRate ? (
                <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Pay Rate</h3>
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
                      <div className="text-2xl font-bold text-gray-900">{currentRate.overtime_multiplier}x</div>
                      <div className="text-xs text-gray-500 mt-1">
                        {formatCurrency(currentRate.base_rate * currentRate.overtime_multiplier, currentRate.currency)} overtime
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50 rounded-lg">
                  <p className="text-gray-500">No active pay rate set</p>
                </div>
              )}

              {/* Pay Rate History */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Pay Rate History</h3>
                {payRates && payRates.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rate</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Effective From</th>
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
                              {formatDate(rate.effective_from)}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                !rate.effective_to ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                              }`}>
                                {!rate.effective_to ? 'Active' : 'Inactive'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>No pay rate history available</p>
                  </div>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Time Tracking Tab */}
        {activeTab === 'time' && (
          <Card>
            <CardHeader title="Time Tracking" />
            <div className="p-6 space-y-6">
              {/* Date Range Selector */}
              <div className="flex gap-2">
                <button
                  onClick={() => setDateRange('week')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    dateRange === 'week'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-300'
                  }`}
                >
                  Last Week
                </button>
                <button
                  onClick={() => setDateRange('month')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    dateRange === 'month'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-300'
                  }`}
                >
                  Last Month
                </button>
                <button
                  onClick={() => setDateRange('year')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    dateRange === 'year'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-300'
                  }`}
                >
                  Last Year
                </button>
              </div>

              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-lg p-4">
                  <div className="text-sm font-medium text-blue-900">Total Hours</div>
                  <div className="text-2xl font-bold text-blue-900 mt-1">{analytics.totalHours.toFixed(1)}</div>
                  <div className="text-xs text-blue-700 mt-1">{analytics.totalEntries} entries</div>
                </div>
                <div className="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-lg p-4">
                  <div className="text-sm font-medium text-green-900">Days Worked</div>
                  <div className="text-2xl font-bold text-green-900 mt-1">{analytics.daysWorked}</div>
                  <div className="text-xs text-green-700 mt-1">in selected period</div>
                </div>
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-lg p-4">
                  <div className="text-sm font-medium text-purple-900">Projects</div>
                  <div className="text-2xl font-bold text-purple-900 mt-1">{analytics.projectCount}</div>
                  <div className="text-xs text-purple-700 mt-1">unique projects</div>
                </div>
              </div>

              {/* Time Entries Table */}
              {timeEntries && timeEntries.items.length > 0 ? (
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
                      {timeEntries.items.slice(0, 20).map((entry: TimeEntry) => (
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
                            {formatDuration(entry.duration_seconds)}
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
                  <p className="text-gray-500">No time entries found</p>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Teams Tab */}
        {activeTab === 'teams' && (
          <Card>
            <CardHeader title="Team Memberships" />
            <div className="p-6">
              {staffTeams && staffTeams.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {staffTeams.map((team: any) => (
                    <div key={team.id} className="border border-gray-200 rounded-lg p-4 hover:border-green-300 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-gray-900">{team.name}</h4>
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                          team.memberRole === 'admin'
                            ? 'bg-purple-100 text-purple-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {team.memberRole === 'admin' ? '👑 Admin' : '👤 Member'}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600">
                        {team.members?.length || 0} members • Created {formatDate(team.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50 rounded-lg">
                  <p className="text-gray-500">Not a member of any teams</p>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Projects Tab */}
        {activeTab === 'projects' && (
          <Card>
            <CardHeader title="Accessible Projects" />
            <div className="p-6">
              {staffProjects.length > 0 ? (
                <div className="space-y-3">
                  {staffProjects.map((project: Project) => {
                    const team = staffTeams?.find((t: any) => t.id === project.team_id);
                    return (
                      <div key={project.id} className="border border-gray-200 rounded-lg p-4 hover:border-purple-300 transition-colors">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h4 className="font-semibold text-gray-900">{project.name}</h4>
                              <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                project.is_archived
                                  ? 'bg-gray-100 text-gray-800'
                                  : 'bg-green-100 text-green-800'
                              }`}>
                                {project.is_archived ? '📦 Archived' : '🟢 Active'}
                              </span>
                            </div>
                            {project.description && (
                              <p className="text-sm text-gray-600 mb-2">{project.description}</p>
                            )}
                            <div className="text-xs text-gray-500">
                              Team: {team?.name || 'Unknown'} • Created {formatDate(project.created_at)}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50 rounded-lg">
                  <p className="text-gray-500">No accessible projects</p>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <Card>
            <CardHeader title="Staff Settings" />
            <div className="p-6">
              {editMode ? (
                <form onSubmit={handleUpdateStaff} className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                      <input
                        type="text"
                        required
                        value={editForm.name}
                        onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('name') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('name') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('name')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                      <input
                        type="email"
                        required
                        value={editForm.email}
                        onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('email') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('email') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('email')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Job Title</label>
                      <input
                        type="text"
                        value={editForm.job_title}
                        onChange={(e) => setEditForm({ ...editForm, job_title: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('job_title') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('job_title') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('job_title')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                      <input
                        type="text"
                        value={editForm.department}
                        onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('department') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('department') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('department')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                      <input
                        type="tel"
                        value={editForm.phone}
                        onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('phone') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('phone') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('phone')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                      <input
                        type="text"
                        value={editForm.address}
                        onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('address') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('address') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('address')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Emergency Contact Name</label>
                      <input
                        type="text"
                        value={editForm.emergency_contact_name}
                        onChange={(e) => setEditForm({ ...editForm, emergency_contact_name: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('emergency_contact_name') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('emergency_contact_name') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('emergency_contact_name')}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Emergency Contact Phone</label>
                      <input
                        type="tel"
                        value={editForm.emergency_contact_phone}
                        onChange={(e) => setEditForm({ ...editForm, emergency_contact_phone: e.target.value })}
                        className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 ${
                          formValidation.hasFieldError('emergency_contact_phone') 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-gray-300'
                        }`}
                      />
                      {formValidation.hasFieldError('emergency_contact_phone') && (
                        <p className="text-xs text-red-600 mt-1">{formValidation.getFieldError('emergency_contact_phone')}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end pt-4">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setEditMode(false);
                        formValidation.clearErrors();
                      }}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" isLoading={updateStaffMutation.isPending}>
                      Save Changes
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="text-center py-12">
                  <p className="text-gray-600 mb-4">Edit mode is disabled. Click "Edit Info" button in the header to make changes.</p>
                  <Button onClick={startEdit}>Start Editing</Button>
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
