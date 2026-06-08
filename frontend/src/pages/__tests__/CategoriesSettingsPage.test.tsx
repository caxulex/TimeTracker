import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CategoriesSettingsPage } from '../CategoriesSettingsPage';

const hooks = vi.hoisted(() => ({
  useCategories: vi.fn(),
  useCreateCategory: vi.fn(),
  useUpdateCategory: vi.fn(),
  useDeleteCategory: vi.fn(),
}));

vi.mock('../../hooks/useApi', () => ({
  useCategories: hooks.useCategories,
  useCreateCategory: hooks.useCreateCategory,
  useUpdateCategory: hooks.useUpdateCategory,
  useDeleteCategory: hooks.useDeleteCategory,
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <CategoriesSettingsPage />
    </QueryClientProvider>
  );
}

describe('CategoriesSettingsPage', () => {
  const createMutateAsync = vi.fn();
  const updateMutate = vi.fn();
  const deleteMutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    hooks.useCategories.mockReturnValue({
      data: [
        {
          id: 1,
          name: 'IT Security',
          color: '#DC2626',
          description: 'Security work',
          task_count: 3,
          created_at: '',
          updated_at: '',
        },
      ],
      isLoading: false,
    });
    hooks.useCreateCategory.mockReturnValue({ mutateAsync: createMutateAsync, isPending: false });
    hooks.useUpdateCategory.mockReturnValue({ mutate: updateMutate });
    hooks.useDeleteCategory.mockReturnValue({ mutateAsync: deleteMutateAsync });
  });

  it('renders categories list and allows inline edits', () => {
    renderPage();

    expect(screen.getByTestId('categories-settings-list')).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue('IT Security'), { target: { value: 'Operations' } });
    expect(updateMutate).toHaveBeenCalled();
  });

  it('shows delete confirmation with task count', () => {
    renderPage();

    fireEvent.click(screen.getByTestId('category-delete-1'));
    expect(screen.getByTestId('category-delete-confirmation')).toBeInTheDocument();
    expect(screen.getByText(/currently applied to 3 tasks/i)).toBeInTheDocument();
  });
});
