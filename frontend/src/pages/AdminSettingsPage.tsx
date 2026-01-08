// ============================================
// TIME TRACKER - ADMIN SETTINGS PAGE
// API Key Management (Super Admin Only)
// SEC-020: Secure API Key Storage
// ============================================
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button, Input } from '../components/common';
import { AdminAISettings } from '../components/ai';
import { apiKeysApi } from '../api/apiKeys';
import { usersApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { useNotifications } from '../hooks/useNotifications';
import { isAdminUser } from '../utils/helpers';
import type { APIKey, APIKeyCreate, AIProvider } from '../types/apiKey';

// Provider options with display info
const PROVIDERS: { id: AIProvider; name: string; icon: string; hint: string }[] = [
  { id: 'gemini', name: 'Google Gemini', icon: '✨', hint: 'AIza...' },
  { id: 'openai', name: 'OpenAI', icon: '🤖', hint: 'sk-...' },
  { id: 'anthropic', name: 'Anthropic', icon: '🧠', hint: 'sk-ant-...' },
  { id: 'azure_openai', name: 'Azure OpenAI', icon: '☁️', hint: 'Varies by endpoint' },
  { id: 'other', name: 'Other', icon: '🔑', hint: 'Any format' },
];

export function AdminSettingsPage() {
  const { user } = useAuthStore();
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  
  // Active tab state - default to api-keys for all admins
  const [activeTab, setActiveTab] = useState<'api-keys' | 'ai-features'>('api-keys');
  
  // Form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newKey, setNewKey] = useState<APIKeyCreate>({
    provider: 'gemini',
    api_key: '',
    label: '',
    notes: '',
  });
  const [testingId, setTestingId] = useState<number | null>(null);

  // All admins now have full access (admin = super_admin)
  const isAdmin = isAdminUser(user);

  // Fetch users for AI settings (admin only)
  const { data: usersData } = useQuery({
    queryKey: ['users-list'],
    queryFn: async () => {
      const response = await usersApi.getAll(1, 500);
      return response.items.filter(u => u.is_active);
    },
    enabled: isAdmin,
  });

  // Fetch encryption status
  const { data: encryptionStatus } = useQuery({
    queryKey: ['encryption-status'],
    queryFn: () => apiKeysApi.getEncryptionStatus(),
    enabled: isAdmin,
  });

  // Fetch API keys
  const { data: keysData, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => apiKeysApi.getAll(),
    enabled: isAdmin,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: APIKeyCreate) => apiKeysApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setShowAddForm(false);
      setNewKey({ provider: 'gemini', api_key: '', label: '', notes: '' });
      addNotification({
        type: 'success',
        title: 'API Key Added',
        message: 'The API key has been securely stored',
      });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      addNotification({
        type: 'error',
        title: 'Failed to Add Key',
        message: axiosError.response?.data?.detail || 'An error occurred',
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiKeysApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      addNotification({
        type: 'success',
        title: 'API Key Deleted',
        message: 'The API key has been removed',
      });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      addNotification({
        type: 'error',
        title: 'Failed to Delete',
        message: axiosError.response?.data?.detail || 'An error occurred',
      });
    },
  });

  // Toggle active mutation
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) =>
      apiKeysApi.update(id, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
    },
  });

  // Test mutation
  const testMutation = useMutation({
    mutationFn: (id: number) => apiKeysApi.test(id),
    onSuccess: (result) => {
      if (result.success) {
        addNotification({
          type: 'success',
          title: 'Connection Successful',
          message: `${result.provider}: ${result.message}${result.latency_ms ? ` (${result.latency_ms}ms)` : ''}`,
        });
      } else {
        addNotification({
          type: 'error',
          title: 'Connection Failed',
          message: result.message,
        });
      }
      setTestingId(null);
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      addNotification({
        type: 'error',
        title: 'Test Failed',
        message: axiosError.response?.data?.detail || 'An error occurred',
      });
      setTestingId(null);
    },
  });

  const handleTest = (id: number) => {
    setTestingId(id);
    testMutation.mutate(id);
  };

  const handleDelete = (key: APIKey) => {
    if (confirm(`Delete ${getProviderName(key.provider)} key "${key.key_preview}"?`)) {
      deleteMutation.mutate(key.id);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.api_key.trim()) {
      addNotification({
        type: 'error',
        title: 'Validation Error',
        message: 'API key is required',
      });
      return;
    }
    createMutation.mutate(newKey);
  };

  const getProviderName = (provider: AIProvider) => {
    return PROVIDERS.find(p => p.id === provider)?.name || provider;
  };

  const getProviderIcon = (provider: AIProvider) => {
    return PROVIDERS.find(p => p.id === provider)?.icon || '🔑';
  };

  // Access denied for non-super admins for API keys, but admins can access AI features
  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card>
          <div className="text-center p-8">
            <svg
              className="w-16 h-16 mx-auto text-red-500 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Access Restricted
            </h2>
            <p className="text-gray-500 dark:text-gray-400">
              Only Administrators can access this page.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Admin Settings
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Manage API keys and AI features
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('api-keys')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'api-keys'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400'
            }`}
          >
            <span className="flex items-center gap-2">
              <span>🔑</span>
              API Keys
            </span>
          </button>
          <button
            onClick={() => setActiveTab('ai-features')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'ai-features'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400'
            }`}
          >
            <span className="flex items-center gap-2">
              <span>🤖</span>
              AI Features
            </span>
          </button>
        </nav>
      </div>

      {/* AI Features Tab */}
      {activeTab === 'ai-features' && (
        <AdminAISettings 
          users={usersData || []}
        />
      )}

      {/* API Keys Tab - All Admins */}
      {activeTab === 'api-keys' && (
        <>
      {/* Encryption Status Warning */}
      {encryptionStatus && !encryptionStatus.configured && (
        <Card>
          <div className="flex items-center gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
            <svg
              className="w-6 h-6 text-amber-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <p className="font-medium text-amber-800 dark:text-amber-200">
                Encryption Not Configured
              </p>
              <p className="text-sm text-amber-600 dark:text-amber-300">
                {encryptionStatus.message}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* API Keys Card */}
      <Card>
        <CardHeader 
          title="AI Provider API Keys" 
          subtitle="Securely stored with AES-256-GCM encryption"
        />
        {isLoading && <LoadingOverlay message="Loading API keys..." />}

        {/* Add Key Button */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          {!showAddForm ? (
            <Button onClick={() => setShowAddForm(true)}>
              <svg
                className="w-4 h-4 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Add API Key
            </Button>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Provider Select */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    AI Provider
                  </label>
                  <select
                    value={newKey.provider}
                    onChange={(e) =>
                      setNewKey({ ...newKey, provider: e.target.value as AIProvider })
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                             bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                             focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.icon} {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Label */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Label (Optional)
                  </label>
                  <Input
                    value={newKey.label || ''}
                    onChange={(e) => setNewKey({ ...newKey, label: e.target.value })}
                    placeholder="e.g., Production Key"
                  />
                </div>
              </div>

              {/* API Key Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  API Key
                </label>
                <Input
                  type="password"
                  value={newKey.api_key}
                  onChange={(e) => setNewKey({ ...newKey, api_key: e.target.value })}
                  placeholder={PROVIDERS.find(p => p.id === newKey.provider)?.hint || 'Enter API key'}
                  required
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  The key will be encrypted before storage. Only a preview (last 4 characters) will be visible.
                </p>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Notes (Optional)
                </label>
                <textarea
                  value={newKey.notes || ''}
                  onChange={(e) => setNewKey({ ...newKey, notes: e.target.value })}
                  placeholder="Any additional notes about this key..."
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                           bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                           focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              {/* Form Actions */}
              <div className="flex gap-2">
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Saving...' : 'Save Key'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setShowAddForm(false);
                    setNewKey({ provider: 'gemini', api_key: '', label: '', notes: '' });
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>

        {/* Keys List */}
        <div className="divide-y divide-gray-200 dark:divide-gray-700">
          {keysData?.items && keysData.items.length > 0 ? (
            keysData.items.map((key) => (
              <div
                key={key.id}
                className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <div className="flex items-center gap-4">
                  {/* Provider Icon */}
                  <div className="text-2xl">{getProviderIcon(key.provider)}</div>

                  {/* Key Info */}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {getProviderName(key.provider)}
                      </span>
                      {key.label && (
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          — {key.label}
                        </span>
                      )}
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          key.is_active
                            ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                        }`}
                      >
                        {key.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-4">
                      <span className="font-mono">{key.key_preview}</span>
                      {key.usage_count > 0 && (
                        <span>Used {key.usage_count} times</span>
                      )}
                      {key.last_used_at && (
                        <span>
                          Last used: {new Date(key.last_used_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  {/* Test Button */}
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleTest(key.id)}
                    disabled={testingId === key.id || !key.is_active}
                    title={!key.is_active ? 'Activate key to test' : 'Test connectivity'}
                  >
                    {testingId === key.id ? (
                      <svg
                        className="w-4 h-4 animate-spin"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                    ) : (
                      'Test'
                    )}
                  </Button>

                  {/* Toggle Active */}
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      toggleActiveMutation.mutate({
                        id: key.id,
                        isActive: !key.is_active,
                      })
                    }
                  >
                    {key.is_active ? 'Deactivate' : 'Activate'}
                  </Button>

                  {/* Delete Button */}
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(key)}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
              <svg
                className="w-12 h-12 mx-auto mb-4 opacity-50"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
                />
              </svg>
              <p className="font-medium">No API Keys Configured</p>
              <p className="text-sm mt-1">
                Add an API key to enable AI-powered features.
              </p>
            </div>
          )}
        </div>
      </Card>

      {/* Security Info */}
      <Card>
        <CardHeader title="Security Information" />
        <div className="p-4 space-y-3 text-sm text-gray-600 dark:text-gray-400">
          <div className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <span>
              <strong>AES-256-GCM Encryption:</strong> All API keys are encrypted before
              storage using military-grade encryption.
            </span>
          </div>
          <div className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <span>
              <strong>Key Preview Only:</strong> Once stored, only the last 4 characters
              are displayed for identification.
            </span>
          </div>
          <div className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <span>
              <strong>Audit Logging:</strong> All key operations are recorded in the
              audit log for security compliance.
            </span>
          </div>
          <div className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <span>
              <strong>Super Admin Only:</strong> Only Super Administrators can view,
              add, or manage API keys.
            </span>
          </div>
        </div>
      </Card>
        </>
      )}
    </div>
  );
}

