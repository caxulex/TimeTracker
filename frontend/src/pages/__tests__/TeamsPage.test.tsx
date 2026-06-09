import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TeamsPage } from '../TeamsPage';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockAdmin = {
  id: 1,
  name: 'Admin',
  email: 'admin@example.com',
  role: 'super_admin' as const,
  is_active: true,
  company_id: 1,
  created_at: '2026-01-01T00:00:00Z',
};

vi.mock('../../stores/authStore', () => ({
  useAuthStore: () => ({ user: mockAdmin }),
}));

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: mockAdmin, isAuthenticated: true }),
}));

const notifySuccess = vi.fn();
const notifyError = vi.fn();

vi.mock('../../hooks/useStaffNotifications', () => ({
  useStaffNotifications: () => ({
    notifySuccess,
    notifyError,
  }),
}));

vi.mock('../../hooks/useDebounce', () => ({
  useDebounce: vi.fn((value: unknown) => value),
}));

const teamsGetAll = vi.fn();
const teamsGetById = vi.fn();
const teamsGetProjects = vi.fn();
const usersGetAll = vi.fn();
const projectsGetAll = vi.fn();
const addTeamToProject = vi.fn();
const removeTeamFromProject = vi.fn();

vi.mock('../../api/client', () => ({
  teamsApi: {
    getAll: (...args: unknown[]) => teamsGetAll(...args),
    getById: (...args: unknown[]) => teamsGetById(...args),
    getProjects: (...args: unknown[]) => teamsGetProjects(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
    restore: vi.fn(),
    listDeleted: vi.fn(),
  },
  usersApi: {
    getAll: (...args: unknown[]) => usersGetAll(...args),
  },
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    restore: vi.fn(),
    addTeam: (...args: unknown[]) => addTeamToProject(...args),
    removeTeam: (...args: unknown[]) => removeTeamFromProject(...args),
    listTeams: vi.fn(),
  },
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TeamsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const mkTeam = (id: number, overrides: Record<string, unknown> = {}) => ({
  id,
  name: `Team ${id}`,
  owner_id: 1,
  member_count: 2,
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

const allProjects = [
  { id: 11, name: 'Alpha Project', color: '#f97316', is_archived: false, primary_team_id: 1, primary_team_name: 'Team 1', association_type: 'primary' as const },
  { id: 12, name: 'Beta Project', color: '#10b981', is_archived: false, primary_team_id: 2, primary_team_name: 'Other Team', association_type: 'additional' as const },
  { id: 13, name: 'Gamma Project', color: '#3b82f6', is_archived: false, primary_team_id: 2, primary_team_name: 'Other Team', association_type: 'additional' as const },
];

let teamProjects = [allProjects[0], allProjects[1]];

describe('TeamsPage - projects section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();
    teamProjects = [allProjects[0], allProjects[1]];

    teamsGetAll.mockResolvedValue({
      items: [mkTeam(1)],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });

    teamsGetById.mockResolvedValue({
      ...mkTeam(1),
      members: [
        {
          user_id: 1,
          team_id: 1,
          role: 'owner',
          joined_at: '2026-01-01T00:00:00Z',
          user: {
            id: 1,
            email: 'admin@example.com',
            name: 'Admin',
            role: 'super_admin',
            is_active: true,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
      ],
    });

    teamsGetProjects.mockImplementation(async () => teamProjects);
    usersGetAll.mockResolvedValue({ items: [], total: 0, page: 1, size: 20, pages: 1 });

    projectsGetAll.mockImplementation(async (filters?: { search?: string }) => {
      const search = (filters?.search ?? '').toLowerCase();
      const items = allProjects.filter(
        (project) => project.name.toLowerCase().includes(search) && !teamProjects.some((assoc) => assoc.id === project.id)
      );
      return { items, total: items.length, page: 1, size: 100, pages: 1 };
    });

    addTeamToProject.mockImplementation(async ({ projectId }: { projectId: number }) => {
      const project = allProjects.find((item) => item.id === projectId);
      if (project && !teamProjects.some((assoc) => assoc.id === project.id)) {
        teamProjects = [...teamProjects, project];
      }
      return { message: 'Team associated with project' };
    });

    removeTeamFromProject.mockImplementation(async ({ projectId }: { projectId: number }) => {
      teamProjects = teamProjects.filter((project) => project.id !== projectId);
    });
  });

  it('renders the projects section, info banner, and primary-team label', async () => {
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await userEvent.setup().click(teamCard);

    await screen.findByText('Projects (2)');
    expect(screen.getByText('Changes here affect all team members, not just you.')).toBeInTheDocument();
    expect(screen.getByText('Alpha Project')).toBeInTheDocument();
    expect(screen.getByText('Beta Project')).toBeInTheDocument();
    expect(screen.getByText('Primary: Other Team')).toBeInTheDocument();
  });

  it('shows the empty state when a team has no projects', async () => {
    teamProjects = [];
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await userEvent.setup().click(teamCard);

    await screen.findByText('No projects yet. Click + Add Project to get started.');
  });

  it('supports searching, selecting, confirming, and immediately showing an added project', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByText('Projects (2)');

    await user.click(screen.getByRole('button', { name: '+ Add Project' }));
    const search = screen.getByPlaceholderText('Search projects...');
    await user.type(search, 'Gamma');

    await screen.findByRole('button', { name: 'Gamma Project' });
    await user.click(screen.getByRole('button', { name: 'Gamma Project' }));
    const addDialog = await screen.findByRole('dialog', { name: /Add Project to Team 1/i });
    expect(addDialog.textContent).toContain('Gamma Project');

    await user.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => {
      expect(addTeamToProject).toHaveBeenCalled();
    });
    expect(await screen.findByRole('heading', { name: 'Projects (3)' })).toBeInTheDocument();
    expect(screen.getByText('Gamma Project')).toBeInTheDocument();
  });

  it('supports removing a project with confirmation and updates the list', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByText('Projects (2)');

    const row = await screen.findByTestId('team-project-row-12');
    await user.click(row.querySelector('[data-testid="project-kebab-button"]') as HTMLElement);
    await user.click(await screen.findByTestId('project-kebab-action-remove-team'));

    const removeDialog = await screen.findByRole('dialog', { name: /Remove project from team\?/i });
    expect(removeDialog.textContent).toContain('Beta Project');

    await user.click(screen.getByRole('button', { name: 'Remove' }));

    await waitFor(() => {
      expect(removeTeamFromProject).toHaveBeenCalled();
    });
    expect(await screen.findByRole('heading', { name: 'Projects (1)' })).toBeInTheDocument();
    expect(screen.queryByText('Beta Project')).not.toBeInTheDocument();
  });

  it('clicking project name navigates to /projects?edit={id}', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    await user.click(screen.getByTestId('team-project-link-11'));

    expect(mockNavigate).toHaveBeenCalledWith('/projects?edit=11');
  });

  it('kebab menu shows Remove from team as most prominent action', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    const row = await screen.findByTestId('team-project-row-12');
    await user.click(row.querySelector('[data-testid="project-kebab-button"]') as HTMLElement);

    const menu = await screen.findByTestId('project-kebab-menu');
    const buttons = menu.querySelectorAll('button');
    expect(buttons[0].textContent).toContain('Remove from team');
    expect(await screen.findByTestId('project-kebab-action-remove-team')).toHaveClass('font-semibold');
  });

  it('Remove from team kebab action calls the remove handler (no nav)', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    const row = await screen.findByTestId('team-project-row-12');
    await user.click(row.querySelector('[data-testid="project-kebab-button"]') as HTMLElement);
    await user.click(await screen.findByTestId('project-kebab-action-remove-team'));

    expect(await screen.findByRole('dialog', { name: /Remove project from team\?/i })).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('Edit kebab action navigates to /projects?edit={id}', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    const row = await screen.findByTestId('team-project-row-12');
    await user.click(row.querySelector('[data-testid="project-kebab-button"]') as HTMLElement);
    await user.click(await screen.findByTestId('project-kebab-action-edit'));

    expect(mockNavigate).toHaveBeenCalledWith('/projects?edit=12');
  });

  it('Delete kebab action navigates to /projects?delete={id}', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    const row = await screen.findByTestId('team-project-row-12');
    await user.click(row.querySelector('[data-testid="project-kebab-button"]') as HTMLElement);
    await user.click(await screen.findByTestId('project-kebab-action-delete'));

    expect(mockNavigate).toHaveBeenCalledWith('/projects?delete=12');
  });

  it('filters team projects by name (case-insensitive)', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    const searchInput = screen.getByTestId('team-projects-search-input');
    await user.type(searchInput, 'alpha');

    expect(await screen.findByText('Alpha Project')).toBeInTheDocument();
    expect(screen.queryByText('Beta Project')).not.toBeInTheDocument();
  });

  it('shows N of M indicator when filter is active', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    await user.type(screen.getByTestId('team-projects-search-input'), 'alpha');

    expect(await screen.findByRole('heading', { name: 'Projects (1 of 2)' })).toBeInTheDocument();
  });

  it('shows empty state when filter yields no matches', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    await user.type(screen.getByTestId('team-projects-search-input'), 'zzz');

    expect(await screen.findByText('No projects match')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Projects (0 of 2)' })).toBeInTheDocument();
  });

  it('clearing the filter shows all projects again', async () => {
    const user = userEvent.setup();
    renderPage();

    const teamCard = await screen.findByText('Team 1');
    await user.click(teamCard);
    await screen.findByRole('heading', { name: 'Projects (2)' });

    const searchInput = screen.getByTestId('team-projects-search-input');
    await user.type(searchInput, 'alpha');
    expect(await screen.findByRole('heading', { name: 'Projects (1 of 2)' })).toBeInTheDocument();

    await user.clear(searchInput);

    expect(await screen.findByRole('heading', { name: 'Projects (2)' })).toBeInTheDocument();
    expect(screen.getByText('Alpha Project')).toBeInTheDocument();
    expect(screen.getByText('Beta Project')).toBeInTheDocument();
  });
});