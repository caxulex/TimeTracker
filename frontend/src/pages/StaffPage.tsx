// ============================================
// TIME TRACKER - STAFF MANAGEMENT PAGE
// ============================================
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { usersApi, teamsApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import type { User, UserCreate, Team } from '../types';

export function StaffPage() {
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showTeamsModal, setShowTeamsModal] = useState(false);
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
                  Email
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
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{staff.email}</div>
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
                        title="Edit"
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

      {/* Create Staff Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="max-w-md w-full">
            <CardHeader title="Add New Staff Member" />
            <form onSubmit={handleCreateStaff} className="space-y-4 p-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                <select
                  value={createForm.role}
                  onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                >
                  <option value="regular_user">Worker</option>
                  <option value="super_admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <Button type="button" variant="secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" loading={createStaffMutation.isPending}>
                  Create Staff
                </Button>
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
    </div>
  );
}

// Manage Teams Modal Component
function ManageTeamsModal({ staff, onClose }: { staff: User; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [selectedTeams, setSelectedTeams] = useState<number[]>([]);

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(1, 100),
  });

  const addToTeamMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      teamsApi.addMember(teamId, { user_id: userId, role: 'member' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      alert('Staff member added to team successfully!');
    },
  });

  const handleAddToTeam = (teamId: number) => {
    if (confirm(`Add ${staff.name} to this team?`)) {
      addToTeamMutation.mutate({ teamId, userId: staff.id });
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="max-w-2xl w-full max-h-[80vh] overflow-auto">
        <CardHeader title={`Manage Teams for ${staff.name}`} />
        <div className="p-6 space-y-4">
          <p className="text-sm text-gray-600">
            Add this staff member to teams. They will immediately see all projects from those teams.
          </p>
          <div className="space-y-2">
            {teamsData?.items.map((team: Team) => (
              <div key={team.id} className="flex items-center justify-between p-3 border rounded-lg">
                <div>
                  <div className="font-medium">{team.name}</div>
                  <div className="text-sm text-gray-500">{team.member_count} members</div>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleAddToTeam(team.id)}
                  loading={addToTeamMutation.isPending}
                >
                  Add to Team
                </Button>
              </div>
            ))}
          </div>
          <div className="flex justify-end pt-4">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
