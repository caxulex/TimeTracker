// ============================================
// TIME TRACKER - EDIT TIME ENTRY MODAL
// PATCH /api/time/entries/{id} — partial updates only.
// Special "stop first" UI for running timers.
// ============================================
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Modal, Button, Input } from '../common';
import { ProjectSelect } from '../projects/ProjectSelect';
import { TaskSelect } from '../tasks/TaskSelect';
import { projectsApi, timeEntriesApi } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';
import { isNoRunningTimerError } from '../../utils/timerErrors';
import { formatDuration } from '../../utils/helpers';
import type { Project, TimeEntry, TimeEntryUpdate } from '../../types';

export interface EditEntryModalProps {
  entry: TimeEntry | null;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

interface FormState {
  date: string;       // YYYY-MM-DD (local)
  startTime: string;  // HH:mm     (local)
  endTime: string;    // HH:mm     (local)
  projectId: number | '';
  taskId: number | '';
  description: string;
}

// Build a YYYY-MM-DD in local timezone (matches the manual-entry pattern
// already used in TimePage).
function localDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function localTime(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

function entryToFormState(entry: TimeEntry): FormState {
  const start = new Date(entry.start_time);
  const end = entry.end_time ? new Date(entry.end_time) : start;
  return {
    date: localDate(start),
    startTime: localTime(start),
    endTime: localTime(end),
    projectId: entry.project_id ?? '',
    taskId: entry.task_id ?? '',
    description: entry.description ?? '',
  };
}

export function EditEntryModal({ entry, isOpen, onClose, onSaved }: EditEntryModalProps) {
  const { t } = useTranslation();
  const { addNotification } = useNotifications();
  const [form, setForm] = useState<FormState | null>(null);
  const [original, setOriginal] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const isRunning = entry?.end_time === null || entry?.end_time === undefined;

  // Reset state whenever a new entry is opened.
  useEffect(() => {
    if (isOpen && entry) {
      const initial = entryToFormState(entry);
      setForm(initial);
      setOriginal(initial);
      setError(null);
    } else if (!isOpen) {
      setForm(null);
      setOriginal(null);
      setError(null);
      setIsSaving(false);
      setIsStopping(false);
    }
  }, [isOpen, entry]);

  // Project list (only when the form is shown).
  //
  // page_size=100 caps at the server's `le=100` ceiling. Without it,
  // editing an entry whose project was outside the most-recent 20
  // would render with the project field unselectable — same
  // pagination-shadow class as PR #30 / PR #33. Query key kept in
  // sync with the rest of the app so the cache is shared with
  // ProjectSelect.
  const { data: projectsData } = useQuery({
    queryKey: ['projects', 'active'],
    queryFn: () => projectsApi.getAll({ include_archived: false, page_size: 100 }),
    enabled: isOpen && !isRunning,
  });
  const projects: Project[] = projectsData?.items ?? [];

  const hasChanges = useMemo(() => {
    if (!form || !original) return false;
    return (
      form.date !== original.date ||
      form.startTime !== original.startTime ||
      form.endTime !== original.endTime ||
      form.projectId !== original.projectId ||
      form.taskId !== original.taskId ||
      form.description !== original.description
    );
  }, [form, original]);

  const liveDurationSeconds = useMemo(() => {
    if (!form) return 0;
    const start = new Date(`${form.date}T${form.startTime}`);
    const end = new Date(`${form.date}T${form.endTime}`);
    const diff = Math.floor((end.getTime() - start.getTime()) / 1000);
    return diff > 0 ? diff : 0;
  }, [form]);

  const handleAttemptClose = () => {
    if (hasChanges) {
      const confirmed = window.confirm(t('time.editEntryDiscardConfirm'));
      if (!confirmed) return;
    }
    onClose();
  };

  const handleStopTimer = async () => {
    setIsStopping(true);
    setError(null);
    try {
      await timeEntriesApi.stopTimer();
      onSaved();
      onClose();
    } catch (err) {
      if (entry && isNoRunningTimerError(err)) {
        try {
          const refreshedEntry = await timeEntriesApi.getById(entry.id);
          if (refreshedEntry.end_time) {
            addNotification({
              type: 'success',
              title: t('common.success'),
              message: 'Entry already stopped',
              duration: 2500,
            });
            onSaved();
            onClose();
            return;
          }
        } catch {
          // If the refetch fails, fall through to the original server error message.
        }
      }

      setError(extractErrorMessage(err, t));
      setIsStopping(false);
    }
  };

  const buildPatch = (current: FormState, baseline: FormState): TimeEntryUpdate => {
    const patch: TimeEntryUpdate = {};

    if (current.description !== baseline.description) {
      patch.description = current.description;
    }
    if (current.projectId !== baseline.projectId) {
      patch.project_id = current.projectId === '' ? undefined : (current.projectId as number);
    }
    if (current.taskId !== baseline.taskId) {
      patch.task_id = current.taskId === '' ? null : (current.taskId as number);
    }

    const dateOrTimeChanged =
      current.date !== baseline.date ||
      current.startTime !== baseline.startTime ||
      current.endTime !== baseline.endTime;
    if (dateOrTimeChanged) {
      const startLocal = new Date(`${current.date}T${current.startTime}`);
      const endLocal = new Date(`${current.date}T${current.endTime}`);
      if (current.date !== baseline.date || current.startTime !== baseline.startTime) {
        patch.start_time = startLocal.toISOString();
      }
      if (current.date !== baseline.date || current.endTime !== baseline.endTime) {
        patch.end_time = endLocal.toISOString();
      }
    }

    return patch;
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!entry || !form || !original || !hasChanges) return;

    const patch = buildPatch(form, original);
    if (Object.keys(patch).length === 0) return;

    setIsSaving(true);
    setError(null);
    try {
      await timeEntriesApi.updateEntry(entry.id, patch);
      onSaved();
      onClose();
    } catch (err) {
      setError(extractErrorMessage(err, t));
      setIsSaving(false);
    }
  };

  if (!isOpen || !entry) return null;

  // ----- Running-timer banner UI -----
  if (isRunning) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title={t('time.editEntryTitle')}>
        <div className="space-y-4">
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
            <p className="font-semibold text-yellow-900 flex items-center gap-2">
              <span aria-hidden="true">⚠️</span>
              {t('time.editEntryRunningTitle')}
            </p>
            <p className="mt-2 text-sm text-yellow-800">
              {t('time.editEntryRunningHint')}
            </p>
          </div>
          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              {error}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              onClick={handleStopTimer}
              isLoading={isStopping}
            >
              {t('time.editEntryStopNow')}
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  // ----- Edit form -----
  if (!form) return null;

  return (
    <Modal isOpen={isOpen} onClose={handleAttemptClose} title={t('time.editEntryTitle')}>
      <form onSubmit={handleSave} className="space-y-4" data-testid="edit-entry-form">
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <div>
          <label htmlFor="edit-entry-date" className="block text-sm font-medium text-gray-700 mb-1">
            {t('time.editEntryDateLabel')}
          </label>
          <Input
            id="edit-entry-date"
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="edit-entry-start" className="block text-sm font-medium text-gray-700 mb-1">
              {t('time.startTimeLabel')}
            </label>
            <Input
              id="edit-entry-start"
              type="time"
              value={form.startTime}
              onChange={(e) => setForm({ ...form, startTime: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="edit-entry-end" className="block text-sm font-medium text-gray-700 mb-1">
              {t('time.endTimeLabel')}
            </label>
            <Input
              id="edit-entry-end"
              type="time"
              value={form.endTime}
              onChange={(e) => setForm({ ...form, endTime: e.target.value })}
            />
          </div>
        </div>

        <div>
          <label htmlFor="edit-entry-project" className="block text-sm font-medium text-gray-700 mb-1">
            {t('time.projectLabel')}
          </label>
          <ProjectSelect
            id="edit-entry-project"
            value={form.projectId === '' ? null : form.projectId}
            onChange={(id) =>
              setForm({
                ...form,
                projectId: id ?? '',
                // Project changed → clear task to avoid mismatched-project errors.
                taskId: '',
              })
            }
            projects={projects}
            placeholder={t('time.noProject')}
          />
        </div>

        {form.projectId !== '' && (
          <div>
            <label htmlFor="edit-entry-task" className="block text-sm font-medium text-gray-700 mb-1">
              {t('time.taskLabel')}
            </label>
            <TaskSelect
              id="edit-entry-task"
              projectId={form.projectId}
              value={form.taskId === '' ? null : form.taskId}
              onChange={(id) =>
                setForm({ ...form, taskId: id ?? '' })
              }
              placeholder={t('time.noTask')}
            />
          </div>
        )}

        <div>
          <label htmlFor="edit-entry-description" className="block text-sm font-medium text-gray-700 mb-1">
            {t('time.descriptionLabel')}
          </label>
          <textarea
            id="edit-entry-description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
            maxLength={500}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div className="rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-sm text-blue-800">
          {t('time.editEntryDuration')}:{' '}
          <span className="font-semibold" data-testid="edit-entry-duration">
            {formatDuration(liveDurationSeconds)}
          </span>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={handleAttemptClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" isLoading={isSaving} disabled={!hasChanges}>
            {t('common.saveChanges')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// Pull a server-provided detail message off an axios error, falling back
// to a generic translated string.
function extractErrorMessage(err: unknown, t: (key: string) => string): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (first && typeof first === 'object' && 'msg' in first) {
        return String((first as { msg: unknown }).msg);
      }
    }
  }
  return t('time.editEntryGenericError');
}

export default EditEntryModal;
