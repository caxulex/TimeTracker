/**
 * Admin AI Settings Component
 * 
 * Admin panel for managing global AI features and per-user overrides.
 */

import React, { useState } from 'react';
import {
  useAdminAIFeatures,
  useToggleGlobalFeature,
  useUsageSummary,
  useUserPreferencesAdmin,
  useSetUserOverride,
  useRemoveUserOverride,
  useSeedAIFeatures,
} from '../../hooks/useAIFeatures';
import { FEATURE_UI_CONFIG } from '../../types/aiFeatures';
import type { AdminFeatureSummary, FeatureStatus } from '../../types/aiFeatures';

interface AdminAISettingsProps {
  className?: string;
  users?: Array<{ id: number; name: string; email: string }>;
}

export const AdminAISettings: React.FC<AdminAISettingsProps> = ({ 
  className = '',
  users = [],
}) => {
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: featuresData, isLoading: featuresLoading } = useAdminAIFeatures();
  const { data: usageData } = useUsageSummary(30);
  const { data: selectedUserPrefs, isLoading: userPrefsLoading } = useUserPreferencesAdmin(selectedUserId);

  const toggleGlobalMutation = useToggleGlobalFeature();
  const setOverrideMutation = useSetUserOverride();
  const removeOverrideMutation = useRemoveUserOverride();
  const seedMutation = useSeedAIFeatures();

  const handleGlobalToggle = (featureId: string, enabled: boolean) => {
    toggleGlobalMutation.mutate({ featureId, isEnabled: enabled });
  };

  const handleUserOverride = (userId: number, featureId: string, enabled: boolean) => {
    setOverrideMutation.mutate({ userId, featureId, isEnabled: enabled });
  };

  const handleRemoveOverride = (userId: number, featureId: string) => {
    removeOverrideMutation.mutate({ userId, featureId });
  };

  const filteredUsers = users.filter(
    (user) =>
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (featuresLoading) {
    return (
      <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 bg-gray-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const features = featuresData?.features || [];

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Usage Summary Card */}
      {usageData && (
        <div className="bg-gradient-to-br from-purple-600 to-purple-800 rounded-xl p-6 text-white shadow-lg">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span>📊</span> AI Usage Summary (Last 30 Days)
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-purple-200 text-sm">Total Requests</p>
              <p className="text-2xl font-bold">{(usageData.total_requests ?? 0).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-purple-200 text-sm">Tokens Used</p>
              <p className="text-2xl font-bold">{(usageData.total_tokens ?? 0).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-purple-200 text-sm">Estimated Cost</p>
              <p className="text-2xl font-bold">${(usageData.total_cost ?? 0).toFixed(2)}</p>
            </div>
            <div>
              <p className="text-purple-200 text-sm">Unique Users</p>
              <p className="text-2xl font-bold">{usageData.unique_users ?? 0}</p>
            </div>
          </div>
        </div>
      )}

      {/* Global Feature Controls */}
      <div className="bg-white rounded-lg shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <span>🎛️</span> Global Feature Controls
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Enable or disable AI features for all users
          </p>
        </div>
        <div className="p-6">
          {features.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500 mb-4">No AI features found in database.</p>
              <button
                onClick={() => seedMutation.mutate()}
                disabled={seedMutation.isPending}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {seedMutation.isPending ? 'Seeding Features...' : '🌱 Seed AI Features'}
              </button>
              {seedMutation.isError && (
                <p className="text-red-500 text-sm mt-2">
                  Error: {(seedMutation.error as Error)?.message || 'Failed to seed features'}
                </p>
              )}
              {seedMutation.isSuccess && (
                <p className="text-green-500 text-sm mt-2">
                  Features seeded successfully! Refreshing...
                </p>
              )}
            </div>
          ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {features.map((feature: AdminFeatureSummary) => {
              const config = FEATURE_UI_CONFIG[feature.feature_id] || {
                icon: '🤖',
                color: 'text-gray-600',
                bgColor: 'bg-gray-50',
              };

              return (
                <div
                  key={feature.feature_id}
                  className={`p-4 rounded-lg border ${
                    feature.is_enabled ? `${config.bgColor} border-gray-200` : 'bg-gray-50 border-gray-100'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 flex-1">
                      <span className="text-xl">{config.icon}</span>
                      <div>
                        <h4 className="font-medium text-gray-900">{feature.feature_name}</h4>
                        {feature.description && (
                          <p className="text-sm text-gray-500 mt-0.5">{feature.description}</p>
                        )}
                        <div className="mt-2 flex items-center gap-3 text-sm">
                          <span className="text-gray-600">
                            {feature.enabled_user_count}/{feature.total_user_count} users
                          </span>
                          {feature.usage_this_month.total_requests > 0 && (
                            <span className="text-gray-400">
                              • {feature.usage_this_month.total_requests} requests
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={feature.is_enabled}
                      onClick={() => handleGlobalToggle(feature.feature_id, !feature.is_enabled)}
                      disabled={toggleGlobalMutation.isPending}
                      className={`
                        w-11 h-6 relative inline-flex flex-shrink-0 rounded-full
                        transition-colors duration-200 ease-in-out cursor-pointer
                        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500
                        ${feature.is_enabled ? 'bg-purple-600' : 'bg-gray-200'}
                      `}
                    >
                      <span
                        className={`
                          w-5 h-5 inline-block rounded-full bg-white shadow-sm
                          transform transition-transform duration-200 ease-in-out
                          ${feature.is_enabled ? 'translate-x-5' : 'translate-x-0.5'}
                        `}
                      />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          )}
        </div>
      </div>

      {/* Per-User Settings */}
      <div className="bg-white rounded-lg shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <span>👥</span> Per-User Settings
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Override AI settings for specific users
          </p>
        </div>
        <div className="p-6">
          {/* User Search */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search User
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name or email..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            />
          </div>

          {/* User List */}
          {users.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 mb-6 max-h-48 overflow-y-auto">
              {filteredUsers.slice(0, 20).map((user) => (
                <button
                  key={user.id}
                  onClick={() => setSelectedUserId(user.id)}
                  className={`
                    p-3 text-left rounded-lg border transition-colors
                    ${selectedUserId === user.id 
                      ? 'bg-purple-50 border-purple-300' 
                      : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                    }
                  `}
                >
                  <p className="font-medium text-gray-900 truncate">{user.name}</p>
                  <p className="text-sm text-gray-500 truncate">{user.email}</p>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">
              No users available. User list should be passed as a prop.
            </p>
          )}

          {/* Selected User Preferences */}
          {selectedUserId && (
            <div className="border-t border-gray-200 pt-6">
              {userPrefsLoading ? (
                <div className="animate-pulse space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 bg-gray-100 rounded"></div>
                  ))}
                </div>
              ) : selectedUserPrefs ? (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h4 className="font-medium text-gray-900">{selectedUserPrefs.user_name}</h4>
                      <p className="text-sm text-gray-500">{selectedUserPrefs.user_email}</p>
                    </div>
                    <button
                      onClick={() => setSelectedUserId(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="space-y-3">
                    {(selectedUserPrefs.preferences || []).map((pref: FeatureStatus) => {
                      const config = FEATURE_UI_CONFIG[pref.feature_id] || {
                        icon: '🤖',
                        color: 'text-gray-600',
                        bgColor: 'bg-gray-50',
                      };

                      return (
                        <div
                          key={pref.feature_id}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="flex items-center gap-2">
                            <span>{config.icon}</span>
                            <span className="font-medium text-gray-900">{pref.feature_name}</span>
                            {pref.admin_override && (
                              <span className="px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded-full">
                                Override
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {pref.admin_override ? (
                              <button
                                onClick={() => handleRemoveOverride(selectedUserId, pref.feature_id)}
                                className="text-sm text-gray-500 hover:text-gray-700"
                              >
                                Remove Override
                              </button>
                            ) : null}
                            <select
                              value={pref.admin_override ? (pref.is_enabled ? 'force_on' : 'force_off') : 'user'}
                              onChange={(e) => {
                                const value = e.target.value;
                                if (value === 'user') {
                                  handleRemoveOverride(selectedUserId, pref.feature_id);
                                } else {
                                  handleUserOverride(selectedUserId, pref.feature_id, value === 'force_on');
                                }
                              }}
                              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-purple-500"
                            >
                              <option value="user">User Choice</option>
                              <option value="force_on">Force ON</option>
                              <option value="force_off">Force OFF</option>
                            </select>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-4">
                  Failed to load user preferences
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminAISettings;
