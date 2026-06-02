/**
 * AnomalyAlertPanel Component
 * 
 * Displays anomaly detection results for admin dashboard.
 * Shows warnings about unusual time tracking patterns.
 */

import React, { useState } from 'react';
import {
  useAllAnomalies,
  useAnomalyScan,
  useDismissAnomaly,
  useDismissedAnomalies,
  useRestoreAnomalyDismissal,
} from '../../hooks/useAIServices';
import { AnomalyDetails, DismissedAnomaly } from '../../api/aiServices';

interface AnomalyAlertPanelProps {
  // Period in days to analyze
  periodDays?: number;
  // Optional team filter
  teamId?: number;
  // Whether user is admin
  isAdmin?: boolean;
  // Compact mode for sidebar
  compact?: boolean;
  // Maximum items to show
  maxItems?: number;
}

export const AnomalyAlertPanel: React.FC<AnomalyAlertPanelProps> = ({
  periodDays = 7,
  teamId,
  isAdmin = false,
  compact = false,
  maxItems = 10,
}) => {
  const [expandedAnomaly, setExpandedAnomaly] = useState<string | null>(null);
  const [dismissReason, setDismissReason] = useState('');
  const [showDismissModal, setShowDismissModal] = useState<AnomalyDetails | null>(null);
  const [dismissError, setDismissError] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'active' | 'dismissed'>('active');

  const { data, isLoading, error, refetch } = useAllAnomalies(periodDays, teamId, {
    enabled: isAdmin,
  });

  const {
    data: dismissedData,
    isLoading: isDismissedLoading,
    error: dismissedError,
    refetch: refetchDismissed,
  } = useDismissedAnomalies(
    { limit: maxItems, offset: 0 },
    { enabled: isAdmin && activeTab === 'dismissed' }
  );

  const { mutate: scanAnomalies, isPending: isScanning } = useAnomalyScan();
  const { mutate: dismissAnomaly, isPending: isDismissing } = useDismissAnomaly();
  const { mutate: restoreAnomalyDismissal, isPending: isRestoring } = useRestoreAnomalyDismissal();

  const handleScan = () => {
    scanAnomalies({
      period_days: periodDays,
      team_id: teamId,
      scan_all: true,
    });
  };

  const handleDismiss = (anomaly: AnomalyDetails) => {
    setDismissError(null);
    dismissAnomaly({
      user_id: anomaly.user_id,
      anomaly_type: anomaly.type,
      reason: dismissReason,
    }, {
      onSuccess: () => {
        setShowDismissModal(null);
        setDismissReason('');
        setDismissError(null);
        refetch();
      },
      onError: () => {
        // Persistence failure (backend returns 500). Surface a
        // user-visible message so the dismiss button no longer looks
        // like a silent no-op.
        setDismissError('Failed to dismiss anomaly. Please try again.');
      },
    });
  };

  const handleRestore = (dismissal: DismissedAnomaly) => {
    setRestoreError(null);
    restoreAnomalyDismissal(dismissal.id, {
      onSuccess: () => {
        setRestoreError(null);
        refetchDismissed();
        refetch();
      },
      onError: () => {
        setRestoreError('Failed to restore dismissal. Please try again.');
      },
    });
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return '🔴';
      case 'warning':
        return '🟡';
      case 'info':
      default:
        return '🔵';
    }
  };

  const getSeverityClasses = (severity: string): string => {
    switch (severity) {
      case 'critical':
        return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800';
      case 'info':
      default:
        return 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800';
    }
  };

  const getTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      extended_day: 'Extended Work Day',
      consecutive_long_days: 'Consecutive Long Days',
      weekend_spike: 'Weekend Work Spike',
      missing_time: 'Missing Time Entries',
      duplicate_entry: 'Potential Duplicates',
      overtime_risk: 'Overtime Risk',
      burnout_risk: 'Burnout Risk',
    };
    return labels[type] || type;
  };

  if (!isAdmin) {
    return null;
  }

  const anomalies = data?.anomalies || [];
  const statistics = data?.statistics;
  const displayedAnomalies = anomalies.slice(0, maxItems);
  const hasMore = anomalies.length > maxItems;
  const dismissedAnomalies = dismissedData || [];

  if (compact) {
    // Compact sidebar view
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center">
            <span className="mr-2">⚠️</span>
            Anomaly Alerts
          </h3>
          {statistics && (
            <span className={`
              px-2 py-0.5 text-xs rounded-full font-medium
              ${statistics.critical_count > 0 
                ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
              }
            `}>
              {statistics.total_anomalies}
            </span>
          )}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          </div>
        ) : error ? (
          <p className="text-sm text-red-500">Failed to load</p>
        ) : anomalies.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No anomalies detected ✓
          </p>
        ) : (
          <ul className="space-y-2">
            {displayedAnomalies.slice(0, 5).map((anomaly, index) => (
              <li 
                key={`${anomaly.user_id}-${anomaly.type}-${index}`}
                className={`
                  p-2 rounded border text-xs
                  ${getSeverityClasses(anomaly.severity)}
                `}
              >
                <div className="flex items-start">
                  <span className="mr-1.5">{getSeverityIcon(anomaly.severity)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white truncate">
                      {anomaly.user_name}
                    </p>
                    <p className="text-gray-600 dark:text-gray-300 truncate">
                      {getTypeLabel(anomaly.type)}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  // Full panel view
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <span className="mr-2">⚠️</span>
            Anomaly Detection
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Unusual patterns in time tracking data (last {periodDays} days)
          </p>
        </div>
        {activeTab === 'active' && (
          <button
            onClick={handleScan}
            disabled={isScanning}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium
              ${isScanning
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-gray-700'
                : 'bg-blue-600 text-white hover:bg-blue-700'
              }
            `}
          >
            {isScanning ? 'Scanning...' : '🔄 Scan Now'}
          </button>
        )}
      </div>

      <div className="px-6 pt-4">
        <div role="tablist" aria-label="Anomaly views" className="inline-flex rounded-lg bg-gray-100 p-1 dark:bg-gray-700">
          <button
            role="tab"
            aria-selected={activeTab === 'active'}
            onClick={() => setActiveTab('active')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'active'
              ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
              : 'text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white'
            }`}
          >
            Active
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'dismissed'}
            onClick={() => setActiveTab('dismissed')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'dismissed'
              ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
              : 'text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white'
            }`}
          >
            Dismissed
          </button>
        </div>
      </div>

      {/* Statistics */}
      {activeTab === 'active' && statistics && (
        <div className="px-6 py-3 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 grid grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {statistics.users_scanned}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Users Scanned</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {statistics.critical_count}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Critical</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {statistics.warning_count}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Warnings</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {statistics.info_count}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Info</p>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {activeTab === 'active' && isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : activeTab === 'active' && error ? (
          <div className="px-6 py-8 text-center">
            <p className="text-red-500">Failed to load anomaly data</p>
            <button
              onClick={() => refetch()}
              className="mt-2 text-sm text-blue-500 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : activeTab === 'active' && anomalies.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <span className="text-4xl">✓</span>
            <p className="mt-2 text-gray-600 dark:text-gray-300 font-medium">
              No anomalies detected
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              All time tracking patterns appear normal
            </p>
          </div>
        ) : activeTab === 'active' ? (
          displayedAnomalies.map((anomaly, index) => (
            <div
              key={`${anomaly.user_id}-${anomaly.type}-${index}`}
              className={`px-6 py-4 ${getSeverityClasses(anomaly.severity)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  <span className="text-xl">{getSeverityIcon(anomaly.severity)}</span>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="font-medium text-gray-900 dark:text-white">
                        {anomaly.user_name}
                      </h3>
                      <span className={`
                        px-2 py-0.5 text-xs rounded-full font-medium
                        ${anomaly.severity === 'critical' ? 'bg-red-200 text-red-800' : ''}
                        ${anomaly.severity === 'warning' ? 'bg-yellow-200 text-yellow-800' : ''}
                        ${anomaly.severity === 'info' ? 'bg-blue-200 text-blue-800' : ''}
                      `}>
                        {anomaly.severity.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mt-1">
                      {getTypeLabel(anomaly.type)}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                      {anomaly.description}
                    </p>
                    
                    {/* Expandable details */}
                    <button
                      onClick={() => setExpandedAnomaly(
                        expandedAnomaly === `${anomaly.user_id}-${anomaly.type}-${index}` 
                          ? null 
                          : `${anomaly.user_id}-${anomaly.type}-${index}`
                      )}
                      className="text-sm text-blue-600 hover:underline mt-2"
                    >
                      {expandedAnomaly === `${anomaly.user_id}-${anomaly.type}-${index}` 
                        ? 'Hide details' 
                        : 'Show details'}
                    </button>
                    
                    {expandedAnomaly === `${anomaly.user_id}-${anomaly.type}-${index}` && (
                      <div className="mt-3 p-3 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-600">
                        <pre className="text-xs text-gray-600 dark:text-gray-300 overflow-x-auto">
                          {JSON.stringify(anomaly.details, null, 2)}
                        </pre>
                        {anomaly.recommendation && (
                          <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                            <p className="text-xs font-medium text-gray-700 dark:text-gray-200">
                              Recommendation:
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-300">
                              {anomaly.recommendation}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setShowDismissModal(anomaly)}
                    className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 
                             rounded hover:bg-gray-100 dark:hover:bg-gray-700
                             text-gray-600 dark:text-gray-300"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))
        ) : isDismissedLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : dismissedError ? (
          <div className="px-6 py-8 text-center">
            <p className="text-red-500">Failed to load dismissed anomalies</p>
            <button
              onClick={() => refetchDismissed()}
              className="mt-2 text-sm text-blue-500 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : dismissedAnomalies.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-gray-600 dark:text-gray-300 font-medium">
              No anomalies have been dismissed for your company.
            </p>
          </div>
        ) : (
          <div className="space-y-3 px-6 py-4">
            {restoreError && (
              <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200">
                {restoreError}
              </div>
            )}
            {dismissedAnomalies.map((dismissal) => (
              <div
                key={dismissal.id}
                className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-700/40"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate font-medium text-gray-900 dark:text-white">
                        {dismissal.target_user_name}
                      </h3>
                      <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs uppercase tracking-wide text-gray-700 dark:bg-gray-600 dark:text-gray-200">
                        {getTypeLabel(dismissal.anomaly_type)}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                      {dismissal.target_user_email}
                    </p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Dismissed {new Date(dismissal.dismissed_at).toLocaleString()} by {dismissal.dismissed_by_name || 'unknown'}
                    </p>
                    {dismissal.reason && (
                      <div className="group mt-2 max-w-3xl">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          Reason
                        </p>
                        <p
                          className="mt-1 overflow-hidden text-ellipsis whitespace-nowrap text-sm text-gray-700 dark:text-gray-200 group-hover:whitespace-normal group-hover:overflow-visible"
                          title={dismissal.reason}
                        >
                          {dismissal.reason}
                        </p>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => handleRestore(dismissal)}
                    disabled={isRestoring}
                    className="shrink-0 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                  >
                    {isRestoring ? 'Restoring...' : 'Restore'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'active' && hasMore && (
          <div className="px-6 py-3 text-center bg-gray-50 dark:bg-gray-700/50">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Showing {maxItems} of {anomalies.length} anomalies
            </p>
          </div>
        )}
      </div>

      {/* Dismiss Modal */}
      {showDismissModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Dismiss Anomaly
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
              Dismissing anomaly for <strong>{showDismissModal.user_name}</strong>:{' '}
              {getTypeLabel(showDismissModal.type)}
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Reason (optional)
              </label>
              <textarea
                value={dismissReason}
                onChange={(e) => setDismissReason(e.target.value)}
                placeholder="e.g., Approved overtime, Project deadline..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 
                         rounded-lg dark:bg-gray-700 dark:text-white
                         focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
              />
            </div>
            {dismissError && (
              <div
                role="alert"
                className="mb-4 px-3 py-2 rounded bg-red-50 border border-red-200
                           text-sm text-red-700 dark:bg-red-900/30 dark:border-red-800
                           dark:text-red-200"
                data-testid="anomaly-dismiss-error"
              >
                {dismissError}
              </div>
            )}
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowDismissModal(null);
                  setDismissReason('');
                  setDismissError(null);
                }}
                className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 
                         rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700
                         text-gray-600 dark:text-gray-300"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDismiss(showDismissModal)}
                disabled={isDismissing}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg 
                         hover:bg-blue-700 disabled:opacity-50"
              >
                {isDismissing ? 'Dismissing...' : 'Dismiss'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnomalyAlertPanel;
