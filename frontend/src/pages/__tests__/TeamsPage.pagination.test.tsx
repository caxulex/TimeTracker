// ============================================
// TIME TRACKER - TEAMS PAGE PAGINATION TESTS
// Covers the useInfiniteQuery refactor introduced in
// feat/admin-lists-pagination:
//   - initial fetch uses page_size=50,
//   - "Showing X of N teams" indicator renders,
//   - Load More advances pages and disappears at the end.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TeamsPage } from '../TeamsPage';

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

vi.mock('../../hooks/useStaffNotifications', () => ({
  useStaffNotifications: () => ({
    notifySuccess: vi.fn(),
    notifyError: vi.fn(),
  }),
}));

vi.mock('../../components/users/UserSelect', () => ({
  UserSelect: () => null,
}));

const teamsGetAll = vi.fn();
const teamsGetById = vi.fn();
const usersGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  teamsApi: {
    getAll: (...args: unknown[]) => teamsGetAll(...args),
    getById: (...args: unknown[]) => teamsGetById(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
  },
  usersApi: {
    getAll: (...args: unknown[]) => usersGetAll(...args),
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
  owner_id: 99,
  member_count: 3,
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

describe('TeamsPage - pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    usersGetAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 1,
    });
  });

  it('initial fetch uses page_size=50 and renders "Showing X of N teams"', async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => mkTeam(i + 1));
    teamsGetAll.mockResolvedValueOnce({
      items: page1,
      total: 120,
      page: 1,
      page_size: 50,
      pages: 3,
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('teams-count').textContent).toMatch(
        /Showing 50 of 120 teams/
      );
    });
    expect(teamsGetAll).toHaveBeenCalledWith(1, 50);
    expect(screen.getByTestId('teams-load-more')).toBeInTheDocument();
  });

  it('"Load More" advances to the next page; indicator updates; button disappears at end', async () => {
    const user = userEvent.setup();
    const page1 = Array.from({ length: 50 }, (_, i) => mkTeam(i + 1));
    const page2 = Array.from({ length: 12 }, (_, i) => mkTeam(i + 51));
    teamsGetAll
      .mockResolvedValueOnce({
        items: page1,
        total: 62,
        page: 1,
        page_size: 50,
        pages: 2,
      })
      .mockResolvedValueOnce({
        items: page2,
        total: 62,
        page: 2,
        page_size: 50,
        pages: 2,
      });
    renderPage();
    await screen.findByTestId('teams-load-more');

    await user.click(screen.getByTestId('teams-load-more'));

    await waitFor(() => {
      expect(teamsGetAll).toHaveBeenCalledWith(2, 50);
    });
    await waitFor(() => {
      expect(screen.getByTestId('teams-count').textContent).toMatch(
        /Showing 62 of 62 teams/
      );
    });
    expect(screen.queryByTestId('teams-load-more')).not.toBeInTheDocument();
  });

  it('Load More is absent when the first page already contains everything', async () => {
    teamsGetAll.mockResolvedValueOnce({
      items: [mkTeam(1), mkTeam(2)],
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('teams-count').textContent).toMatch(
        /Showing 2 of 2 teams/
      );
    });
    expect(screen.queryByTestId('teams-load-more')).not.toBeInTheDocument();
  });
});
