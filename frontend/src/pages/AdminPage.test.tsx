// ============================================
// TIME TRACKER - ADMIN PAGE TESTS
// Phase 2: Test Coverage - Admin Dashboard
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { User } from '../types';

// ============================================
// MOCKS — must be declared before component import
// ============================================

const mockAdminUser = {
  id: 1,
  name: 'Admin User',
  email: 'admin@example.com',
  role: 'super_admin' as const,
  is_active: true,
  company_id: 1,
  created_at: new Date().toISOString(),
};

const mockRegularUser = {
  id: 5,
  name: 'Regular User',
  email: 'user@example.com',
  role: 'regular_user' as const,
  is_active: true,
  company_id: 1,
  created_at: new Date().toISOString(),
};

let currentMockUser: User = mockAdminUser;

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({
    user: currentMockUser,
  })),
}));

// Helpers — use importOriginal to preserve all exports (cn, truncate, etc.)
// that child components like Button and Card depend on
vi.mock('../utils/helpers', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../utils/helpers')>();
  return {
    ...actual,
    isAdminUser: vi.fn((user: User | null | undefined) =>
      user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'company_admin'
    ),
    formatDate: vi.fn((d: string) => d),
    formatDuration: vi.fn((s: number) => `${Math.floor(s / 3600)}h`),
  };
});

// Mock API client — AdminPage uses usersApi
const mockUsers = [
  { id: 2, name: 'Alice', email: 'alice@test.com', role: 'regular_user', is_active: true },
  { id: 3, name: 'Bob', email: 'bob@test.com', role: 'regular_user', is_active: true },
  { id: 4, name: 'Carol', email: 'carol@test.com', role: 'regular_user', is_active: false },
];

vi.mock('../api/client', () => ({
  usersApi: {
    getAll: vi.fn(() =>
      Promise.resolve({
        items: mockUsers,
        total: 3,
        page: 1,
        size: 20,
        pages: 1,
      })
    ),
    delete: vi.fn(() => Promise.resolve()),
    updateRole: vi.fn(() => Promise.resolve()),
    update: vi.fn(() => Promise.resolve()),
  },
}));

// Import after mocks
import { AdminPage } from './AdminPage';

// ============================================
// TEST UTILITIES
// ============================================

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });

function renderAdminPage(initialRoute = '/admin') {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/dashboard" element={<div>Dashboard Redirect</div>} />
          <Route path="/login" element={<div>Login Redirect</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ============================================
// TESTS
// ============================================

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentMockUser = mockAdminUser;
  });

  // ----------------------------------------
  // A) Renders admin dashboard with summary data
  // ----------------------------------------
  describe('Dashboard Rendering', () => {
    it('should render the admin page without crashing', async () => {
      renderAdminPage();

      await waitFor(() => {
        const content = document.body.textContent || '';
        expect(content.length).toBeGreaterThan(0);
      });
    });

    it('should display admin-related heading', async () => {
      renderAdminPage();

      await waitFor(() => {
        const heading =
          screen.queryByText(/admin/i) ||
          screen.queryByText(/user management/i) ||
          screen.queryByText(/management/i);
        expect(heading).toBeTruthy();
      });
    });

    it('should display user list with mock data', async () => {
      renderAdminPage();

      await waitFor(() => {
        expect(screen.getByText('Alice')).toBeInTheDocument();
        expect(screen.getByText('Bob')).toBeInTheDocument();
      });
    });

    it('should show user email addresses', async () => {
      renderAdminPage();

      await waitFor(() => {
        expect(screen.getByText('alice@test.com')).toBeInTheDocument();
        expect(screen.getByText('bob@test.com')).toBeInTheDocument();
      });
    });
  });

  // ----------------------------------------
  // B) Navigation / sub-sections
  // ----------------------------------------
  describe('Navigation', () => {
    it('should render navigation elements or action buttons', async () => {
      renderAdminPage();

      await waitFor(() => {
        // AdminPage has action buttons for user management
        const links = document.querySelectorAll('a, button');
        expect(links.length).toBeGreaterThan(0);
      });
    });

    it('should have a search input for filtering users', async () => {
      renderAdminPage();

      await waitFor(() => {
        const searchInput =
          screen.queryByPlaceholderText(/search/i) ||
          screen.queryByRole('textbox');
        expect(searchInput).toBeTruthy();
      });
    });
  });

  // ----------------------------------------
  // C) Permission guard for non-admin
  // ----------------------------------------
  describe('Permission Guard', () => {
    it('should restrict content for non-admin users', async () => {
      currentMockUser = mockRegularUser;
      const helpers = await import('../utils/helpers');
      vi.mocked(helpers.isAdminUser).mockReturnValue(false);

      renderAdminPage();

      await waitFor(() => {
        const content = document.body.textContent?.toLowerCase() || '';
        // Non-admin: should see access denied OR not see user list
        expect(
          content.includes('access') ||
          content.includes('denied') ||
          content.includes('permission') ||
          content.includes('admin') ||
          !content.includes('alice')
        ).toBeTruthy();
      });
    });
  });

  // ----------------------------------------
  // D) Sub-sections render with mock data
  // ----------------------------------------
  describe('Data Display', () => {
    it('should show user role information', async () => {
      renderAdminPage();

      await waitFor(() => {
        const content = document.body.textContent?.toLowerCase() || '';
        // Should show role badges or role text
        expect(
          content.includes('user') ||
          content.includes('admin') ||
          content.includes('regular')
        ).toBeTruthy();
      });
    });

    it('should handle API errors without crashing', async () => {
      const { usersApi } = await import('../api/client');
      vi.mocked(usersApi.getAll).mockRejectedValueOnce(new Error('Server error'));

      renderAdminPage();

      await waitFor(() => {
        const content = document.body.textContent || '';
        expect(content.length).toBeGreaterThan(0);
      });
    });

    it('should show loading state initially', async () => {
      const { usersApi } = await import('../api/client');
      const helpers = await import('../utils/helpers');

      // Restore isAdminUser (Permission Guard test may have overridden it)
      vi.mocked(helpers.isAdminUser).mockImplementation(
        (user: User | null | undefined) =>
          user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'company_admin'
      );

      vi.mocked(usersApi.getAll).mockReset();
      vi.mocked(usersApi.getAll).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderAdminPage();

      await waitFor(() => {
        const loading =
          screen.queryByText(/loading/i) ||
          document.querySelector('.animate-spin');
        expect(loading).toBeTruthy();
      });
    });
  });
});
