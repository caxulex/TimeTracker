// ============================================
// TIME TRACKER - TASK SELECT TESTS
// Covers the typeahead combobox introduced in
// feat/task-select-typeahead.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskSelect } from '../TaskSelect';
import type { Task } from '../../../types';

vi.mock('../../../api/client', () => ({
  tasksApi: {
    getAll: vi.fn(),
  },
}));

import { tasksApi } from '../../../api/client';

const makeTask = (overrides: Partial<Task>): Task => ({
  id: 1,
  project_id: 1,
  name: 'Task',
  description: null,
  status: 'TODO',
  created_at: new Date().toISOString(),
  basecamp_due_on: null,
  basecamp_todo_created_at: null,
  basecamp_todo_position: null,
  ...overrides,
} as Task);

const TASKS: Task[] = [
  makeTask({ id: 10, name: 'Design mockups' }),
  makeTask({ id: 11, name: 'Implement login' }),
  makeTask({ id: 12, name: 'Write docs' }),
  makeTask({ id: 13, name: 'Fix bug 42' }),
];

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
}

function renderSelect(
  props: Partial<React.ComponentProps<typeof TaskSelect>> = {},
  opts: { queryClient?: QueryClient } = {}
) {
  const onChange = vi.fn();
  const queryClient = opts.queryClient ?? makeClient();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <TaskSelect
        projectId={props.projectId === undefined ? 1 : props.projectId}
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        placeholder={props.placeholder ?? 'Select task'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange, queryClient };
}

