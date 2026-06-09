import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { TeamMultiSelect } from '../TeamMultiSelect';

const getAllMock = vi.fn();

vi.mock('../../../api/client', () => ({
  teamsApi: {
    getAll: (...args: unknown[]) => getAllMock(...args),
  },
}));

function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('TeamMultiSelect', () => {
  beforeEach(() => {
    getAllMock.mockResolvedValue({
      items: [
        { id: 1, name: 'SEO', color: '#10B981' },
        { id: 2, name: 'Dev', color: '#3B82F6' },
      ],
      total: 2,
      page: 1,
      page_size: 100,
      pages: 1,
    });
  });

  it('adds a selected team', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithQuery(<TeamMultiSelect selectedIds={[]} onChange={onChange} />);

    // Wait for the async query to populate options before selecting
    await screen.findByRole('option', { name: 'SEO' });
    await user.selectOptions(screen.getByLabelText('Add team'), '1');
    expect(onChange).toHaveBeenCalledWith([1]);
  });
});
