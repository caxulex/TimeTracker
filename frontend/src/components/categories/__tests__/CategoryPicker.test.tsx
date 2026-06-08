import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CategoryPicker } from '../CategoryPicker';

const useCategoriesMock = vi.fn();
const mutateAsyncMock = vi.fn();

vi.mock('../../../hooks/useApi', () => ({
  useCategories: () => useCategoriesMock(),
  useCreateCategory: () => ({ mutateAsync: mutateAsyncMock, isPending: false }),
}));

describe('CategoryPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useCategoriesMock.mockReturnValue({
      data: [
        { id: 1, name: 'Dev', color: '#3B82F6', description: null, task_count: 0, created_at: '', updated_at: '' },
        { id: 2, name: 'SEO', color: '#10B981', description: null, task_count: 0, created_at: '', updated_at: '' },
      ],
    });
  });

  it('renders selected chips and adds a category via select', () => {
    const onChange = vi.fn();
    render(<CategoryPicker selectedIds={[1]} onChange={onChange} />);

    expect(screen.getByTestId('category-chip-Dev')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('category-picker-select'), { target: { value: '2' } });
    expect(onChange).toHaveBeenCalledWith([1, 2]);
  });

  it('opens create modal from create option', () => {
    const onChange = vi.fn();
    render(<CategoryPicker selectedIds={[]} onChange={onChange} />);

    fireEvent.change(screen.getByTestId('category-picker-select'), { target: { value: '__create__' } });
    expect(screen.getByText('Create Category')).toBeInTheDocument();
  });
});
