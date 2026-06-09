import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TasksPage } from '../TasksPage';

const tasksGetAll = vi.fn();
const tasksCreate = vi.fn();
const tasksUpdate = vi.fn();
const projectsGetAll = vi.fn();
const categoriesList = vi.fn();

vi.mock('../../api/client', () => ({
  tasksApi: {
    getAll: (...args: unknown[]) => tasksGetAll(...args),
    create: (...args: unknown[]) => tasksCreate(...args),
    update: (...args: unknown[]) => tasksUpdate(...args),
    delete: vi.fn(),
  },
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
  },
  categoriesApi: {
    list: (...args: unknown[]) => categoriesList(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    getById: vi.fn(),
  },
}));

vi.mock('../../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: false }),
}));

vi.mock('../../components/ai', () => ({
  TaskEstimationCard: () => null,
}));

function renderPage() {
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

const project = {
  id: 1,
  name: 'Visible Project',
  description: '',
  color: '#3B82F6',
  team_id: 1,
  team_name: 'Team',
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  task_count: 1,
};

const categories = [
  { id: 1, name: 'Billing', color: '#10B981', description: null },
  { id: 2, name: 'Urgent', color: '#DC2626', description: null },
];

const existingTask = {
  id: 11,
  name: 'Close the books',
  description: 'Month-end cleanup',
  status: 'TODO',
  project_id: 1,
  team_id: 1,
  categories: [categories[0]],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
};

describe('TasksPage - category integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    tasksGetAll.mockResolvedValue({
      items: [existingTask],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    tasksCreate.mockResolvedValue({ id: 20 });
    tasksUpdate.mockResolvedValue({ ...existingTask, categories });
    projectsGetAll.mockResolvedValue({
      items: [project],
      total: 1,
      page: 1,
      page_size: 100,
      pages: 1,
    });
    categoriesList.mockResolvedValue(categories);
  });

  it('renders category chips on task cards and preloads categories in the edit modal', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('Close the books')).toBeInTheDocument();
    expect(screen.getByText('Billing')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /edit task close the books/i }));

    expect(await screen.findByRole('heading', { name: /edit task/i })).toBeInTheDocument();
    expect(screen.getByText('Categories')).toBeInTheDocument();
    expect(screen.getByTestId('category-picker')).toBeInTheDocument();
    expect(screen.getByTestId('category-picker-selected')).toHaveTextContent('Billing');
  });

  it('submits selected category ids from the task modal', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /new task/i }));

    await user.type(await screen.findByLabelText(/task name/i), 'Prepare invoices');

    const categorySelect = await screen.findByLabelText(/add category/i);
    await user.selectOptions(categorySelect, '1');
    await user.selectOptions(categorySelect, '2');

    await user.click(screen.getByRole('button', { name: /create task/i }));

    await waitFor(() => {
      expect(tasksCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Prepare invoices',
          project_id: 1,
          category_ids: [1, 2],
        })
      );
    });
  });

  it('persists edited category ids in the update payload', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /edit task close the books/i }));

    const categorySelect = await screen.findByLabelText(/add category/i);
    await user.selectOptions(categorySelect, '2');

    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(tasksUpdate).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          category_ids: [1, 2],
        })
      );
    });
  });
});
