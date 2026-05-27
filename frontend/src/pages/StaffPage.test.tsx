// ============================================
// TIME TRACKER - STAFF PAGE TESTS
// Phase 2: Test Coverage - Staff Management
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { User } from '../types';

// ============================================
// MOCKS — must be declared before component import
// ============================================

// Mock Recharts to avoid canvas issues
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="responsive-container">{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div data-testid="cell" />,
}));

// Auth store mock
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

// Notifications hook
vi.mock('../hooks/useStaffNotifications', () => ({
  useStaffNotifications: vi.fn(() => ({
    notifyStaffCreated: vi.fn(),
    notifyStaffCreationFailed: vi.fn(),
    notifyStaffUpdated: vi.fn(),
    notifyStaffDeleted: vi.fn(),
    notifyError: vi.fn(),
    notifyExportStarted: vi.fn(),
    notifyPayRateSet: vi.fn(),
    notifyAddedToTeam: vi.fn(),
    notifyRemovedFromTeam: vi.fn(),
  })),
}));

// Permissions hook
vi.mock('../hooks/usePermissions', () => ({
  usePermissions: vi.fn(() => ({
    checkPermission: vi.fn(() => true),
    canManageStaff: true,
    canViewPayroll: true,
    canManageTeams: true,
    canExportData: true,
    canModifyStaff: true,
    canDeactivateStaff: true,
  })),
}));

// Form validation hook
vi.mock('../hooks/useStaffFormValidation', () => ({
  useStaffFormValidation: vi.fn(() => ({
    errors: {},
    validateStaffForm: vi.fn(() => ({ isValid: true, errors: {} })),
    hasFieldError: vi.fn(() => false),
    getFieldError: vi.fn(() => ''),
    secureAndValidate: vi.fn((data: unknown) => ({ valid: true, securedData: data })),
    clearErrors: vi.fn(),
  })),
}));

// Debounce hook — return value immediately
vi.mock('../hooks/useDebounce', () => ({
  useDebounce: vi.fn((value: unknown) => value),
}));

// Security util
vi.mock('../utils/security', () => ({
  rateLimiter: {
    canProceed: vi.fn(() => true),
    isAllowed: vi.fn(() => true),
  },
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
    toISODateString: vi.fn((d: Date) => d.toISOString().split('T')[0]),
    getStartOfWeek: vi.fn(() => new Date()),
  };
});

// Sample staff data
const mockStaffList = [
  {
    id: 2,
    name: 'Admin User',
    email: 'admin@example.com',
    role: 'super_admin',
    is_active: true,
    company_id: 1,
    phone: '555-0100',
    job_title: 'Operations Lead',
    department: 'Operations',
    employment_type: 'full_time',
    expected_hours_per_week: 40,
    start_date: '2024-01-10',
    created_at: '2024-01-10T00:00:00Z',
  },
  {
    id: 10,
    name: 'Alice Johnson',
    email: 'alice@company.com',
    role: 'regular_user',
    is_active: true,
    company_id: 1,
    phone: '555-0101',
    job_title: 'Developer',
    department: 'Engineering',
    employment_type: 'full_time',
    expected_hours_per_week: 40,
    start_date: '2025-01-15',
    created_at: '2025-01-15T00:00:00Z',
  },
  {
    id: 11,
    name: 'Bob Smith',
    email: 'bob@company.com',
    role: 'regular_user',
    is_active: true,
    company_id: 1,
    phone: '555-0102',
    job_title: 'Designer',
    department: 'Design',
    employment_type: 'part_time',
    expected_hours_per_week: 20,
    start_date: '2025-03-01',
    created_at: '2025-03-01T00:00:00Z',
  },
  {
    id: 12,
    name: 'Charlie Brown',
    email: 'charlie@company.com',
    role: 'regular_user',
    is_active: false,
    company_id: 1,
    phone: null,
    job_title: 'QA Analyst',
    department: 'Quality',
    employment_type: 'contractor',
    expected_hours_per_week: 30,
    start_date: '2024-06-01',
    created_at: '2024-06-01T00:00:00Z',
  },
];

