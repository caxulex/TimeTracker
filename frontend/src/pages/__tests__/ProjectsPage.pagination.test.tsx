// ============================================
// TIME TRACKER - PROJECTS PAGE PAGINATION TESTS
// Covers the useInfiniteQuery refactor introduced in
// fix/project-selectors-typeahead-and-pagination:
//   - "Showing X of Y projects" indicator
//   - "Load More" button advances to the next page
//   - "Show Archived" toggle filters the loaded pages
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectsPage } from '../ProjectsPage';
import { useAuthStore } from '../../stores/authStore';

vi.mock('../../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({ addNotification: vi.fn() }),
}));

vi.mock('../../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: false }),
}));

vi.mock('../../components/ai/ProjectHealthCard', () => ({
  default: () => null,
}));

const projectsGetAll = vi.fn();
const projectsListTeams = vi.fn();
const projectsAddTeam = vi.fn();
const teamsGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
    listTeams: (...args: unknown[]) => projectsListTeams(...args),
    addTeam: (...args: unknown[]) => projectsAddTeam(...args),
    create: vi.fn(),
    update: vi.fn(),
    restore: vi.fn(),
    delete: vi.fn(),
    removeTeam: vi.fn(),
  },
  teamsApi: {
    getAll: (...args: unknown[]) => teamsGetAll(...args),
  },
}));

const mockedAuth = useAuthStore as unknown as ReturnType<typeof vi.fn>;

