// ============================================
// TIME TRACKER - USERS PAGE (ADMIN)
// TASK-023: Admin user management page
// ============================================
import React, { useState } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, Button, Input, Modal, LoadingOverlay, Select } from '../components/common';
import { usersApi } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { formatDate, cn } from '../utils/helpers';
import type { User } from '../types';

const ROLE_OPTIONS = [
  { value: 'regular_user', label: 'Regular User' },
  { value: 'super_admin', label: 'Administrator' },
];

const ROLE_COLORS: Record<string, string> = {
  super_admin: 'bg-purple-100 text-purple-800',
  regular_user: 'bg-gray-100 text-gray-800',
};

export function UsersPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDeactivated, setShowDeactivated] = useState(false);

  // Fetch users — paginated via Load More.
  //
  // Same pagination-shadow shape as ProjectsPage (PR #35) and
  // TasksPage (PR #39): the server defaults to page_size=20 and
  // silently caps the list. We use useInfiniteQuery with
  // page_size=50 plus a "Showing X of Y" indicator and a
  // "Load More" button so admins can reach every user even on
  // tenants with hundreds of accounts. The search and
  // "show deactivated" filters are pure client-side filters over
  // the loaded pages — they don't go in the query key — so the
  // user can flip them without re-fetching what was already paged
  // in. (If a tenant ever grows past a few hundred users the
  // right fix is server-side search; out of scope here.)
  const USERS_PAGE_SIZE = 50;
  const {
    data: usersData,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['users', 'paginated'],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      usersApi.getAll(pageParam as number, USERS_PAGE_SIZE),
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce(
        (acc, p) => acc + (p.items?.length || 0),
        0
      );
      const total = lastPage?.total ?? 0;
      if (loaded >= total) return undefined;
      return allPages.length + 1;
    },
  });

  const users: User[] = (usersData?.pages ?? []).flatMap(
    (p) => p.items || []
  );
  const totalUsers = usersData?.pages?.[0]?.total ?? users.length;

  // Filter users
  const filteredUsers = users.filter((user: User) => {
    const matchesSearch = user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesActive = showDeactivated || user.is_active;
    return matchesSearch && matchesActive;
  });

  // Update role mutation
  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) =>
      usersApi.updateRole(id, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  // Update user mutation
  const updateUserMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<User> }) =>
      usersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowModal(false);
      setEditingUser(null);
    },
  });

  // Toggle active status
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) =>
      usersApi.update(id, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setShowModal(true);
  };

  const handleToggleActive = (user: User) => {
    if (user.id === currentUser?.id) {
      alert("You cannot deactivate your own account");
      return;
    }
    toggleActiveMutation.mutate({ id: user.id, isActive: !user.is_active });
  };

  if (isLoading) {
    return <LoadingOverlay message="Loading users..." />;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="text-gray-500">Manage user accounts and permissions</p>
        </div>
      </div>

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <Input
              placeholder="Search users..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={showDeactivated}
              onChange={(e) => setShowDeactivated(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Show deactivated users
          </label>
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900">{users.length}</p>
            <p className="text-sm text-gray-500">Total Users</p>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <p className="text-2xl font-bold text-green-600">
              {users.filter((u: User) => u.is_active).length}
            </p>
            <p className="text-sm text-gray-500">Active Users</p>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <p className="text-2xl font-bold text-purple-600">
              {users.filter((u: User) => u.role === 'super_admin').length}
            </p>
            <p className="text-sm text-gray-500">Administrators</p>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <p className="text-2xl font-bold text-red-600">
              {users.filter((u: User) => !u.is_active).length}
            </p>
            <p className="text-sm text-gray-500">Deactivated</p>
          </div>
        </Card>
      </div>

      {/* "Showing X of Y users" indicator. Counts the
          currently-visible (client-filtered) users against the
          server-reported total so admins can see when more pages
          remain to be loaded. */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500" data-testid="users-count">
          Showing {filteredUsers.length} of {totalUsers} users
        </p>
      </div>

      {/* Users table */}
      <Card>
        <CardHeader title="All Users" subtitle={`${filteredUsers.length} users found`} />
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Joined
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredUsers.map((user: User) => (
                <tr key={user.id} className={cn(!user.is_active && 'bg-gray-50 opacity-60')}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                        <span className="text-blue-600 font-medium">
                          {user.name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">
                          {user.name}
                          {user.id === currentUser?.id && (
                            <span className="ml-2 text-xs text-blue-600">(You)</span>
                          )}
                        </div>
                        <div className="text-sm text-gray-500">{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <select
                      value={user.role}
                      onChange={(e) => updateRoleMutation.mutate({ id: user.id, role: e.target.value })}
                      disabled={user.id === currentUser?.id}
                      className={cn(
                        'text-xs px-2 py-1 rounded-full border-0 cursor-pointer focus:ring-2 focus:ring-blue-500',
                        ROLE_COLORS[user.role] || ROLE_COLORS.regular_user,
                        user.id === currentUser?.id && 'cursor-not-allowed'
                      )}
                    >
                      {ROLE_OPTIONS.map((role) => (
                        <option key={role.value} value={role.value}>
                          {role.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={cn(
                      'px-2 py-1 text-xs rounded-full',
                      user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    )}>
                      {user.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleEdit(user)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Edit
                      </button>
                      {user.id !== currentUser?.id && (
                        <button
                          onClick={() => handleToggleActive(user)}
                          className={cn(
                            user.is_active ? 'text-red-600 hover:text-red-900' : 'text-green-600 hover:text-green-900'
                          )}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Load More — server-side pagination via useInfiniteQuery.
          Hidden once everything is loaded; disabled while the
          next page is in flight. */}
      {hasNextPage && (
        <div className="flex justify-center pt-2">
          <Button
            variant="secondary"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            data-testid="users-load-more"
          >
            {isFetchingNextPage ? 'Loading…' : 'Load More'}
          </Button>
        </div>
      )}

      {/* Edit User Modal */}
      <UserEditModal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setEditingUser(null);
        }}
        user={editingUser}
        onSubmit={(data) => {
          if (editingUser) {
            updateUserMutation.mutate({ id: editingUser.id, data });
          }
        }}
        isLoading={updateUserMutation.isPending}
      />
    </div>
  );
}

// User Edit Modal Component
interface UserEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onSubmit: (data: Partial<User>) => void;
  isLoading: boolean;
}

function UserEditModal({ isOpen, onClose, user, onSubmit, isLoading }: UserEditModalProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');

  React.useEffect(() => {
    if (user) {
      setName(user.name);
      setEmail(user.email);
    }
  }, [user]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ name, email });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit User">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />

        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading}>
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  );
}