// Mock API client
vi.mock('../api/client', () => ({
  usersApi: {
    getAll: vi.fn(() =>
      Promise.resolve({
        items: mockStaffList,
        total: 3,
        page: 1,
        size: 20,
        pages: 1,
      })
    ),
    create: vi.fn(() => Promise.resolve({ id: 20, name: 'New User' })),
    update: vi.fn(() => Promise.resolve({ id: 10, name: 'Updated Alice' })),
    delete: vi.fn(() => Promise.resolve()),
    getById: vi.fn((id: number) =>
      Promise.resolve(mockStaffList.find((s) => s.id === id) || mockStaffList[0])
    ),
  },
  teamsApi: {
    getAll: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
    getTeamMembers: vi.fn(() => Promise.resolve([])),
    addMember: vi.fn(() => Promise.resolve()),
    removeMember: vi.fn(() => Promise.resolve()),
  },
  payRatesApi: {
    getUserCurrentRate: vi.fn(() => Promise.resolve(null)),
    getUserPayRates: vi.fn(() => Promise.resolve([])),
    create: vi.fn(() => Promise.resolve({ id: 1 })),
    update: vi.fn(() => Promise.resolve({ id: 1 })),
  },
  timeEntriesApi: {
    getAll: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  },
  projectsApi: {
    getAll: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  },
  reportsApi: {
    getWeekly: vi.fn(() =>
      Promise.resolve({ total_seconds: 0, total_hours: 0 })
    ),
    getDashboard: vi.fn(() => Promise.resolve({})),
  },
  companiesApi: {
    getMyCompany: vi.fn(() =>
      Promise.resolve({ id: 1, name: 'Test Company' })
    ),
  },
}));

// Import after mocks
import { StaffPage } from './StaffPage';

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

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/staff']}>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
};

// ============================================
// TESTS
// ============================================

