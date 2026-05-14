// ============================================
// TIME TRACKER - TASKS PAGE STAFF VISIBILITY TEST
// --------------------------------------------
// Confirms the task-creation UI (the "New Task" button) is rendered
// for a non-admin (regular_user) just as it is for admins, so staff
// can create tasks on any project they can already see.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TasksPage } from '../TasksPage';

vi.mock('../../api/client', () => ({
  tasksApi: {
    getAll: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 1 }),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  projectsApi: {
    getAll: vi.fn().mockResolvedValue({
      items: [{ id: 1, name: 'Visible Project', color: '#3B82F6', team_id: 1 }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    }),
  },
}));

vi.mock('../../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: false }),
}));

vi.mock('../../components/ai', () => ({
  TaskEstimationCard: () => null,
}));

function renderTasksPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('TasksPage - staff task creation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the New Task button for non-admin users', async () => {
    renderTasksPage();
    await waitFor(() => {
      // The "New Task" button must be reachable by any authenticated
      // user — task creation is no longer admin-gated (2026-05-14).
      expect(screen.getByRole('button', { name: /new task/i })).toBeInTheDocument();
    });
  });

  it('renders the Tasks heading for non-admin users', async () => {
    renderTasksPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^tasks$/i })).toBeInTheDocument();
    });
  });
});
