// ============================================
// TIME TRACKER - EDIT ENTRY MODAL TESTS
// Covers spec scenarios: pre-population, save-disabled gating,
// success path, error display, cancel-confirm, running-timer UX,
// project change task reload, live duration.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EditEntryModal } from './EditEntryModal';
import type { TimeEntry } from '../../types';

// ----- Mock API client -----
const updateEntryMock = vi.fn();
const stopTimerMock = vi.fn();
const getByIdMock = vi.fn();
const projectsGetAllMock = vi.fn();
const tasksGetAllMock = vi.fn();
const addNotificationMock = vi.fn();

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({
    addNotification: addNotificationMock,
  }),
}));

vi.mock('../../api/client', () => ({
  timeEntriesApi: {
    updateEntry: (...args: unknown[]) => updateEntryMock(...args),
    stopTimer: (...args: unknown[]) => stopTimerMock(...args),
    getById: (...args: unknown[]) => getByIdMock(...args),
  },
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAllMock(...args),
  },
  tasksApi: {
    getAll: (...args: unknown[]) => tasksGetAllMock(...args),
  },
}));

const PROJECT_A = { id: 1, name: 'Project A', company_id: 1, is_active: true };
const PROJECT_B = { id: 2, name: 'Project B', company_id: 1, is_active: true };
const TASK_1 = { id: 11, name: 'Task 1', project_id: 1, is_active: true };
const TASK_2 = { id: 22, name: 'Task 2', project_id: 2, is_active: true };

// Build an entry whose start/end are anchored to a fixed local clock so
// the rendered HH:mm values are deterministic.
function buildCompletedEntry(overrides: Partial<TimeEntry> = {}): TimeEntry {
  const start = new Date(2025, 5, 15, 9, 0, 0);  // 2025-06-15 09:00 local
  const end = new Date(2025, 5, 15, 10, 30, 0);  // 2025-06-15 10:30 local
  return {
    id: 100,
    user_id: 1,
    project_id: 1,
    task_id: 11,
    start_time: start.toISOString(),
    end_time: end.toISOString(),
    duration_seconds: 5400,
    description: 'Initial description',
    is_running: false,
    created_at: start.toISOString(),
    ...overrides,
  };
}

function buildRunningEntry(): TimeEntry {
  const start = new Date(2025, 5, 15, 9, 0, 0);
  return {
    id: 200,
    user_id: 1,
    project_id: 1,
    task_id: null,
    start_time: start.toISOString(),
    end_time: null,
    duration_seconds: 0,
    description: 'Running timer',
    is_running: true,
    created_at: start.toISOString(),
  };
}

function renderModal(entry: TimeEntry | null, opts: { isOpen?: boolean } = {}) {
  const onClose = vi.fn();
  const onSaved = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <EditEntryModal
        entry={entry}
        isOpen={opts.isOpen ?? true}
        onClose={onClose}
        onSaved={onSaved}
      />
    </QueryClientProvider>
  );
  return { ...utils, onClose, onSaved };
}

