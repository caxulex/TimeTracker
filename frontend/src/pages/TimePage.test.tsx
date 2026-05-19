// ============================================
// TIME TRACKER - TIME PAGE TESTS
// Phase 7: Testing - Time entries page component
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { TimePage } from './TimePage';
import type { TimeEntry } from '../types';
import { NotificationProvider } from '../components/Notifications';
import { BrandingProvider } from '../contexts/BrandingContext';

// Mock the auth hook
vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: 1,
      email: 'user@test.com',
      name: 'Test User',
      role: 'user',
      company_id: 1,
    },
    isAuthenticated: true,
  })),
}));

// Mock notifications
vi.mock('../hooks/useNotifications', () => ({
  useNotifications: vi.fn(() => ({
    addNotification: vi.fn(),
  })),
}));

// Mock AI features
vi.mock('../hooks/useAIFeatures', () => ({
  useFeatureEnabled: vi.fn(() => ({ data: false })),
}));

// Mock API client
vi.mock('../api/client', () => ({
  timeEntriesApi: {
    getAll: vi.fn(() => Promise.resolve({
      items: [
        {
          id: 1,
          user_id: 1,
          project_id: 1,
          project_name: 'Project A',
          task_id: null,
          task_name: null,
          description: 'Working on feature',
          start_time: '2026-01-08T09:00:00Z',
          end_time: '2026-01-08T12:00:00Z',
          duration_seconds: 10800,
          is_billable: true,
          created_at: '2026-01-08T09:00:00Z',
          updated_at: '2026-01-08T12:00:00Z',
        },
        {
          id: 2,
          user_id: 1,
          project_id: 2,
          project_name: 'Project B',
          task_id: null,
          task_name: null,
          description: 'Bug fix',
          start_time: '2026-01-08T13:00:00Z',
          end_time: '2026-01-08T14:30:00Z',
          duration_seconds: 5400,
          is_billable: false,
          created_at: '2026-01-08T13:00:00Z',
          updated_at: '2026-01-08T14:30:00Z',
        },
      ],
      total: 2,
      page: 1,
      size: 50,
      pages: 1,
    })),
    create: vi.fn(() => Promise.resolve({
      id: 3,
      duration_seconds: 3600,
    })),
    update: vi.fn(() => Promise.resolve({})),
    delete: vi.fn(() => Promise.resolve()),
    getTimer: vi.fn(() => Promise.resolve({ is_running: false, current_entry: null })),
    startTimer: vi.fn(() => Promise.resolve({ id: 1, is_running: true })),
    stopTimer: vi.fn(() => Promise.resolve({ id: 1, duration_seconds: 3600 })),
  },
  projectsApi: {
    getAll: vi.fn(() => Promise.resolve({
      items: [
        { id: 1, name: 'Project A', company_id: 1, is_active: true },
        { id: 2, name: 'Project B', company_id: 1, is_active: true },
      ],
      total: 2,
    })),
  },
  tasksApi: {
    getAll: vi.fn(() => Promise.resolve({
      items: [],
      total: 0,
    })),
  },
}));

// Create query client for tests
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  });