describe('TaskSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tasksApi.getAll).mockResolvedValue({
      items: TASKS,
      total: TASKS.length,
      page: 1,
      size: 100,
      pages: 1,
    });
  });

  it('renders disabled with "Select project first" when projectId is null', () => {
    renderSelect({ projectId: null });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    expect(input).toBeDisabled();
    expect(input.placeholder).toMatch(/select project first/i);
  });

  it('renders disabled when projectId is undefined', () => {
    renderSelect({ projectId: undefined });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    expect(input).toBeDisabled();
  });

  it('does not fetch tasks when projectId is null', () => {
    renderSelect({ projectId: null });
    expect(tasksApi.getAll).not.toHaveBeenCalled();
  });

  it('renders the currently-selected task name', async () => {
    renderSelect({ value: 12 });
    await waitFor(() => {
      const input = screen.getByRole('combobox') as HTMLInputElement;
      expect(input.value).toBe('Write docs');
    });
  });

  it('opens the dropdown on focus and lists all tasks', async () => {
    renderSelect();
    await waitFor(() =>
      expect(tasksApi.getAll).toHaveBeenCalledWith({ project_id: 1, page_size: 100 })
    );
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => {
      expect(screen.getByTestId('task-select-option-10')).toBeInTheDocument();
    });
    expect(screen.getByTestId('task-select-option-11')).toBeInTheDocument();
    expect(screen.getByTestId('task-select-option-12')).toBeInTheDocument();
    expect(screen.getByTestId('task-select-option-13')).toBeInTheDocument();
  });

  it('filters options as the user types (case-insensitive substring)', async () => {
    const user = userEvent.setup();
    renderSelect();
    await waitFor(() =>
      expect(tasksApi.getAll).toHaveBeenCalled()
    );
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'desi');
    expect(screen.getByTestId('task-select-option-10')).toBeInTheDocument();
    expect(screen.queryByTestId('task-select-option-11')).not.toBeInTheDocument();
    expect(screen.queryByTestId('task-select-option-12')).not.toBeInTheDocument();
  });

  it('shows empty-state message when no tasks match the query', async () => {
    const user = userEvent.setup();
    renderSelect();
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'xyz');
    const empty = await screen.findByTestId('task-select-empty');
    expect(empty.textContent).toMatch(/xyz/);
    expect(empty.textContent).toMatch(/No tasks match/i);
  });

  it('shows "This project has no tasks yet" when the project has zero tasks', async () => {
    vi.mocked(tasksApi.getAll).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      size: 100,
      pages: 0,
    });
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => {
      expect(screen.getByTestId('task-select-empty-project')).toBeInTheDocument();
    });
  });

  it('calls onChange when an option is clicked', async () => {
    const { onChange } = renderSelect();
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    const option = await screen.findByTestId('task-select-option-12');
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(12, expect.objectContaining({ id: 12, name: 'Write docs' }));
  });

  it('keyboard: ArrowDown + Enter selects an option', async () => {
    const user = userEvent.setup();
    const { onChange } = renderSelect();
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    const input = screen.getByRole('combobox');
    await user.click(input);
    // Highlight starts at index 0. ArrowDown twice -> index 2 (Write docs).
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');
    expect(onChange).toHaveBeenCalledWith(12, expect.objectContaining({ id: 12, name: 'Write docs' }));
  });

  it('keyboard: Escape closes the panel', async () => {
    const user = userEvent.setup();
    renderSelect();
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    const input = screen.getByRole('combobox');
    await user.click(input);
    await screen.findByTestId('task-select-listbox');
    await user.keyboard('{Escape}');
    expect(screen.queryByTestId('task-select-listbox')).not.toBeInTheDocument();
  });

  it('click-outside closes the panel', async () => {
    renderSelect();
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await screen.findByTestId('task-select-listbox');
    fireEvent.mouseDown(document.body);
    await waitFor(() =>
      expect(screen.queryByTestId('task-select-listbox')).not.toBeInTheDocument()
    );
  });

  it('shows loading state while the query is in flight', async () => {
    vi.mocked(tasksApi.getAll).mockReturnValueOnce(new Promise(() => {}));
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => {
      expect(screen.getByTestId('task-select-loading')).toBeInTheDocument();
    });
  });

  it('fetches with project_id and page_size=100', async () => {
    renderSelect({ projectId: 7 });
    await waitFor(() => {
      expect(tasksApi.getAll).toHaveBeenCalledWith({
        project_id: 7,
        page_size: 100,
      });
    });
  });

  it('refetches with new project_id when prop changes', async () => {
    const queryClient = makeClient();
    const onChange = vi.fn();
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <TaskSelect projectId={1} value={null} onChange={onChange} />
      </QueryClientProvider>
    );
    await waitFor(() =>
      expect(tasksApi.getAll).toHaveBeenCalledWith({ project_id: 1, page_size: 100 })
    );

    rerender(
      <QueryClientProvider client={queryClient}>
        <TaskSelect projectId={2} value={null} onChange={onChange} />
      </QueryClientProvider>
    );
    await waitFor(() =>
      expect(tasksApi.getAll).toHaveBeenCalledWith({ project_id: 2, page_size: 100 })
    );
  });

  it('calls onChange(null) when projectId changes and a task was selected', async () => {
    const queryClient = makeClient();
    const onChange = vi.fn();
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <TaskSelect projectId={1} value={12} onChange={onChange} />
      </QueryClientProvider>
    );
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    // Initial mount must NOT fire onChange(null).
    expect(onChange).not.toHaveBeenCalled();

    rerender(
      <QueryClientProvider client={queryClient}>
        <TaskSelect projectId={2} value={12} onChange={onChange} />
      </QueryClientProvider>
    );
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(null, null));
  });

  it('does NOT fire onChange(null) on initial mount even when value is set', async () => {
    const onChange = vi.fn();
    renderSelect({ projectId: 1, value: 11, onChange });
    await waitFor(() => expect(tasksApi.getAll).toHaveBeenCalled());
    // Give effects time to run.
    await new Promise((r) => setTimeout(r, 0));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('renders Basecamp-disambiguated labels for duplicate task names', async () => {
    const md = (iso: string) =>
      new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    vi.mocked(tasksApi.getAll).mockResolvedValueOnce({
      items: [
        makeTask({ id: 1, name: 'Monthly Report', basecamp_due_on: '2026-01-04' }),
        makeTask({ id: 2, name: 'Monthly Report', basecamp_due_on: '2026-05-04' }),
        makeTask({ id: 3, name: 'Unique' }),
      ],
      total: 3,
      page: 1,
      size: 100,
      pages: 1,
    });
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    // Sorted DESC by due_on: option-2 (May) before option-1 (Jan).
    const option2 = await screen.findByTestId('task-select-option-2');
    const option1 = screen.getByTestId('task-select-option-1');
    expect(option2.textContent).toBe(`Monthly Report (Due ${md('2026-05-04')})`);
    expect(option1.textContent).toBe(`Monthly Report (Due ${md('2026-01-04')})`);
    // Unique name stays plain.
    expect(screen.getByTestId('task-select-option-3').textContent).toBe('Unique');
  });
});
