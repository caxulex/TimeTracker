// ============================================
// TIME TRACKER - INTEGRATIONS PAGE
// ============================================
// Basecamp v1 integration UI: status, connect, sync, disconnect.
// Visible to admin + super_admin; only super_admin can mutate.
// ============================================
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Plug } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useNotifications } from '../hooks/useNotifications';
import { useTeams } from '../hooks/useApi';
import { isAdminUser, isSuperAdmin } from '../utils/helpers';
import {
  basecampApi,
  type BasecampStatus,
  type BasecampSyncResult,
} from '../api/basecamp';
import { formatDateTime, getRelativeTime } from '../utils/helpers';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'not_configured' }
  | { kind: 'access_denied' }
  | { kind: 'ready'; status: BasecampStatus }
  | { kind: 'error'; message: string };

function ConfirmDisconnectModal({
  open,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="presentation"
      onClick={() => {
        if (!busy) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="disconnect-title"
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="disconnect-title"
          className="text-lg font-semibold text-gray-900 dark:text-gray-100"
        >
          Disconnect Basecamp?
        </h2>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
          Are you sure? This will delete the connection but preserve previously
          imported projects.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {busy && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            )}
            Disconnect
          </button>
        </div>
      </div>
    </div>
  );
}

export function IntegrationsPage() {
  const { user } = useAuthStore();
  const { addNotification } = useNotifications();
  const [searchParams, setSearchParams] = useSearchParams();

  const canView = isAdminUser(user);
  const canMutate = isSuperAdmin(user);

  const [state, setState] = useState<LoadState>(
    canView ? { kind: 'loading' } : { kind: 'access_denied' }
  );
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [lastSync, setLastSync] = useState<BasecampSyncResult | null>(null);
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const [savingTeam, setSavingTeam] = useState(false);
  const [savingAutoSync, setSavingAutoSync] = useState(false);
  const teamsQuery = useTeams();

  const fetchStatus = useCallback(async () => {
    try {
      const status = await basecampApi.getStatus();
      setState({ kind: 'ready', status });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 503) {
        setState({ kind: 'not_configured' });
        return;
      }
      if (axios.isAxiosError(err) && err.response?.status === 403) {
        setState({ kind: 'access_denied' });
        return;
      }
      const message =
        (axios.isAxiosError(err) &&
          (err.response?.data as { detail?: string } | undefined)?.detail) ||
        'Failed to load Basecamp status.';
      setState({ kind: 'error', message });
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    if (!canView) return;
    fetchStatus();
  }, [canView, fetchStatus]);

  // OAuth callback handling
  useEffect(() => {
    const status = searchParams.get('status');
    if (!status) return;
    if (status === 'connected') {
      addNotification({
        type: 'success',
        title: 'Successfully connected to Basecamp!',
      });
    } else if (status === 'error') {
      const detail = searchParams.get('message') || 'Unable to connect to Basecamp.';
      addNotification({ type: 'error', title: 'Connection failed', message: detail });
    }
    // Clear query params so refresh doesn't re-trigger
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams, addNotification]);

  const onConnect = async () => {
    setConnecting(true);
    try {
      const { authorization_url } = await basecampApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch (err) {
      const message =
        (axios.isAxiosError(err) &&
          (err.response?.data as { detail?: string } | undefined)?.detail) ||
        'Could not start Basecamp authorization.';
      addNotification({ type: 'error', title: 'Connect failed', message });
      setConnecting(false);
    }
  };

  const onSync = async () => {
    setSyncing(true);
    try {
      const result = await basecampApi.sync(false);
      setLastSync(result);
      setDetailsExpanded(false);
      const summary = `${result.created} created, ${result.updated} updated, ${result.unchanged} unchanged`;
      if (result.errors.length > 0) {
        addNotification({
          type: 'warning',
          title: `Sync completed with ${result.errors.length} error${result.errors.length === 1 ? '' : 's'}`,
          message: summary,
        });
      } else {
        addNotification({
          type: 'success',
          title: 'Sync complete',
          message: summary,
        });
      }
      // Refresh status to update last_sync_at
      fetchStatus();
    } catch (err) {
      const message =
        (axios.isAxiosError(err) &&
          (err.response?.data as { detail?: string } | undefined)?.detail) ||
        'Sync failed.';
      addNotification({ type: 'error', title: 'Sync failed', message });
    } finally {
      setSyncing(false);
    }
  };

  const onTargetTeamChange = async (raw: string) => {
    const next = raw === '' ? null : Number(raw);
    setSavingTeam(true);
    try {
      const updated = await basecampApi.updateSettings({ target_team_id: next });
      setState({ kind: 'ready', status: updated });
      addNotification({ type: 'success', title: 'Target team updated' });
    } catch (err) {
      const message =
        (axios.isAxiosError(err) &&
          (err.response?.data as { detail?: string } | undefined)?.detail) ||
        'Failed to update target team.';
      addNotification({ type: 'error', title: 'Update failed', message });
    } finally {
      setSavingTeam(false);
    }
  };

  const onAutoSyncToggle = async (next: boolean) => {
    setSavingAutoSync(true);
    try {
      const updated = await basecampApi.updateSettings({ auto_sync_enabled: next });
      setState({ kind: 'ready', status: updated });
      addNotification({
        type: 'success',
        title: next ? 'Auto-sync enabled' : 'Auto-sync disabled',
      });
    } catch (err) {
      const message =
        (axios.isAxiosError(err) &&
          (err.response?.data as { detail?: string } | undefined)?.detail) ||
        'Failed to update auto-sync.';
      addNotification({ type: 'error', title: 'Update failed', message });
    } finally {
      setSavingAutoSync(false);
    }
  };

  const onDisconnectConfirm = async () => {
    setDisconnecting(true);
    try {
      await basecampApi.disconnect();
      addNotification({ type: 'success', title: 'Basecamp disconnected.' });
      setConfirmOpen(false);
      setLastSync(null);
      setDetailsExpanded(false);
      await fetchStatus();
    } catch (err) {
      const message =
        (axios.isAxiosError(err) &&
          (err.response?.data as { detail?: string } | undefined)?.detail) ||
        'Disconnect failed.';
      addNotification({ type: 'error', title: 'Disconnect failed', message });
    } finally {
      setDisconnecting(false);
    }
  };

  // ====== Render ======
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Integrations
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Connect external services to import projects and keep your data in sync.
        </p>
      </header>

      {state.kind === 'access_denied' && (
        <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-200">
          Access denied. You don't have permission to view integrations.
        </div>
      )}

      {state.kind !== 'access_denied' && (
        <section
          className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800"
          aria-labelledby="basecamp-heading"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                <Plug className="h-5 w-5" />
              </div>
              <div>
                <h2
                  id="basecamp-heading"
                  className="text-lg font-semibold text-gray-900 dark:text-gray-100"
                >
                  Basecamp
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Import projects from your Basecamp account.
                </p>
              </div>
            </div>

            {state.kind === 'ready' && (
              <span
                className={
                  state.status.connected
                    ? 'inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/40 dark:text-green-200'
                    : 'inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-700 dark:text-gray-200'
                }
                data-testid="basecamp-status-badge"
              >
                {state.status.connected ? 'Connected' : 'Not connected'}
              </span>
            )}
          </div>

          <div className="mt-6">
            {state.kind === 'loading' && (
              <div data-testid="basecamp-skeleton" className="space-y-3">
                <div className="h-4 w-2/3 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-4 w-1/2 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-9 w-40 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
              </div>
            )}

            {state.kind === 'not_configured' && (
              <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-200">
                Basecamp integration is not configured. Contact your administrator.
              </div>
            )}

            {state.kind === 'error' && (
              <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200">
                {state.message}
              </div>
            )}

            {state.kind === 'ready' && !state.status.connected && (
              <div className="space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  No Basecamp account is connected yet.
                </p>
                {canMutate ? (
                  <button
                    type="button"
                    onClick={onConnect}
                    disabled={connecting}
                    className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {connecting && (
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    )}
                    Connect to Basecamp
                  </button>
                ) : (
                  <p className="text-sm italic text-gray-500 dark:text-gray-400">
                    Contact a super admin to connect.
                  </p>
                )}
              </div>
            )}

            {state.kind === 'ready' && state.status.connected && (
              <div className="space-y-4">
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Account
                    </dt>
                    <dd
                      className="mt-1 text-sm text-gray-900 dark:text-gray-100"
                      data-testid="basecamp-account-name"
                    >
                      {state.status.account_name || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Last synced
                    </dt>
                    <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">
                      {state.status.last_sync_at
                        ? getRelativeTime(state.status.last_sync_at)
                        : 'Never'}
                    </dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Token expires
                    </dt>
                    <dd className="mt-1 text-sm text-gray-900 dark:text-gray-100">
                      {state.status.expires_at
                        ? formatDateTime(state.status.expires_at)
                        : '—'}
                    </dd>
                  </div>
                </dl>

                <div
                  className="mt-2 rounded-md border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/40"
                  data-testid="basecamp-sync-settings"
                >
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    Sync Settings
                  </h3>
                  <div className="mt-3 space-y-3">
                    <label
                      className="flex flex-col gap-1 text-sm text-gray-700 dark:text-gray-200 sm:flex-row sm:items-center sm:gap-3"
                      htmlFor="basecamp-target-team"
                    >
                      <span className="sm:w-48">Projects sync to:</span>
                      <select
                        id="basecamp-target-team"
                        data-testid="basecamp-target-team-select"
                        value={state.status.target_team_id ?? ''}
                        disabled={!canMutate || savingTeam || teamsQuery.isLoading}
                        onChange={(e) => onTargetTeamChange(e.target.value)}
                        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm disabled:opacity-60 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                      >
                        <option value="">
                          (Default: lowest-id team
                          {state.status.target_team_id === null &&
                          state.status.target_team_name === null
                            ? ''
                            : ''}
                          )
                        </option>
                        {(teamsQuery.data?.items ?? []).map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                      {savingTeam && (
                        <span
                          className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
                          aria-label="Saving"
                        />
                      )}
                    </label>

                    <label
                      className="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-200"
                      htmlFor="basecamp-auto-sync"
                    >
                      <input
                        id="basecamp-auto-sync"
                        data-testid="basecamp-auto-sync-toggle"
                        type="checkbox"
                        checked={state.status.auto_sync_enabled}
                        disabled={!canMutate || savingAutoSync}
                        onChange={(e) => onAutoSyncToggle(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-60"
                      />
                      <span>Auto-sync every 4 hours</span>
                      {savingAutoSync && (
                        <span
                          className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
                          aria-label="Saving"
                        />
                      )}
                    </label>
                  </div>
                </div>

                {canMutate ? (
                  <div className="flex flex-wrap gap-3 pt-2">
                    <button
                      type="button"
                      onClick={onSync}
                      disabled={syncing || disconnecting}
                      className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {syncing && (
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      )}
                      Sync Now
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmOpen(true)}
                      disabled={syncing || disconnecting}
                      className="inline-flex items-center gap-2 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-700 dark:bg-gray-800 dark:text-red-300"
                    >
                      Disconnect
                    </button>
                  </div>
                ) : (
                  <p className="pt-2 text-sm italic text-gray-500 dark:text-gray-400">
                    Read-only view. Contact a super admin to sync or disconnect.
                  </p>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {lastSync && (
        <section
          className="mt-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
          aria-label="Last sync result"
        >
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-700 dark:text-gray-200">
              Last sync: {lastSync.created} created, {lastSync.updated} updated,{' '}
              {lastSync.unchanged} unchanged, {lastSync.errors.length} error
              {lastSync.errors.length === 1 ? '' : 's'}
            </p>
            <button
              type="button"
              onClick={() => setDetailsExpanded((v) => !v)}
              className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              {detailsExpanded ? 'Hide details' : 'View details'}
            </button>
          </div>
          {detailsExpanded && (
            <div className="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
              {lastSync.errors.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No errors reported.
                </p>
              ) : (
                <ul className="list-disc space-y-1 pl-5 text-sm text-red-700 dark:text-red-300">
                  {lastSync.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      <ConfirmDisconnectModal
        open={confirmOpen}
        busy={disconnecting}
        onCancel={() => {
          if (!disconnecting) setConfirmOpen(false);
        }}
        onConfirm={onDisconnectConfirm}
      />
    </div>
  );
}

export default IntegrationsPage;
