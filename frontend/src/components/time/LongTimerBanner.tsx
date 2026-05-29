// ============================================
// TIME TRACKER - LONG TIMER BANNER (PR-B)
// Amber in-app warning that appears above the TimerWidget when the
// running TimeEntry has been going for 6+ hours. Re-fires at each 2h
// step (6h, 8h, 10h, 12h, ...). Pairs with the backend hourly email
// warning shipped in PR #5 — this is the foreground / in-app half.
// ============================================
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';
import { timeEntriesApi } from '../../api/client';
import { useTimerStore } from '../../stores/timerStore';
import { useStopTimer } from '../../hooks/useApi';
import { getCurrentBannerLevel } from '../../utils/longTimerThresholds';
import { EditEntryModal } from './EditEntryModal';
import { Button } from '../common';

const DISMISSALS_STORAGE_KEY = 'longTimerDismissals';
const PERMISSION_STORAGE_KEY = 'longTimerNotificationPermission';

type DismissalMap = Record<string, number>;

function readDismissals(): DismissalMap {
  try {
    const raw = localStorage.getItem(DISMISSALS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as DismissalMap) : {};
  } catch {
    return {};
  }
}

function writeDismissals(map: DismissalMap): void {
  try {
    localStorage.setItem(DISMISSALS_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore quota / privacy errors */
  }
}

function getNotificationApi(): typeof Notification | null {
  if (typeof window === 'undefined') return null;
  const N = (window as unknown as { Notification?: typeof Notification }).Notification;
  return N || null;
}

export function LongTimerBanner() {
  const { t } = useTranslation();
  const { currentEntry, isRunning, elapsedSeconds } = useTimerStore();
  const stopTimer = useStopTimer();

  const [dismissals, setDismissals] = useState<DismissalMap>(() => readDismissals());
  const [editOpen, setEditOpen] = useState(false);
  const lastNotifiedLevelRef = useRef<number | null>(null);
  const permissionRequestedRef = useRef(false);

  const entryId = currentEntry?.id ?? null;
  const entryKey = entryId !== null ? String(entryId) : null;
  const lastDismissedLevel = entryKey ? (dismissals[entryKey] ?? null) : null;

  const level = useMemo(() => {
    if (!isRunning || !currentEntry) return null;
    return getCurrentBannerLevel(elapsedSeconds, lastDismissedLevel);
  }, [isRunning, currentEntry, elapsedSeconds, lastDismissedLevel]);

  // Reset cross-entry notify guard when entry changes.
  useEffect(() => {
    lastNotifiedLevelRef.current = null;
    permissionRequestedRef.current = false;
  }, [entryId]);

  // Request Notification permission on first banner render for this entry.
  useEffect(() => {
    if (level === null) return;
    if (permissionRequestedRef.current) return;
    permissionRequestedRef.current = true;

    const N = getNotificationApi();
    if (!N) return;

    let storedDecision: string | null = null;
    try {
      storedDecision = localStorage.getItem(PERMISSION_STORAGE_KEY);
    } catch {
      storedDecision = null;
    }

    if (storedDecision === 'denied') return; // respect prior denial

    if (N.permission === 'default') {
      try {
        const maybePromise = N.requestPermission((result) => {
          try {
            localStorage.setItem(PERMISSION_STORAGE_KEY, result);
          } catch { /* ignore */ }
        });
        if (maybePromise && typeof (maybePromise as Promise<NotificationPermission>).then === 'function') {
          (maybePromise as Promise<NotificationPermission>).then((result) => {
            try {
              localStorage.setItem(PERMISSION_STORAGE_KEY, result);
            } catch { /* ignore */ }
          }).catch(() => { /* ignore */ });
        }
      } catch {
        /* ignore */
      }
    } else {
      try {
        localStorage.setItem(PERMISSION_STORAGE_KEY, N.permission);
      } catch { /* ignore */ }
    }
  }, [level]);

  // Fire a system notification when the banner level appears/changes.
  useEffect(() => {
    if (level === null) return;
    if (lastNotifiedLevelRef.current === level) return;

    const N = getNotificationApi();
    if (!N) return;
    if (N.permission !== 'granted') return;

    let cancelled = false;

    const verifyAndNotify = async () => {
      try {
        const fresh = await timeEntriesApi.getTimer();
        if (cancelled) {
          return;
        }

        const freshEntry = fresh.current_entry;
        const mismatchedEntry = !!currentEntry && !!freshEntry && freshEntry.id !== currentEntry.id;
        const noActiveTimer = !fresh.is_running || !freshEntry;

        if (noActiveTimer || mismatchedEntry) {
          useTimerStore.getState().applyServerState(fresh);
          return;
        }

        const taskName =
          currentEntry?.description ||
          (currentEntry?.task_id ? `Task #${currentEntry.task_id}` : '') ||
          (currentEntry?.project_id ? `Project #${currentEntry.project_id}` : '') ||
          t('time.noDescription');

        try {
          new N(t('time.longTimerBanner.notificationTitle'), {
            body: t('time.longTimerBanner.notificationBody', { taskName, hours: level }),
          });
          lastNotifiedLevelRef.current = level;
        } catch {
          /* ignore — some test environments construct-throw */
        }
      } catch {
        // Conservative path: skip notification when the pre-flight verification fails.
      }
    };

    void verifyAndNotify();

    return () => {
      cancelled = true;
    };
  }, [level, currentEntry, t]);

  const handleKeepGoing = useCallback(() => {
    if (!entryKey || level === null) return;
    const next = { ...dismissals, [entryKey]: level };
    setDismissals(next);
    writeDismissals(next);
  }, [dismissals, entryKey, level]);

  const handleStopNow = useCallback(() => {
    stopTimer.mutate();
  }, [stopTimer]);

  const handleAdjustEndTime = useCallback(() => {
    setEditOpen(true);
  }, []);

  const handleModalClose = useCallback(() => setEditOpen(false), []);
  const handleModalSaved = useCallback(() => setEditOpen(false), []);

  if (level === null || !currentEntry) {
    // Still render the modal portal if it happens to be open (defensive).
    return editOpen ? (
      <EditEntryModal
        entry={currentEntry}
        isOpen={editOpen}
        onClose={handleModalClose}
        onSaved={handleModalSaved}
      />
    ) : null;
  }

  return (
    <>
      <div
        role="alert"
        data-testid="long-timer-banner"
        className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-sm"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          <div className="flex items-start gap-3 flex-1">
            <AlertTriangle
              className="h-6 w-6 flex-shrink-0 text-amber-600 mt-0.5"
              aria-hidden="true"
            />
            <div className="flex-1">
              <p className="font-semibold text-amber-900">
                {t('time.longTimerBanner.title', { hours: level })}
              </p>
              <p className="text-sm text-amber-800 mt-0.5">
                {t('time.longTimerBanner.subtitle')}
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:gap-2 sm:flex-shrink-0">
            <Button
              variant="primary"
              size="sm"
              onClick={handleKeepGoing}
              className="bg-amber-600 hover:bg-amber-700 focus:ring-amber-500"
            >
              {t('time.longTimerBanner.keepGoing')}
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleStopNow}
              isLoading={stopTimer.isPending}
            >
              {t('time.longTimerBanner.stopNow')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleAdjustEndTime}
              className="text-amber-800 underline hover:bg-amber-100"
            >
              {t('time.longTimerBanner.adjustEndTime')}
            </Button>
          </div>
        </div>
      </div>
      <EditEntryModal
        entry={currentEntry}
        isOpen={editOpen}
        onClose={handleModalClose}
        onSaved={handleModalSaved}
      />
    </>
  );
}
