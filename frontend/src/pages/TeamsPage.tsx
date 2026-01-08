// ============================================
// TIME TRACKER - TEAMS PAGE
// ============================================
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, Button, Input, Modal, LoadingOverlay } from '../components/common';
import { teamsApi, usersApi } from '../api/client';
import { formatDate, getInitials, isAdminUser, cn } from '../utils/helpers';
import { useAuthStore } from '../stores/authStore';
import { useAuth } from '../hooks/useAuth';
import { useStaffNotifications } from '../hooks/useStaffNotifications';
import type { Team, TeamMember, User } from '../types';

export function TeamsPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const notifications = useStaffNotifications();
  
  const [showModal, setShowModal] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<number | null>(null);
  const [showMemberModal, setShowMemberModal] = useState(false);

  // Fetch teams
  const { data: teamsData, isLoading, error: teamsError } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(),
  });

  // Fetch selected team details
  const { data: teamDetails, error: teamDetailsError, isLoading: isLoadingDetails } = useQuery({
    queryKey: ['team', selectedTeam],
    queryFn: () => teamsApi.getById(selectedTeam!),
    enabled: !!selectedTeam,
  });

  // Fetch users for member add (admin only)
  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.getAll(),
    enabled: isAdmin,
  });

  const teams = teamsData?.items || [];
  const users = usersData?.items || [];

  // Create team mutation (admin only)
  const createMutation = useMutation({
    mutationFn: (name: string) => teamsApi.create({ name }),
    onSuccess: (team) => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      setShowModal(false);
      notifications.notifySuccess('Team Created', `Team "${team.name}" has been created successfully.`);
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to create team';
      notifications.notifyError('Create Failed', errorMessage);
    },
  });

  // Update team mutation (admin only)
  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      teamsApi.update(id, { name }),
    onSuccess: (team) => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeam] });
      setShowModal(false);
      setEditingTeam(null);
      notifications.notifySuccess('Team Updated', `Team "${team.name}" has been updated successfully.`);
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to update team';
      if (error?.response?.status === 403) {
        notifications.notifyError('Permission Denied', 'Only team owners and super admins can update teams.');
      } else {
        notifications.notifyError('Update Failed', errorMessage);
      }
    },
  });

  // Delete team mutation (admin only)
  const deleteMutation = useMutation({
    mutationFn: (id: number) => teamsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      setSelectedTeam(null);
      notifications.notifySuccess('Team Deleted', 'Team has been successfully deleted.');
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to delete team';
      if (error?.response?.status === 403) {
        notifications.notifyError('Permission Denied', 'Only team owners and super admins can delete teams.');
      } else {
        notifications.notifyError('Delete Failed', errorMessage);
      }
    },
  });

  // Add member mutation (admin only)
  const addMemberMutation = useMutation({
    mutationFn: ({ teamId, userId, role }: { teamId: number; userId: number; role: string }) =>
      teamsApi.addMember(teamId, userId, role),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeam] });
      setShowMemberModal(false);
      const user = users.find(u => u.id === variables.userId);
      notifications.notifySuccess('Member Added', `${user?.name || 'User'} has been added to the team.`);
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to add member';
      if (error?.response?.status === 403) {
        notifications.notifyError('Permission Denied', 'Only team owners and admins can add members.');
      } else if (error?.response?.status === 400) {
        notifications.notifyError('Invalid Request', errorMessage);
      } else {
        notifications.notifyError('Add Member Failed', errorMessage);
      }
    },
  });

  // Remove member mutation (admin only)
  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      teamsApi.removeMember(teamId, userId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeam] });
      const teamMember = teamDetails?.members?.find((m: TeamMember) => m.user_id === variables.userId);
      notifications.notifySuccess('Member Removed', `${teamMember?.user?.name || 'User'} has been removed from the team.`);
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to remove member';
      if (error?.response?.status === 403) {
        notifications.notifyError('Permission Denied', 'Only team owners and admins can remove members.');
      } else {
        notifications.notifyError('Remove Member Failed', errorMessage);
      }
    },
  });

  const handleEdit = (team: Team) => {
    if (!isAdmin) return;
    setEditingTeam(team);
    setShowModal(true);
  };

  if (isLoading) {
    return <LoadingOverlay message="Loading teams..." />;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="text-gray-500">
            {isAdmin ? 'Manage your teams and members' : 'View your teams'}
          </p>
        </div>
        {isAdmin && (
          <Button onClick={() => setShowModal(true)}>
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Team
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Teams list */}
        <div className="lg:col-span-1 space-y-3">
          {teams.length === 0 ? (
            <Card className="text-center py-8">
              <svg className="mx-auto w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              <h3 className="mt-4 text-lg font-medium text-gray-900">No teams yet</h3>
              <p className="mt-2 text-gray-500">
                {isAdmin ? 'Create your first team to get started.' : 'No teams available. Contact your admin.'}
              </p>
            </Card>
          ) : (
            teams.map((team: Team) => (
              <Card
                key={team.id}
                padding="sm"
                className={cn(
                  'cursor-pointer transition-all',
                  selectedTeam === team.id
                    ? 'ring-2 ring-blue-500 bg-blue-50'
                    : 'hover:shadow-md'
                )}
                onClick={() => setSelectedTeam(team.id)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{team.name}</h3>
                    <p className="text-sm text-gray-500">
                      {team.member_count || 1} member{(team.member_count || 1) !== 1 ? 's' : ''}
                    </p>
                  </div>
                  {team.owner_id === currentUser?.id && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                      Owner
                    </span>
                  )}
                </div>
              </Card>
            ))
          )}
        </div>

        {/* Team details */}
        <div className="lg:col-span-2">
          {selectedTeam && isLoadingDetails ? (
            <Card>
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="mt-4 text-gray-500">Loading team details...</p>
                </div>
              </div>
            </Card>
          ) : selectedTeam && teamDetailsError ? (
            <Card>
              <div className="text-center py-12">
                <svg className="mx-auto w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="mt-4 text-lg font-medium text-gray-900">Error loading team</h3>
                <p className="mt-2 text-red-600">
                  {teamDetailsError instanceof Error ? teamDetailsError.message : 'Failed to load team details'}
                </p>
                <Button
                  variant="secondary"
                  className="mt-4"
                  onClick={() => setSelectedTeam(null)}
                >
                  Back to teams
                </Button>
              </div>
            </Card>
          ) : selectedTeam && teamDetails ? (
            <Card>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{teamDetails.name}</h2>
                  <p className="text-sm text-gray-500">
                    Created {formatDate(teamDetails.created_at)}
                  </p>
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => handleEdit(teamDetails)}>
                      Edit
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        if (confirm('Are you sure you want to delete this team?')) {
                          deleteMutation.mutate(teamDetails.id);
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                )}
              </div>

              {/* Members section */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-gray-900">Members</h3>
                  {isAdmin && (
                    <Button size="sm" onClick={() => setShowMemberModal(true)}>
                      Add Member
                    </Button>
                  )}
                </div>

                <div className="space-y-2">
                  {teamDetails.members?.map((member: TeamMember) => (
                    <div
                      key={member.user_id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-medium">
                          {getInitials(member.user?.name || 'U')}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">
                            {member.user?.name || 'Unknown User'}
                          </p>
                          <p className="text-sm text-gray-500">{member.user?.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'px-2 py-0.5 text-xs rounded-full',
                            member.role === 'admin'
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-gray-100 text-gray-800'
                          )}
                        >
                          {member.role}
                        </span>
                        {isAdmin && member.user_id !== teamDetails.owner_id && (
                          <button
                            onClick={() =>
                              removeMemberMutation.mutate({
                                teamId: teamDetails.id,
                                userId: member.user_id,
                              })
                            }
                            className="p-1 text-gray-400 hover:text-red-600"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          ) : (
            <Card className="text-center py-12">
              <svg className="mx-auto w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              <h3 className="mt-4 text-lg font-medium text-gray-900">Select a team</h3>
              <p className="mt-2 text-gray-500">Choose a team from the list to view details.</p>
            </Card>
          )}
        </div>
      </div>

      {/* Create/Edit Team Modal - Admin only */}
      {isAdmin && (
        <TeamModal
          isOpen={showModal}
          onClose={() => {
            setShowModal(false);
            setEditingTeam(null);
          }}
          team={editingTeam}
          onSubmit={(name) => {
            if (editingTeam) {
              updateMutation.mutate({ id: editingTeam.id, name });
            } else {
              createMutation.mutate(name);
            }
          }}
          isLoading={createMutation.isPending || updateMutation.isPending}
        />
      )}

      {/* Add Member Modal - Admin only */}
      {isAdmin && (
        <AddMemberModal
          isOpen={showMemberModal}
          onClose={() => setShowMemberModal(false)}
          users={users.filter(
            (u: User) => !teamDetails?.members?.some((m: TeamMember) => m.user_id === u.id)
          )}
          onSubmit={(userId, role) => {
            if (selectedTeam) {
              addMemberMutation.mutate({ teamId: selectedTeam, userId, role });
            }
          }}
          isLoading={addMemberMutation.isPending}
        />
      )}
    </div>
  );
}

// Team Modal Component
interface TeamModalProps {
  isOpen: boolean;
  onClose: () => void;
  team: Team | null;
  onSubmit: (name: string) => void;
  isLoading: boolean;
}

function TeamModal({ isOpen, onClose, team, onSubmit, isLoading }: TeamModalProps) {
  const [name, setName] = useState('');

  React.useEffect(() => {
    setName(team?.name || '');
  }, [team, isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(name);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={team ? 'Edit Team' : 'New Team'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Team Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Team"
          required
        />

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading}>
            {team ? 'Save Changes' : 'Create Team'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// Add Member Modal Component
interface AddMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  users: User[];
  onSubmit: (userId: number, role: string) => void;
  isLoading: boolean;
}

function AddMemberModal({ isOpen, onClose, users, onSubmit, isLoading }: AddMemberModalProps) {
  const [selectedUser, setSelectedUser] = useState<number | ''>('');
  const [role, setRole] = useState('member');

  React.useEffect(() => {
    setSelectedUser('');
    setRole('member');
  }, [isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedUser) {
      onSubmit(selectedUser as number, role);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Team Member">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select User
          </label>
          <select
            value={selectedUser}
            onChange={(e) => setSelectedUser(Number(e.target.value))}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          >
            <option value="">Choose a user...</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.name} ({user.email})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Role
          </label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading} disabled={!selectedUser}>
            Add Member
          </Button>
        </div>
      </form>
    </Modal>
  );
}
