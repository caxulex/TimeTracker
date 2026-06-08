import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CategoryChip } from '../CategoryChip';

describe('CategoryChip', () => {
  it('renders the category name and color style', () => {
    render(<CategoryChip category={{ name: 'IT Security', color: '#DC2626' }} />);

    const chip = screen.getByTestId('category-chip-IT Security');
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent('IT Security');
    expect(chip).toHaveStyle({ color: '#DC2626' });
  });

  it('calls onRemove when remove button is clicked', async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();

    render(
      <CategoryChip
        category={{ name: 'SEO', color: '#10B981' }}
        onRemove={onRemove}
      />
    );

    await user.click(screen.getByTestId('category-chip-remove-SEO'));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });
});