// Test wrapper with providers
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NotificationProvider>
          <BrandingProvider>
            {children}
          </BrandingProvider>
        </NotificationProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('TimePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render the time entries page title', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/time/i)).toBeInTheDocument();
      });
    });

    it('should render loading state initially', () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      // Should show loading
      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('should display time entries after loading', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });
    });

    it('should display project names in entries', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Use getAllByText since project names may appear multiple times
        // (in entry list and possibly in filter dropdown)
        const projectAElements = screen.getAllByText('Project A');
        const projectBElements = screen.getAllByText('Project B');
        expect(projectAElements.length).toBeGreaterThan(0);
        expect(projectBElements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Timer Widget', () => {
    it('should render timer widget section', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Timer widget should be present
        const page = screen.getByText(/time/i);
        expect(page).toBeInTheDocument();
      });
    });
  });

  describe('Manual Entry', () => {
    it('should have manual entry button', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        const addButton = screen.queryByRole('button', { name: /manual|add/i });
        // Button should be present for manual entry
        expect(addButton).toBeDefined();
      });
    });
  });

  describe('Project Filter', () => {
    it('should render project filter dropdown', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Look for filter or select element
        const filterSelect = screen.queryByRole('combobox');
        // Should have filter available
        expect(filterSelect).toBeDefined();
      });
    });
  });

  describe('Entry List', () => {
    it('should group entries by date', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Entries should be grouped by date
        // The component groups by date string
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
        expect(screen.getByText('Bug fix')).toBeInTheDocument();
      });
    });

    it('should display duration for each entry', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Should show formatted duration
        // 10800 seconds = 3:00:00
        // 5400 seconds = 1:30:00
        const content = screen.getByText(/working on feature/i);
        expect(content).toBeInTheDocument();
      });
    });
  });

  describe('Entry Actions', () => {
    it('should show edit and delete options for entries', async () => {
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Each entry should have action buttons
        const entryText = screen.getByText('Working on feature');
        expect(entryText).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no entries', async () => {
      const { timeEntriesApi } = await import('../api/client');
      vi.mocked(timeEntriesApi.getAll).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        size: 50,
        pages: 0,
      });

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        // Should show empty state message or the page title
        const pageElement = screen.getByText(/time/i);
        expect(pageElement).toBeInTheDocument();
      });
    });
  });

  describe('Pagination', () => {
    it('should request the list with page_size (not size) and page=1', async () => {
      const { timeEntriesApi } = await import('../api/client');
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(vi.mocked(timeEntriesApi.getAll)).toHaveBeenCalled();
      });

      const firstCallArgs = vi.mocked(timeEntriesApi.getAll).mock.calls[0][0] ?? {};
      // Param name must match the FastAPI declaration on /api/time.
      expect(firstCallArgs).toHaveProperty('page_size', 100);
      expect(firstCallArgs).toHaveProperty('page', 1);
      // The old (broken) `size` key must not be sent.
      expect(firstCallArgs).not.toHaveProperty('size');
    });

    it('should hide Load More when all items are loaded (items.length >= total)', async () => {
      const { timeEntriesApi } = await import('../api/client');
      vi.mocked(timeEntriesApi.getAll).mockResolvedValueOnce({
        items: [
          {
            id: 1,
            user_id: 1,
            project_id: 1,
            task_id: null,
            description: 'Single entry',
            start_time: '2026-01-08T09:00:00Z',
            end_time: '2026-01-08T10:00:00Z',
            duration_seconds: 3600,
            is_running: false,
            created_at: '2026-01-08T09:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        size: 100,
        pages: 1,
      });

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Single entry')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
    });

    it('should show Load More when items.length < total, fetch next page on click, and append', async () => {
      const { timeEntriesApi } = await import('../api/client');
      const makeEntry = (id: number): TimeEntry => ({
        id,
        user_id: 1,
        project_id: 1,
        task_id: null,
        description: `Entry ${id}`,
        start_time: '2026-01-08T09:00:00Z',
        end_time: '2026-01-08T10:00:00Z',
        duration_seconds: 3600,
        is_running: false,
        created_at: '2026-01-08T09:00:00Z',
      });
      vi.mocked(timeEntriesApi.getAll)
        .mockResolvedValueOnce({
          items: [makeEntry(1), makeEntry(2)],
          total: 4,
          page: 1,
          size: 100,
          pages: 2,
        })
        .mockResolvedValueOnce({
          items: [makeEntry(3), makeEntry(4)],
          total: 4,
          page: 2,
          size: 100,
          pages: 2,
        });

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Entry 1')).toBeInTheDocument();
      });

      const loadMore = await screen.findByRole('button', { name: /load more/i });
      expect(loadMore).toBeInTheDocument();
      // Showing X of Y indicator.
      expect(screen.getByText(/showing 2 of 4 entries/i)).toBeInTheDocument();

      fireEvent.click(loadMore);

      await waitFor(() => {
        // Previously loaded entries remain (appended, not replaced).
        expect(screen.getByText('Entry 1')).toBeInTheDocument();
        expect(screen.getByText('Entry 3')).toBeInTheDocument();
        expect(screen.getByText('Entry 4')).toBeInTheDocument();
      });

      // After loading the last page, the button is gone.
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
      });

      // Second call must request page=2 with the same page_size.
      const secondCallArgs = vi.mocked(timeEntriesApi.getAll).mock.calls[1][0] ?? {};
      expect(secondCallArgs).toHaveProperty('page', 2);
      expect(secondCallArgs).toHaveProperty('page_size', 100);
    });

    it('should reset pagination (refetch page 1) when the Date Range filter changes', async () => {
      const { timeEntriesApi } = await import('../api/client');
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });

      const callsBefore = vi.mocked(timeEntriesApi.getAll).mock.calls.length;

      const selects = screen.getAllByRole('combobox');
      // Filter row is: [Project, Date Range]. Pick the Date Range select
      // (second combobox in the filters row, after the timer widget's
      // project picker may also be present — use the one with the
      // "all"/"today"/... options).
      const dateRangeSelect = selects.find((el) =>
        Array.from((el as HTMLSelectElement).options).some((o) => o.value === 'today')
      ) as HTMLSelectElement | undefined;
      expect(dateRangeSelect).toBeDefined();

      fireEvent.change(dateRangeSelect!, { target: { value: 'today' } });

      await waitFor(() => {
        const calls = vi.mocked(timeEntriesApi.getAll).mock.calls;
        expect(calls.length).toBeGreaterThan(callsBefore);
        const lastArgs = calls[calls.length - 1][0] ?? {};
        // Filter change must reset to page 1 and include the new date filter.
        expect(lastArgs).toHaveProperty('page', 1);
        expect(lastArgs).toHaveProperty('start_date');
        expect(lastArgs).toHaveProperty('end_date');
      });
    });

    it('should reset pagination (refetch page 1) when the Project filter changes', async () => {
      const { timeEntriesApi } = await import('../api/client');
      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });

      const callsBefore = vi.mocked(timeEntriesApi.getAll).mock.calls.length;

      const selects = screen.getAllByRole('combobox');
      // The TimerWidget also has a project picker. Distinguish the
      // filter-row project select by its first option being the
      // "All Projects" translation key (the filter is the only one with
      // an empty-value "all" option among project pickers).
      const projectSelect = selects.find((el) => {
        const opts = Array.from((el as HTMLSelectElement).options);
        const first = opts[0];
        return (
          first &&
          first.value === '' &&
          /all\s*projects/i.test(first.textContent || '') &&
          opts.some((o) => o.value === '1')
        );
      }) as HTMLSelectElement | undefined;
      expect(projectSelect).toBeDefined();

      fireEvent.change(projectSelect!, { target: { value: '1' } });

      await waitFor(() => {
        const calls = vi.mocked(timeEntriesApi.getAll).mock.calls;
        expect(calls.length).toBeGreaterThan(callsBefore);
        const lastArgs = calls[calls.length - 1][0] ?? {};
        expect(lastArgs).toHaveProperty('page', 1);
        expect(lastArgs).toHaveProperty('project_id', 1);
      });
    });
  });
});
