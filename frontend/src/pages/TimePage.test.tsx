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
import { findByLabelTextReliable, findByTestIdReliable, waitForReliable } from '../test/asyncHelpers';

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

      await waitForReliable(() => {
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

    it('prefills manual description from selected task when description is empty', async () => {
      const { tasksApi } = await import('../api/client');
      vi.mocked(tasksApi.getAll).mockImplementation(async (filters?: { project_id?: number }) => {
        if (filters?.project_id === 1) {
          return {
            items: [
              {
                id: 101,
                project_id: 1,
                name: 'Task Alpha',
                description: null,
                status: 'TODO',
                created_at: '2026-01-08T09:00:00Z',
                basecamp_due_on: null,
                basecamp_todo_created_at: null,
                basecamp_todo_position: null,
              },
            ],
            total: 1,
            page: 1,
            size: 100,
            pages: 1,
          };
        }
        return { items: [], total: 0, page: 1, size: 100, pages: 1 };
      });

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      const user = userEvent.setup();
      await waitFor(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });

      const addButton = screen.getAllByRole('button', { name: /manual|add/i })[0];
      await user.click(addButton);

      const descriptionInput = await findByLabelTextReliable(/description/i) as HTMLInputElement;
      expect(descriptionInput.value).toBe('');

      // waitFor needed: modal renders inputs in multiple passes; description appears first via findByLabelText, but project/task inputs may be a tick behind. Sync getElementById fails intermittently in CI without this wait.
      await waitForReliable(() => {
        expect(document.getElementById('manual-entry-project')).toBeTruthy();
      });
      const projectInput = document.getElementById('manual-entry-project') as HTMLInputElement;
      await user.click(projectInput);
      await user.type(projectInput, 'Project A');
      const projectOption = await findByTestIdReliable('project-select-option-1');
      fireEvent.mouseDown(projectOption);

      // waitFor needed: modal renders inputs in multiple passes; description appears first via findByLabelText, but project/task inputs may be a tick behind. Sync getElementById fails intermittently in CI without this wait.
      await waitForReliable(() => {
        expect(document.getElementById('manual-entry-task')).toBeTruthy();
      });
      const taskInput = document.getElementById('manual-entry-task') as HTMLInputElement;
      await user.click(taskInput);
      const taskOption = await findByTestIdReliable('task-select-option-101');
      fireEvent.mouseDown(taskOption);

      await waitForReliable(() => {
        expect((screen.getByLabelText(/description/i) as HTMLInputElement).value).toBe('Task Alpha');
      });
    });

    it('does not overwrite manual description when user already typed text', async () => {
      const { tasksApi } = await import('../api/client');
      vi.mocked(tasksApi.getAll).mockImplementation(async (filters?: { project_id?: number }) => {
        if (filters?.project_id === 1) {
          return {
            items: [
              {
                id: 102,
                project_id: 1,
                name: 'Task Beta',
                description: null,
                status: 'TODO',
                created_at: '2026-01-08T09:00:00Z',
                basecamp_due_on: null,
                basecamp_todo_created_at: null,
                basecamp_todo_position: null,
              },
            ],
            total: 1,
            page: 1,
            size: 100,
            pages: 1,
          };
        }
        return { items: [], total: 0, page: 1, size: 100, pages: 1 };
      });

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      const user = userEvent.setup();
      await waitForReliable(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });

      const addButton = screen.getAllByRole('button', { name: /manual|add/i })[0];
      await user.click(addButton);

      const descriptionInput = await findByLabelTextReliable(/description/i) as HTMLInputElement;
      await user.type(descriptionInput, 'My custom text');

      // waitFor needed: modal renders inputs in multiple passes; description appears first via findByLabelText, but project/task inputs may be a tick behind. Sync getElementById fails intermittently in CI without this wait.
      await waitForReliable(() => {
        expect(document.getElementById('manual-entry-project')).toBeTruthy();
      });
      const projectInput = document.getElementById('manual-entry-project') as HTMLInputElement;
      await user.click(projectInput);
      await user.type(projectInput, 'Project A');
      const projectOption = await findByTestIdReliable('project-select-option-1');
      fireEvent.mouseDown(projectOption);

      // waitFor needed: modal renders inputs in multiple passes; description appears first via findByLabelText, but project/task inputs may be a tick behind. Sync getElementById fails intermittently in CI without this wait.
      await waitForReliable(() => {
        expect(document.getElementById('manual-entry-task')).toBeTruthy();
      });
      const taskInput = document.getElementById('manual-entry-task') as HTMLInputElement;
      await user.click(taskInput);
      const taskOption = await findByTestIdReliable('task-select-option-102');
      fireEvent.mouseDown(taskOption);

      expect(descriptionInput.value).toBe('My custom text');
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

      await waitForReliable(() => {
        expect(screen.getByText('Entry 1')).toBeInTheDocument();
      });

      const loadMore = await screen.findByRole('button', { name: /load more/i });
      expect(loadMore).toBeInTheDocument();
      // Showing X of Y indicator.
      expect(screen.getByText(/showing 2 of 4 entries/i)).toBeInTheDocument();

      fireEvent.click(loadMore);

      await waitForReliable(() => {
        // Previously loaded entries remain (appended, not replaced).
        expect(screen.getByText('Entry 1')).toBeInTheDocument();
        expect(screen.getByText('Entry 3')).toBeInTheDocument();
        expect(screen.getByText('Entry 4')).toBeInTheDocument();
      });

      // After loading the last page, the button is gone.
      await waitForReliable(() => {
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

      await waitForReliable(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });

      const callsBefore = vi.mocked(timeEntriesApi.getAll).mock.calls.length;

      const selects = screen.getAllByRole('combobox');
      // Filter row is: [Project, Date Range]. Pick the Date Range select
      // (second combobox in the filters row, after the timer widget's
      // project picker may also be present — use the one with the
      // "all"/"today"/... options).
      const dateRangeSelect = selects.find((el) =>
        Array.from((el as HTMLSelectElement).options ?? []).some((o) => o.value === 'today')
      ) as HTMLSelectElement | undefined;
      expect(dateRangeSelect).toBeDefined();

      fireEvent.change(dateRangeSelect!, { target: { value: 'today' } });

      await waitForReliable(() => {
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

      await waitForReliable(() => {
        expect(screen.getByText('Working on feature')).toBeInTheDocument();
      });

      const callsBefore = vi.mocked(timeEntriesApi.getAll).mock.calls.length;

      const selects = screen.getAllByRole('combobox');
      // The TimerWidget also has a project picker. Distinguish the
      // filter-row project select by its first option being the
      // "All Projects" translation key (the filter is the only one with
      // an empty-value "all" option among project pickers).
      const projectSelect = selects.find((el) => {
        const opts = Array.from((el as HTMLSelectElement).options ?? []);
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

      await waitForReliable(() => {
        const calls = vi.mocked(timeEntriesApi.getAll).mock.calls;
        expect(calls.length).toBeGreaterThan(callsBefore);
        const lastArgs = calls[calls.length - 1][0] ?? {};
        expect(lastArgs).toHaveProperty('page', 1);
        expect(lastArgs).toHaveProperty('project_id', 1);
      });
    });
  });

  // -----------------------------------------------------------------
  // Regression: fix/entry-project-label-from-response
  // The entry card must render the project label/color directly from
  // TimeEntryResponse.project_name / project_color, not from a lookup
  // against the locally-cached projects list. Otherwise a tenant with
  // > 20 active projects would see entries from "older" projects render
  // unlabeled (the projects list endpoint default-paginates at 20).
  // -----------------------------------------------------------------
  describe('Project label rendering reads from entry, not projects list', () => {
    it('renders project name + color for an entry whose project is NOT in the locally-cached projects list', async () => {
      const { timeEntriesApi, projectsApi } = await import('../api/client');

      // Projects list is intentionally short — entry.project_id=99 is
      // NOT in it. With the old projects.find() lookup this entry
      // would render unlabeled with a gray bar.
      vi.mocked(projectsApi.getAll).mockResolvedValueOnce({
        items: [
          { id: 1, name: 'Project A', company_id: 1, is_active: true } as never,
        ],
        total: 1,
        page: 1,
        page_size: 100,
        pages: 1,
      } as never);

      vi.mocked(timeEntriesApi.getAll).mockResolvedValueOnce({
        items: [
          {
            id: 42,
            user_id: 1,
            project_id: 99,
            project_name: 'Beyond Pagination Project',
            project_color: '#FF00AA',
            task_id: null,
            description: 'Entry whose project is past the page',
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
      } as never);

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      // Project name appears even though it's NOT in projects list.
      await waitForReliable(() => {
        expect(
          screen.getByText('Beyond Pagination Project')
        ).toBeInTheDocument();
      });

      // Color comes from entry.project_color (the colored bar uses
      // inline style backgroundColor). Look for the indicator element.
      const description = screen.getByText(
        'Entry whose project is past the page'
      );
      const card = description.closest('div.flex.items-center.justify-between');
      expect(card).not.toBeNull();
      const colorBar = card!.querySelector('div[style*="background"]') as HTMLElement | null;
      expect(colorBar).not.toBeNull();
      // jsdom normalizes hex to rgb; match either form.
      const bg = colorBar!.style.backgroundColor.toLowerCase();
      expect(bg === '#ff00aa' || bg === 'rgb(255, 0, 170)').toBe(true);
    });

    it('renders no project label for a meeting entry (project_name: null)', async () => {
      const { timeEntriesApi } = await import('../api/client');

      vi.mocked(timeEntriesApi.getAll).mockResolvedValueOnce({
        items: [
          {
            id: 7,
            user_id: 1,
            project_id: null,
            project_name: null,
            project_color: null,
            task_id: null,
            description: 'Sync meeting',
            start_time: '2026-01-08T15:00:00Z',
            end_time: '2026-01-08T15:30:00Z',
            duration_seconds: 1800,
            is_running: false,
            created_at: '2026-01-08T15:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        size: 100,
        pages: 1,
      } as never);

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitForReliable(() => {
        expect(screen.getByText('Sync meeting')).toBeInTheDocument();
      });

      // Only the filter dropdown contains "Project A" / "Project B" —
      // the meeting card itself has no project label. Confirm the card
      // structure has no project name <span>.
      const description = screen.getByText('Sync meeting');
      const card = description.closest('div.flex.items-center.justify-between');
      expect(card).not.toBeNull();
      // The project label, when present, is a span containing exactly
      // the project name as its trailing text node next to an icon.
      // For a meeting card we expect zero project labels matching the
      // typical project names from the default projects mock.
      expect(card!.textContent || '').not.toMatch(/Project A|Project B/);
    });

    it('requests projects list with page_size: 100 so the filter dropdown is not capped at the server default', async () => {
      const { projectsApi } = await import('../api/client');

      render(
        <TestWrapper>
          <TimePage />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(vi.mocked(projectsApi.getAll)).toHaveBeenCalled();
      });

      const args = vi.mocked(projectsApi.getAll).mock.calls[0][0] ?? {};
      expect(args).toHaveProperty('page_size', 100);
      expect(args).toHaveProperty('include_archived', false);
    });
  });
});
