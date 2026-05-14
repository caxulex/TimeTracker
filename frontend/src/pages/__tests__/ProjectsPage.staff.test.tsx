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
const teamsGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
    create: vi.fn(),
    update: vi.fn(),
    restore: vi.fn(),
    delete: vi.fn(),
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

    const teamSelect = await screen.findByRole('combobox');
    // Only the placeholder + the single membership team should be
    // present — the backend already filters teamsApi.getAll(),
    // so the dropdown reflects that scoped list.
    const options = teamSelect.querySelectorAll('option');
    expect(options).toHaveLength(2);
    expect(options[1].textContent).toBe('My Team');
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
});
