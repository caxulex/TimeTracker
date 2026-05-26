// ============================================
// TIME TRACKER - USERS PAGE PAGINATION TESTS
// Covers the useInfiniteQuery refactor introduced in
// feat/admin-lists-pagination:
//   - initial fetch uses page_size=50,
//   - "Showing X of N users" indicator renders,
//   - Load More advances pages and disappears at the end,
//   - the client-side "show deactivated" toggle filters the
//     loaded pages without resetting pagination.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UsersPage } from '../UsersPage';

const mockCurrentUser = {
  id: 1,
  name: 'Admin',
  email: 'admin@example.com',
  role: 'super_admin' as const,
  is_active: true,
  company_id: 1,
  created_at: '2026-01-01T00:00:00Z',
};

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: mockCurrentUser, isAuthenticated: true }),
}));

const usersGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  usersApi: {
    getAll: (...args: unknown[]) => usersGetAll(...args),
    update: vi.fn(),
    updateRole: vi.fn(),
  },
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const mkUser = (id: number, overrides: Record<string, unknown> = {}) => ({
  id,
  name: `User ${id}`,
  email: `user${id}@example.com`,
  role: 'regular_user',
  is_active: true,
  company_id: 1,
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

describe('UsersPage - pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initial fetch uses page_size=50 and renders "Showing X of N users"', async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => mkUser(i + 2));
    usersGetAll.mockResolvedValueOnce({
      items: page1,
      total: 137,
      page: 1,
      page_size: 50,
      pages: 3,
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('users-count').textContent).toMatch(
        /Showing 50 of 137 users/
      );
    });
    expect(usersGetAll).toHaveBeenCalledWith(1, 50);
    expect(screen.getByTestId('users-load-more')).toBeInTheDocument();
  });

  it('"Load More" advances to the next page; indicator updates; button disappears at end', async () => {
    const user = userEvent.setup();
    const page1 = Array.from({ length: 50 }, (_, i) => mkUser(i + 2));
    const page2 = Array.from({ length: 30 }, (_, i) => mkUser(i + 52));
    usersGetAll
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
    await screen.findByTestId('users-load-more');

    await user.click(screen.getByTestId('users-load-more'));

    await waitFor(() => {
      expect(usersGetAll).toHaveBeenCalledWith(2, 50);
    });
    await waitFor(() => {
      expect(screen.getByTestId('users-count').textContent).toMatch(
        /Showing 80 of 80 users/
      );
    });
    expect(screen.queryByTestId('users-load-more')).not.toBeInTheDocument();
  });

  it('Load More is absent when the first page already contains everything', async () => {
    usersGetAll.mockResolvedValueOnce({
      items: [mkUser(2), mkUser(3)],
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('users-count').textContent).toMatch(
        /Showing 2 of 2 users/
      );
    });
    expect(screen.queryByTestId('users-load-more')).not.toBeInTheDocument();
  });

  it('toggling "Show deactivated" re-filters the loaded pages client-side', async () => {
    const user = userEvent.setup();
    const items = [
      mkUser(2, { name: 'Active Alice', is_active: true }),
      mkUser(3, { name: 'Inactive Ivan', is_active: false }),
    ];
    usersGetAll.mockResolvedValue({
      items,
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();

    await screen.findByText('Active Alice');
    // Inactive users are filtered out by default.
    expect(screen.queryByText('Inactive Ivan')).not.toBeInTheDocument();

    const toggle = screen.getByLabelText(/show deactivated users/i);
    await user.click(toggle);

    // Now both rows are visible; flipping the filter must NOT refetch.
    await screen.findByText('Inactive Ivan');
    expect(screen.getByText('Active Alice')).toBeInTheDocument();
    expect(usersGetAll).toHaveBeenCalledTimes(1);
  });
});
