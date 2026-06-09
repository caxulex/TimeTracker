import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { within } from '@testing-library/react';
import { TasksPage } from '../TasksPage';

const tasksGetAll = vi.fn();
const tasksCreate = vi.fn();
const tasksUpdate = vi.fn();
const projectsGetAll = vi.fn();
const teamsGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  tasksApi: {
    getAll: (...args: unknown[]) => tasksGetAll(...args),
    create: (...args: unknown[]) => tasksCreate(...args),
    update: (...args: unknown[]) => tasksUpdate(...args),
    delete: vi.fn(),
  },
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
  },
  teamsApi: {
    getAll: (...args: unknown[]) => teamsGetAll(...args),
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

const project = {
  id: 1,
  name: 'Visible Project',
  description: '',
  color: '#3B82F6',
  team_id: 1,
  team_name: 'Team',
  team_associations: [{ team_id: 1, team_name: 'Team', is_primary: true }],
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  task_count: 1,
};

const teams = [
  { id: 1, name: 'Billing', color: '#10B981' },
  { id: 2, name: 'Urgent', color: '#DC2626' },
];

const existingTask = {
  id: 11,
  name: 'Close the books',
  description: 'Month-end cleanup',
  status: 'TODO',
  project_id: 1,
  team_id: 1,
  teams: [teams[0]],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
};

describe('TasksPage - team integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    tasksGetAll.mockResolvedValue({
      items: [existingTask],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    tasksCreate.mockResolvedValue({ id: 20 });
    tasksUpdate.mockResolvedValue({ ...existingTask, teams });
    projectsGetAll.mockResolvedValue({
      items: [project],
      total: 1,
      page: 1,
      page_size: 100,
      pages: 1,
    });
    teamsGetAll.mockResolvedValue({
      items: teams,
      total: teams.length,
      page: 1,
      page_size: 100,
      pages: 1,
    });
  });

  it('renders team chips on task cards and preloads teams in the edit modal', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('Close the books')).toBeInTheDocument();
    expect(screen.getAllByText('Billing').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: /edit task close the books/i }));

    expect(await screen.findByRole('heading', { name: /edit task/i })).toBeInTheDocument();
    expect(screen.getByText('Teams')).toBeInTheDocument();
    expect(screen.getByTestId('team-multiselect')).toBeInTheDocument();
    expect(within(screen.getByTestId('selected-teams')).getByText('Billing')).toBeInTheDocument();
  });

  it('submits selected team ids from the task modal', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /new task/i }));
    await user.type(await screen.findByLabelText(/task name/i), 'Prepare invoices');

    const teamSelect = await screen.findByLabelText(/add team/i);
    await user.selectOptions(teamSelect, '1');
    await user.selectOptions(teamSelect, '2');

    await user.click(screen.getByRole('button', { name: /create task/i }));

    await waitFor(() => {
      expect(tasksCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Prepare invoices',
          project_id: 1,
          team_ids: [1, 2],
        })
      );
    });
  });

  it('persists edited team ids in the update payload', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /edit task close the books/i }));

    const teamSelect = await screen.findByLabelText(/add team/i);
    await user.selectOptions(teamSelect, '2');

    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(tasksUpdate).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          team_ids: [1, 2],
        })
      );
    });
  });
});