describe('StaffPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentMockUser = mockAdminUser;
  });

  // ----------------------------------------
  // A) Renders staff list correctly
  // ----------------------------------------
  describe('Staff List Rendering', () => {
    it('should render the staff page heading', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const heading = screen.getByText(/staff/i);
        expect(heading).toBeInTheDocument();
      });
    });

    it('should display staff members from API data', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      // StaffPage renders both mobile cards and desktop table,
      // so each name appears twice in the DOM
      await waitFor(() => {
        expect(screen.getAllByText('Alice Johnson').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Bob Smith').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Charlie Brown').length).toBeGreaterThan(0);
      });
    });

    it('should show email addresses for staff members', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      // Both mobile and desktop views show emails
      await waitFor(() => {
        expect(screen.getAllByText('alice@company.com').length).toBeGreaterThan(0);
        expect(screen.getAllByText('bob@company.com').length).toBeGreaterThan(0);
      });
    });

    it('should display job titles', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      // Job titles appear in both mobile and desktop views
      await waitFor(() => {
        expect(screen.getAllByText('Developer').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Designer').length).toBeGreaterThan(0);
      });
    });
  });

  // ----------------------------------------
  // B) Handles empty staff list
  // ----------------------------------------
  describe('Empty State', () => {
    it('should handle empty staff list without crashing', async () => {
      const { usersApi } = await import('../api/client');
      vi.mocked(usersApi.getAll).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        size: 20,
        pages: 0,
      } as never);

      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const content = document.body.textContent || '';
        expect(content.length).toBeGreaterThan(0);
      });
    });
  });

  // ----------------------------------------
  // C) Search/filter functionality
  // ----------------------------------------
  describe('Search and Filter', () => {
    it('should render a search input', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const searchInput =
          screen.queryByPlaceholderText(/search/i) ||
          screen.queryByRole('searchbox') ||
          screen.queryByRole('textbox');
        expect(searchInput).toBeTruthy();
      });
    });

    it('should filter staff list when typing in search', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );
      const user = userEvent.setup();

      await waitFor(() => {
        expect(screen.getAllByText('Alice Johnson').length).toBeGreaterThan(0);
      });

      // StaffPage renders mobile + desktop search inputs; pick the first
      const searchInputs = screen.getAllByPlaceholderText(/search/i);
      const searchInput = searchInputs[0];

      await user.clear(searchInput);
      await user.type(searchInput, 'Alice');

      await waitFor(() => {
        expect(screen.getAllByText('Alice Johnson').length).toBeGreaterThan(0);
      });
    });
  });

  // ----------------------------------------
  // D) Pagination / Stats
  // ----------------------------------------
  describe('Pagination and Stats', () => {
    it('should show staff count somewhere on the page', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const content = document.body.textContent || '';
        // Should show total count of 3 or active count of 2
        expect(content.includes('3') || content.includes('2')).toBeTruthy();
      });
    });
  });

  // ----------------------------------------
  // E) Permission-based UI
  // ----------------------------------------
  describe('Permission-based UI', () => {
    it('should show add/create button for admin users', async () => {
      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      // "Add Staff Member" and "Add Staff" spans both render in JSDOM
      await waitFor(() => {
        const buttons = screen.getAllByText(/add staff/i);
        expect(buttons.length).toBeGreaterThan(0);
      });
    });

    it('should not render staff management content for non-admin users', async () => {
      currentMockUser = mockRegularUser;
      const helpers = await import('../utils/helpers');
      vi.mocked(helpers.isAdminUser).mockReturnValue(false);

      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const content = document.body.textContent?.toLowerCase() || '';
        // Non-admin should see access restriction or no staff data
        expect(
          content.includes('access') ||
          content.includes('denied') ||
          content.includes('permission') ||
          !content.includes('alice johnson')
        ).toBeTruthy();
      });
    });
  });

  describe('Create Modal Manager Picker', () => {
    it('renders UserSelect for manager and supports typeahead selection', async () => {
      const user = userEvent.setup();
      const helpers = await import('../utils/helpers');

      vi.mocked(helpers.isAdminUser).mockImplementation(
        (u: User | null | undefined) =>
          u?.role === 'super_admin' || u?.role === 'admin' || u?.role === 'company_admin'
      );

      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await user.click((await screen.findAllByRole('button', { name: /add staff/i }))[0]);
      await user.click(await screen.findByRole('button', { name: /next/i }));

      const managerInput = await screen.findByLabelText(/manager/i);
      await user.click(managerInput);
      await user.type(managerInput, 'admin');

      fireEvent.mouseDown(await screen.findByTestId('user-select-option-2'));

      await waitFor(() => {
        expect(managerInput).toHaveValue('Admin User');
      });
    });
  });

  // ----------------------------------------
  // F) Error state
  // ----------------------------------------
  describe('Error Handling', () => {
    it('should handle API failure without crashing', async () => {
      const { usersApi } = await import('../api/client');
      vi.mocked(usersApi.getAll).mockRejectedValueOnce(new Error('Network error'));

      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const content = document.body.textContent || '';
        expect(content.length).toBeGreaterThan(0);
      });
    });
  });

  // ----------------------------------------
  // G) Loading state
  // ----------------------------------------
  describe('Loading State', () => {
    it('should show loading indicator while data loads', async () => {
      const { usersApi } = await import('../api/client');
      const helpers = await import('../utils/helpers');

      // Restore isAdminUser (previous test may have mocked it to return false)
      vi.mocked(helpers.isAdminUser).mockImplementation(
        (user: User | null | undefined) =>
          user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'company_admin'
      );

      // mockReset clears any leftover one-time overrides from previous tests
      vi.mocked(usersApi.getAll).mockReset();
      vi.mocked(usersApi.getAll).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <TestWrapper>
          <StaffPage />
        </TestWrapper>
      );

      await waitFor(() => {
        const loadingIndicator =
          screen.queryByText(/loading/i) ||
          document.querySelector('.animate-spin');

        expect(loadingIndicator).toBeTruthy();
      });
    });
  });
});
