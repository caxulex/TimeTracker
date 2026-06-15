// ============================================
// TIME TRACKER - PROJECTS PAGE AI HEALTH PILL TESTS
// Covers the wiring of the "AI Health" pill on project cards:
//   - Pill is a focusable button when feature is enabled
//   - Clicking the pill opens the health modal (not inline panel)
//   - Modal renders ProjectHealthCard for the correct project
//   - Closing the modal removes it from the DOM
//   - Pill is absent when feature is disabled
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectsPage } from '../ProjectsPage';

// ---- module mocks ---- //

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'User', email: 'u@example.com', role: 'regular_user' },
    isAuthenticated: true,
  }),
}));

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({ addNotification: vi.fn() }),
}));

// Feature flag ON for this file — the whole point of these tests.
vi.mock('../../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: true }),
}));

// Lightweight test double that captures which project it was called for.
vi.mock('../../components/ai/ProjectHealthCard', () => ({
  default: ({ projectId, projectName }: { projectId: number; projectName?: string }) => (
    <div
      data-testid="mock-project-health-card"
      data-project-id={String(projectId)}
    >
      {projectName ?? `project-${projectId}`}
    </div>
  ),
}));

const projectsGetAll = vi.fn();
const teamsGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
    getSimilar: vi.fn().mockResolvedValue({ matches: [] }),
    create: vi.fn(),
    update: vi.fn(),
    archive: vi.fn(),
    restore: vi.fn(),
    delete: vi.fn(),
    deletePreview: vi.fn(),
    merge: vi.fn(),
    mergePreview: vi.fn(),
    addTeam: vi.fn(),
    removeTeam: vi.fn(),
    listTeams: vi.fn(),
  },
  teamsApi: {
    getAll: (...args: unknown[]) => teamsGetAll(...args),
  },
}));

// ---- helpers ---- //

const makeProject = (id: number, name: string) => ({
  id,
  name,
  description: 'desc',
  color: '#3B82F6',
  team_id: 1,
  team_name: 'Team',
  team_associations: [{ team_id: 1, team_name: 'Team', is_primary: true, added_by_name: null, added_at: '2026-01-01T00:00:00Z' }],
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  task_count: 0,
  budget_amount: null,
  budget_currency: null,
  deadline: null,
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProjectsPage AI Health pill', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    teamsGetAll.mockResolvedValue({ items: [{ id: 1, name: 'Team' }], total: 1, page: 1, page_size: 20, pages: 1 });
    projectsGetAll.mockResolvedValue({
      items: [makeProject(1, 'Apollo'), makeProject(2, 'Orion')],
      total: 2, page: 1, page_size: 50, pages: 1,
    });
  });

  it('renders the AI Health pill as a focusable button when feature is enabled', async () => {
    renderPage();

    const card = await screen.findByTestId('project-card-1');
    const pill = within(card).getByTitle('View AI health analysis');
    expect(pill.tagName).toBe('BUTTON');
    expect(pill).toHaveTextContent('AI Health');
  });

  it('clicking the pill opens a modal with ProjectHealthCard for the correct project', async () => {
    const user = userEvent.setup();
    renderPage();

    const card = await screen.findByTestId('project-card-1');
    await user.click(within(card).getByTitle('View AI health analysis'));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByTestId('mock-project-health-card')).toHaveAttribute('data-project-id', '1');
    expect(within(dialog).getByText('Apollo')).toBeInTheDocument();
  });

  it('each pill opens health modal for its own project', async () => {
    const user = userEvent.setup();
    renderPage();

    // Click pill on project 2
    const card2 = await screen.findByTestId('project-card-2');
    await user.click(within(card2).getByTitle('View AI health analysis'));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByTestId('mock-project-health-card')).toHaveAttribute('data-project-id', '2');
    expect(within(dialog).getByText('Orion')).toBeInTheDocument();
  });

  it('closing the modal removes it from the DOM', async () => {
    const user = userEvent.setup();
    renderPage();

    const card = await screen.findByTestId('project-card-1');
    await user.click(within(card).getByTitle('View AI health analysis'));
    await screen.findByRole('dialog');

    await user.click(screen.getByRole('button', { name: /close/i }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
