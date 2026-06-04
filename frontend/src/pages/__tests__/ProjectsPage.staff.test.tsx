// ============================================
// TIME TRACKER - PROJECTS PAGE STAFF VISIBILITY TEST
// --------------------------------------------
// Verifies the 2026-05-14 product decision extended to projects:
// the "New Project" button and the create modal are visible to any
// authenticated team member. Edit / archive / delete affordances on
// existing project cards stay admin-only.
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

type Role = 'super_admin' | 'admin' | 'regular_user' | null;

function setUser(role: Role) {
  mockedAuth.mockReturnValue({
    user: role
      ? { id: 1, email: 'u@example.com', name: 'U', role }
      : null,
    isAuthenticated: !!role,
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

describe('ProjectsPage - staff project creation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // teamsApi.getAll is already server-side-scoped to the user's
    // memberships for non-admins; the UI just renders what it gets.
    teamsGetAll.mockResolvedValue({
      items: [{ id: 1, name: 'My Team' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    projectsGetAll.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Existing Project',
          description: '',
          color: '#3B82F6',
          team_id: 1,
          team_associations: [
            {
              team_id: 1,
              team_name: 'My Team',
              is_primary: true,
              added_by_name: null,
              added_at: '2026-01-01T00:00:00Z',
            },
          ],
          is_archived: false,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    projectsAddTeam.mockResolvedValue({ message: 'ok' });
  });

  it('renders the "New Project" button for a non-admin team member', async () => {
    setUser('regular_user');
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /new project/i })
      ).toBeInTheDocument();
    });
  });

  it('hides the "New Project" button when no user is authenticated', async () => {
    setUser(null);
    renderPage();
    // Wait for the project list to render so we know the page settled.
    await screen.findByText('Existing Project');
    expect(
      screen.queryByRole('button', { name: /new project/i })
    ).not.toBeInTheDocument();
  });

  it('keeps edit / archive / delete icons hidden for non-admin users', async () => {
    setUser('regular_user');
    renderPage();
    await screen.findByText('Existing Project');
    expect(
      screen.queryByRole('button', { name: /edit project/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /archive project/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /delete project/i })
    ).not.toBeInTheDocument();
  });

  it('shows only teams the (non-admin) user is a member of in the team selector', async () => {
    setUser('regular_user');
    renderPage();
    const newProjectBtn = await screen.findByRole('button', {
      name: /new project/i,
    });
    await userEvent.click(newProjectBtn);

    // TeamSelect is a combobox-pattern typeahead: open it, then
    // inspect the listbox. teamsApi.getAll is already scoped to the
    // user's memberships server-side, so we expect exactly one option.
    const teamCombobox = await screen.findByRole('combobox', { name: /team/i });
    await userEvent.click(teamCombobox);
    const listbox = await screen.findByTestId('team-select-listbox');
    const options = listbox.querySelectorAll('[role="option"]');
    expect(options).toHaveLength(1);
    expect(options[0].textContent).toContain('My Team');
  });

  it('hides budget_amount and deadline fields in the modal for non-admin users', async () => {
    setUser('regular_user');
    renderPage();
    const newProjectBtn = await screen.findByRole('button', {
      name: /new project/i,
    });
    await userEvent.click(newProjectBtn);

    await screen.findByLabelText(/project name/i);
    expect(screen.queryByText(/budget \(usd\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^deadline$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/budget settings/i)).not.toBeInTheDocument();
  });

  it('shows budget_amount and deadline fields in the modal for admin users', async () => {
    setUser('admin');
    renderPage();
    const newProjectBtn = await screen.findByRole('button', {
      name: /new project/i,
    });
    await userEvent.click(newProjectBtn);

    expect(await screen.findByText(/budget settings/i)).toBeInTheDocument();
    expect(screen.getByText(/budget \(usd\)/i)).toBeInTheDocument();
    expect(screen.getByText(/^deadline$/i)).toBeInTheDocument();
  });

  it('shows add-to-team button when user has one team not yet associated', async () => {
    projectsGetAll.mockResolvedValueOnce({
      items: [
        {
          id: 1,
          name: 'Existing Project',
          description: '',
          color: '#3B82F6',
          team_id: 99,
          team_associations: [
            {
              team_id: 99,
              team_name: 'Engineering',
              is_primary: true,
              added_by_name: null,
              added_at: '2026-01-01T00:00:00Z',
            },
          ],
          is_archived: false,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    teamsGetAll.mockResolvedValueOnce({
      items: [{ id: 1, name: 'My Team' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    setUser('regular_user');
    renderPage();

    expect(await screen.findByRole('button', { name: /add to my team/i })).toBeInTheDocument();
  });

  it('renders "Not on your team" badge for projects without user team association', async () => {
    projectsGetAll.mockResolvedValueOnce({
      items: [
        {
          id: 1,
          name: 'Existing Project',
          description: '',
          color: '#3B82F6',
          team_id: 99,
          team_associations: [
            {
              team_id: 99,
              team_name: 'Engineering',
              is_primary: true,
              added_by_name: null,
              added_at: '2026-01-01T00:00:00Z',
            },
          ],
          is_archived: false,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    setUser('regular_user');
    renderPage();

    const badge = await screen.findByText(/not on your team/i);
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute(
      'title',
      "You can see this project but can't track time. Click 'Add to my team' to start working on it."
    );
  });

  it('does not render "Not on your team" badge when project is already associated', async () => {
    setUser('regular_user');
    renderPage();

    await screen.findByText('Existing Project');
    expect(screen.queryByText(/not on your team/i)).not.toBeInTheDocument();
  });

  it('shows mixed associated and non-associated projects returned by the API', async () => {
    projectsGetAll.mockResolvedValueOnce({
      items: [
        {
          id: 1,
          name: 'Associated Project',
          description: '',
          color: '#3B82F6',
          team_id: 1,
          team_associations: [
            {
              team_id: 1,
              team_name: 'My Team',
              is_primary: true,
              added_by_name: null,
              added_at: '2026-01-01T00:00:00Z',
            },
          ],
          is_archived: false,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: null,
        },
        {
          id: 2,
          name: 'Discovery Project',
          description: '',
          color: '#10B981',
          team_id: 99,
          team_associations: [
            {
              team_id: 99,
              team_name: 'Other Team',
              is_primary: true,
              added_by_name: null,
              added_at: '2026-01-01T00:00:00Z',
            },
          ],
          is_archived: false,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: null,
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    setUser('regular_user');
    renderPage();

    expect(await screen.findByText('Associated Project')).toBeInTheDocument();
    expect(await screen.findByText('Discovery Project')).toBeInTheDocument();
    expect(await screen.findByText(/not on your team/i)).toBeInTheDocument();
    expect(await screen.findByTestId('project-add-team-2')).toBeInTheDocument();
    expect(projectsListTeams).not.toHaveBeenCalled();
  });

  it('hides add-to-team button when user single team is already associated', async () => {
    setUser('regular_user');
    renderPage();
    await screen.findByText('Existing Project');
    expect(screen.queryByRole('button', { name: /add to my team/i })).not.toBeInTheDocument();
  });

  it('renders team dropdown for users with multiple teams', async () => {
    teamsGetAll.mockResolvedValueOnce({
      items: [
        { id: 1, name: 'My Team' },
        { id: 2, name: 'Admin Team' },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    setUser('regular_user');
    renderPage();

    expect(await screen.findByRole('button', { name: /add to team/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /select team for existing project/i })).toBeInTheDocument();
  });
});
