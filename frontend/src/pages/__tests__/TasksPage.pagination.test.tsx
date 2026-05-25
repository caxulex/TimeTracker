// ============================================
// TIME TRACKER - TASKS PAGE PAGINATION TESTS
// Covers the useInfiniteQuery refactor + ProjectSelect (clearable)
// filter introduced in feat/tasks-page-pagination:
//   - initial fetch uses page_size=50,
//   - "Showing X of Y tasks" indicator renders,
//   - Load More advances pages and disappears when done,
//   - changing project / status filter resets to page 1,
//   - the project filter renders ProjectSelect with the
//     "All projects" clear option.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TasksPage } from '../TasksPage';

const tasksGetAll = vi.fn();
const projectsGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  tasksApi: {
    getAll: (...args: unknown[]) => tasksGetAll(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
  },
}));

vi.mock('../../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: false }),
}));

vi.mock('../../components/ai', () => ({
  TaskEstimationCard: () => null,
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const mkTask = (id: number, overrides: Record<string, unknown> = {}) => ({
  id,
  name: `Task ${id}`,
  description: '',
  status: 'TODO',
  project_id: 1,
  team_id: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  ...overrides,
});

const projectsList = [
  {
    id: 1,
    name: 'Alpha',
    description: '',
    color: '#3B82F6',
    team_id: 1,
    team_name: 'Team',
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    task_count: 0,
  },
  {
    id: 2,
    name: 'Bravo',
    description: '',
    color: '#FF0000',
    team_id: 1,
    team_name: 'Team',
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    task_count: 0,
  },
];

describe('TasksPage - pagination & filters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectsGetAll.mockResolvedValue({
      items: projectsList,
      total: projectsList.length,
      page: 1,
      page_size: 100,
      pages: 1,
    });
  });

  it('initial fetch uses page_size=50 and renders "Showing X of N tasks"', async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => mkTask(i + 1));
    tasksGetAll.mockResolvedValueOnce({
      items: page1,
      total: 137,
      page: 1,
      page_size: 50,
      pages: 3,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('tasks-count').textContent).toMatch(
        /Showing 50 of 137 tasks/
      );
    });
    expect(tasksGetAll).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 50 })
    );
    expect(screen.getByTestId('tasks-load-more')).toBeInTheDocument();
  });

  it('"Load More" advances to the next page; indicator updates; button disappears at end', async () => {
    const user = userEvent.setup();
    const page1 = Array.from({ length: 50 }, (_, i) => mkTask(i + 1));
    const page2 = Array.from({ length: 30 }, (_, i) => mkTask(i + 51));
    tasksGetAll
      .mockResolvedValueOnce({
        items: page1,
        total: 80,
        page: 1,
        page_size: 50,
        pages: 2,
      })
      .mockResolvedValueOnce({
        items: page2,
        total: 80,
        page: 2,
        page_size: 50,
        pages: 2,
      });
    renderPage();
    await screen.findByTestId('tasks-load-more');

    await user.click(screen.getByTestId('tasks-load-more'));

    await waitFor(() => {
      expect(tasksGetAll).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2, page_size: 50 })
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('tasks-count').textContent).toMatch(
        /Showing 80 of 80 tasks/
      );
    });
    expect(screen.queryByTestId('tasks-load-more')).not.toBeInTheDocument();
  });

  it('Load More is absent when the first page already contains everything', async () => {
    tasksGetAll.mockResolvedValueOnce({
      items: [mkTask(1), mkTask(2)],
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('tasks-count').textContent).toMatch(
        /Showing 2 of 2 tasks/
      );
    });
    expect(screen.queryByTestId('tasks-load-more')).not.toBeInTheDocument();
  });

  it('changing the status filter resets to page 1 (refetches with new status)', async () => {
    const user = userEvent.setup();
    tasksGetAll.mockResolvedValue({
      items: [mkTask(1)],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await screen.findByTestId('tasks-count');
    tasksGetAll.mockClear();

    const statusSelect = screen.getByLabelText(/filter by status/i);
    await user.selectOptions(statusSelect, 'IN_PROGRESS');

    await waitFor(() => {
      expect(tasksGetAll).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
          page_size: 50,
          status: 'IN_PROGRESS',
        })
      );
    });
  });

  it('changing the project filter resets to page 1 (refetches with new project_id)', async () => {
    const user = userEvent.setup();
    tasksGetAll.mockResolvedValue({
      items: [mkTask(1)],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await screen.findByTestId('tasks-count');
    tasksGetAll.mockClear();

    const projectInput = screen.getByLabelText(/filter by project/i);
    await user.click(projectInput);
    // Click the "Bravo" option (id 2).
    await waitFor(() =>
      expect(screen.getByTestId('project-select-option-2')).toBeInTheDocument()
    );
    // ProjectSelect commits on mousedown.
    const opt = screen.getByTestId('project-select-option-2');
    opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));

    await waitFor(() => {
      expect(tasksGetAll).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
          page_size: 50,
          project_id: 2,
        })
      );
    });
  });

  it('project filter exposes the ProjectSelect "All projects" clear option', async () => {
    tasksGetAll.mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    const user = userEvent.setup();
    renderPage();
    const projectInput = await screen.findByLabelText(/filter by project/i);
    await user.click(projectInput);
    const clear = await screen.findByTestId('project-select-clear');
    expect(clear).toBeInTheDocument();
    expect(clear.textContent).toMatch(/All projects/i);
  });

  it('clicking "All projects" while a project filter is active drops project_id from the next fetch', async () => {
    const user = userEvent.setup();
    tasksGetAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await screen.findByTestId('tasks-count');

    // Apply a project filter first.
    const projectInput = screen.getByLabelText(/filter by project/i);
    await user.click(projectInput);
    await waitFor(() =>
      expect(screen.getByTestId('project-select-option-1')).toBeInTheDocument()
    );
    screen
      .getByTestId('project-select-option-1')
      .dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));

    await waitFor(() => {
      expect(tasksGetAll).toHaveBeenCalledWith(
        expect.objectContaining({ project_id: 1 })
      );
    });
    tasksGetAll.mockClear();

    // Now clear the filter via the "All projects" option.
    await user.click(screen.getByLabelText(/filter by project/i));
    screen
      .getByTestId('project-select-clear')
      .dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));

    await waitFor(() => {
      const lastCall = tasksGetAll.mock.calls[tasksGetAll.mock.calls.length - 1];
      expect(lastCall[0].project_id).toBeUndefined();
      expect(lastCall[0].page).toBe(1);
      expect(lastCall[0].page_size).toBe(50);
    });
  });
});