describe('EditEntryModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectsGetAllMock.mockResolvedValue({ items: [PROJECT_A, PROJECT_B], total: 2 });
    tasksGetAllMock.mockImplementation((filters?: { project_id?: number }) => {
      if (filters?.project_id === 1) return Promise.resolve({ items: [TASK_1], total: 1 });
      if (filters?.project_id === 2) return Promise.resolve({ items: [TASK_2], total: 1 });
      return Promise.resolve({ items: [], total: 0 });
    });
    addNotificationMock.mockReset();
  });

  it('pre-populates form fields from the entry', async () => {
    renderModal(buildCompletedEntry());

    const desc = await screen.findByLabelText(/description/i) as HTMLTextAreaElement;
    expect(desc.value).toBe('Initial description');

    const startInput = screen.getByLabelText(/start time/i) as HTMLInputElement;
    const endInput = screen.getByLabelText(/end time/i) as HTMLInputElement;
    expect(startInput.value).toBe('09:00');
    expect(endInput.value).toBe('10:30');

    const dateInput = screen.getByLabelText(/^date$/i) as HTMLInputElement;
    expect(dateInput.value).toBe('2025-06-15');
  });

  it('disables Save until a field changes', async () => {
    renderModal(buildCompletedEntry());

    const saveBtn = await screen.findByRole('button', { name: /save changes/i });
    expect(saveBtn).toBeDisabled();

    const desc = screen.getByLabelText(/description/i);
    fireEvent.change(desc, { target: { value: 'Updated text' } });

    expect(saveBtn).not.toBeDisabled();
  });

  it('calls updateEntry, onSaved and onClose on successful save', async () => {
    updateEntryMock.mockResolvedValue(buildCompletedEntry({ description: 'New text' }));

    const { onSaved, onClose } = renderModal(buildCompletedEntry());

    const desc = await screen.findByLabelText(/description/i);
    fireEvent.change(desc, { target: { value: 'New text' } });

    const saveBtn = screen.getByRole('button', { name: /save changes/i });
    fireEvent.click(saveBtn);

    await waitFor(() => expect(updateEntryMock).toHaveBeenCalledTimes(1));
    expect(updateEntryMock).toHaveBeenCalledWith(100, expect.objectContaining({ description: 'New text' }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it('renders an inline error banner on a 4xx response', async () => {
    updateEntryMock.mockRejectedValue({
      response: { data: { detail: 'end_time cannot be in the future' } },
    });

    renderModal(buildCompletedEntry());
    const desc = await screen.findByLabelText(/description/i);
    fireEvent.change(desc, { target: { value: 'Triggers error' } });

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/end_time cannot be in the future/i);
    });
  });

  it('cancel without changes closes immediately (no confirm)', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { onClose } = renderModal(buildCompletedEntry());

    const cancelBtn = await screen.findByRole('button', { name: /cancel/i });
    fireEvent.click(cancelBtn);

    expect(confirmSpy).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('cancel with unsaved changes asks for confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { onClose } = renderModal(buildCompletedEntry());

    const desc = await screen.findByLabelText(/description/i);
    fireEvent.change(desc, { target: { value: 'Pending change' } });

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('shows the "stop first" UI for a running timer (no start/end inputs)', async () => {
    renderModal(buildRunningEntry());

    expect(await screen.findByText(/timer is currently running/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/start time/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/end time/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop timer now/i })).toBeInTheDocument();
  });

  it('"Stop timer now" calls stopTimer and closes the modal', async () => {
    stopTimerMock.mockResolvedValue(buildCompletedEntry());

    const { onClose } = renderModal(buildRunningEntry());
    const stopBtn = await screen.findByRole('button', { name: /stop timer now/i });
    fireEvent.click(stopBtn);

    await waitFor(() => expect(stopTimerMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('on stopTimer 404 no-running it refetches entry, notifies success, and closes', async () => {
    stopTimerMock.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 404,
        data: {
          detail: 'No running timer found',
        },
      },
    });
    getByIdMock.mockResolvedValue(buildCompletedEntry({ id: 200 }));

    const { onClose, onSaved } = renderModal(buildRunningEntry());
    const stopBtn = await screen.findByRole('button', { name: /stop timer now/i });
    fireEvent.click(stopBtn);

    await waitFor(() => {
      expect(stopTimerMock).toHaveBeenCalledTimes(1);
      expect(getByIdMock).toHaveBeenCalledWith(200);
      expect(onSaved).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });

    expect(addNotificationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'success',
        message: 'Entry already stopped',
      })
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('changes to project trigger a task list reload (and clear task)', async () => {
    renderModal(buildCompletedEntry());

    // TaskSelect now fetches on dropdown open. Open once to trigger
    // the initial task fetch for project 1.
    const taskInput = screen.getByLabelText(/task/i) as HTMLInputElement;
    fireEvent.focus(taskInput);
    await waitFor(() =>
      expect(tasksGetAllMock).toHaveBeenCalledWith(
        expect.objectContaining({ project_id: 1, page_size: 20 })
      )
    );

    const projectSelect = await screen.findByLabelText(/project/i) as HTMLInputElement;
    fireEvent.focus(projectSelect);
    fireEvent.change(projectSelect, { target: { value: 'Project B' } });
    const option = await screen.findByTestId('project-select-option-2');
    fireEvent.mouseDown(option);

    // Open task dropdown again to fetch tasks for the new project.
    fireEvent.focus(taskInput);

    await waitFor(() =>
      expect(tasksGetAllMock).toHaveBeenCalledWith(
        expect.objectContaining({ project_id: 2, page_size: 20 })
      )
    );

    // TaskSelect renders the task name in its input. After the project
    // change, the previous task selection is cleared so the input is
    // empty.
    expect(taskInput.value).toBe('');
  });

  it('prefills description from selected task when description is empty', async () => {
    renderModal(buildCompletedEntry({ description: '' }));

    const taskInput = screen.getByLabelText(/task/i) as HTMLInputElement;
    fireEvent.focus(taskInput);
    await waitFor(() =>
      expect(tasksGetAllMock).toHaveBeenCalledWith(
        expect.objectContaining({ project_id: 1, page_size: 20 })
      )
    );

    const option = await screen.findByTestId('task-select-option-11');
    fireEvent.mouseDown(option);

    const desc = screen.getByLabelText(/description/i) as HTMLTextAreaElement;
    expect(desc.value).toBe('Task 1');
  });

  it('does not overwrite typed description when selecting a task', async () => {
    renderModal(buildCompletedEntry({ description: 'User typed text' }));

    const taskInput = screen.getByLabelText(/task/i) as HTMLInputElement;
    fireEvent.focus(taskInput);
    await waitFor(() =>
      expect(tasksGetAllMock).toHaveBeenCalledWith(
        expect.objectContaining({ project_id: 1, page_size: 20 })
      )
    );

    const option = await screen.findByTestId('task-select-option-11');
    fireEvent.mouseDown(option);

    const desc = screen.getByLabelText(/description/i) as HTMLTextAreaElement;
    expect(desc.value).toBe('User typed text');
  });

  it('updates the live duration when start/end change', async () => {
    renderModal(buildCompletedEntry());

    const duration = await screen.findByTestId('edit-entry-duration');
    expect(duration).toHaveTextContent(/1h 30m/i);

    const endInput = screen.getByLabelText(/end time/i) as HTMLInputElement;
    fireEvent.change(endInput, { target: { value: '11:00' } });

    await waitFor(() => {
      expect(screen.getByTestId('edit-entry-duration')).toHaveTextContent(/^2h$/);
    });
  });

  it('sends a PATCH body containing only the changed fields', async () => {
    updateEntryMock.mockResolvedValue(buildCompletedEntry());

    renderModal(buildCompletedEntry());
    const desc = await screen.findByLabelText(/description/i);
    fireEvent.change(desc, { target: { value: 'Only desc changes' } });

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(updateEntryMock).toHaveBeenCalledTimes(1));
    const [, body] = updateEntryMock.mock.calls[0];
    expect(body).toEqual({ description: 'Only desc changes' });
    expect(body).not.toHaveProperty('start_time');
    expect(body).not.toHaveProperty('end_time');
    expect(body).not.toHaveProperty('project_id');
    expect(body).not.toHaveProperty('task_id');
  });
});