function setAdmin() {
  mockedAuth.mockReturnValue({
    user: { id: 1, email: 'a@example.com', name: 'A', role: 'admin' },
    isAuthenticated: true,
  });
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const mkProject = (id: number, overrides: Record<string, unknown> = {}) => ({
  id,
  name: `Project ${id}`,
  description: '',
  color: '#3B82F6',
  team_id: 1,
  team_name: 'Team',
  team_associations: [
    {
      team_id: 1,
      team_name: 'Team',
      is_primary: true,
      added_by_name: null,
      added_at: '2026-01-01T00:00:00Z',
    },
  ],
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  task_count: 0,
  ...overrides,
});

describe('ProjectsPage - pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    teamsGetAll.mockResolvedValue({
      items: [{ id: 1, name: 'Team' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    projectsListTeams.mockResolvedValue([
      {
        team_id: 1,
        team_name: 'Team',
        is_primary: true,
        added_by_name: null,
        added_at: '2026-01-01T00:00:00Z',
      },
    ]);
    projectsAddTeam.mockResolvedValue({ message: 'ok' });
    setAdmin();
  });

  it('renders the "Showing X of Y projects" indicator', async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => mkProject(i + 1));
    projectsGetAll.mockResolvedValueOnce({
      items: page1,
      total: 97,
      page: 1,
      page_size: 50,
      pages: 2,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('projects-count').textContent).toMatch(
        /Showing 50 of 97 projects/
      );
    });
    expect(projectsListTeams).not.toHaveBeenCalled();
    expect(screen.getByTestId('projects-load-more')).toBeInTheDocument();
  });

  it('"Load More" advances to the next page', async () => {
    const user = userEvent.setup();
    const page1 = Array.from({ length: 50 }, (_, i) => mkProject(i + 1));
    const page2 = Array.from({ length: 47 }, (_, i) => mkProject(i + 51));
    projectsGetAll
      .mockResolvedValueOnce({
        items: page1,
        total: 97,
        page: 1,
        page_size: 50,
        pages: 2,
      })
      .mockResolvedValueOnce({
        items: page2,
        total: 97,
        page: 2,
        page_size: 50,
        pages: 2,
      });
    renderPage();
    await screen.findByTestId('projects-load-more');
    expect(projectsGetAll).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 50, include_archived: true })
    );

    await user.click(screen.getByTestId('projects-load-more'));

    await waitFor(() => {
      expect(projectsGetAll).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2, page_size: 50 })
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('projects-count').textContent).toMatch(
        /Showing 97 of 97 projects/
      );
    });
    // Once all pages are loaded the Load More button goes away.
    expect(screen.queryByTestId('projects-load-more')).not.toBeInTheDocument();
  });

  it('"Show Archived" toggle filters the loaded pages client-side', async () => {
    const user = userEvent.setup();
    const items = [
      mkProject(1, { name: 'Active One', is_archived: false }),
      mkProject(2, { name: 'Archived One', is_archived: true }),
    ];
    projectsGetAll.mockResolvedValue({
      items,
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();

    await screen.findByText('Active One');
    expect(screen.queryByText('Archived One')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /show archived/i }));

    await screen.findByText('Archived One');
    expect(screen.queryByText('Active One')).not.toBeInTheDocument();
  });

  it('fires API call with search param after 250ms debounce', async () => {
    const user = userEvent.setup();

    projectsGetAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 1,
    });

    renderPage();
    expect(await screen.findByTestId('projects-search-input')).toBeInTheDocument();

    await user.type(screen.getByTestId('projects-search-input'), 'alpha');

    // The debounced request should not fire immediately.
    expect(projectsGetAll).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(projectsGetAll).toHaveBeenCalledWith(
        expect.objectContaining({
          include_archived: true,
          page: 1,
          page_size: 50,
          search: 'alpha',
        })
      );
    }, { timeout: 2000 });
  });

  it('rapid typing only fires one debounced search request', async () => {
    const user = userEvent.setup();

    projectsGetAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 1,
    });

    renderPage();
    const searchInput = await screen.findByTestId('projects-search-input');

    await user.type(searchInput, 'project');

    await waitFor(() => {
      expect(projectsGetAll).toHaveBeenCalledTimes(2);
    }, { timeout: 2000 });
  });

  it('clearing search refetches without search param', async () => {
    const user = userEvent.setup();

    projectsGetAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 1,
    });

    renderPage();
    const searchInput = await screen.findByTestId('projects-search-input');

    await user.type(searchInput, 'alpha');
    await waitFor(() => {
      expect(projectsGetAll).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'alpha' })
      );
    }, { timeout: 2000 });

    const populatedInput = await screen.findByTestId('projects-search-input');
    expect(populatedInput).toHaveValue('alpha');
    await user.click(screen.getByTestId('projects-search-clear'));

    await waitFor(() => {
      expect(projectsGetAll).toHaveBeenLastCalledWith(
        expect.objectContaining({
          include_archived: true,
          page: 1,
          page_size: 50,
          search: undefined,
        })
      );
    }, { timeout: 2000 });
  });

  it('renders search-specific empty state when no projects match query', async () => {
    const user = userEvent.setup();

    projectsGetAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 1,
    });

    renderPage();
    const searchInput = await screen.findByTestId('projects-search-input');

    await user.type(searchInput, 'unknown');

    expect(await screen.findByText('No projects matching "unknown"', {}, { timeout: 2000 })).toBeInTheDocument();
  });

  it('"Show Archived" toggle still works alongside search', async () => {
    const user = userEvent.setup();

    projectsGetAll.mockImplementation((filters?: { search?: string }) => {
      if (filters?.search === 'one') {
        return Promise.resolve({
          items: [
            mkProject(1, { name: 'Active One', is_archived: false }),
            mkProject(2, { name: 'Archived One', is_archived: true }),
          ],
          total: 2,
          page: 1,
          page_size: 50,
          pages: 1,
        });
      }

      return Promise.resolve({
        items: [mkProject(10, { name: 'Starter', is_archived: false })],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      });
    });

    renderPage();

    const searchInput = await screen.findByTestId('projects-search-input');
    await user.type(searchInput, 'one');

  await screen.findByText('Active One', {}, { timeout: 2000 });
    expect(screen.queryByText('Archived One')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /show archived/i }));

    await screen.findByText('Archived One');
    expect(screen.queryByText('Active One')).not.toBeInTheDocument();
  });
});
