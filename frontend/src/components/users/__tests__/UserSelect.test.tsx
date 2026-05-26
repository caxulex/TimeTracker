// ============================================
// TIME TRACKER - USER SELECT TESTS
// Mirrors ProjectSelect.test.tsx — covers the typeahead combobox
// introduced in feat/user-team-select-typeahead.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserSelect } from '../UserSelect';
import type { User } from '../../../types';

vi.mock('../../../api/client', () => ({
  usersApi: {
    getAll: vi.fn(),
  },
}));

import { usersApi } from '../../../api/client';

const makeUser = (overrides: Partial<User>): User =>
  ({
    id: 1,
    email: 'a@example.com',
    name: 'Alice Adams',
    role: 'worker',
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: null,
    ...overrides,
  }) as User;

const users: User[] = [
  makeUser({ id: 1, name: 'Alice Adams', email: 'alice@example.com' }),
  makeUser({ id: 2, name: 'Bob Brown', email: 'bob@example.com' }),
  makeUser({ id: 3, name: 'Carol Developer', email: 'carol@example.com' }),
  makeUser({ id: 4, name: 'Dan Other', email: 'dan@example.com' }),
];

function renderSelect(
  props: Partial<React.ComponentProps<typeof UserSelect>> = {}
) {
  const onChange = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <UserSelect
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        users={props.users ?? users}
        placeholder={props.placeholder ?? 'Select user'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange };
}

describe('UserSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the currently-selected user name in the input', () => {
    renderSelect({ value: 3 });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    expect(input.value).toBe('Carol Developer');
  });

  it('opens the dropdown on focus and renders all users', () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    expect(screen.getByTestId('user-select-listbox')).toBeInTheDocument();
    expect(screen.getByTestId('user-select-option-1')).toBeInTheDocument();
    expect(screen.getByTestId('user-select-option-2')).toBeInTheDocument();
    expect(screen.getByTestId('user-select-option-3')).toBeInTheDocument();
    expect(screen.getByTestId('user-select-option-4')).toBeInTheDocument();
  });

  it('filters by name (case-insensitive substring)', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'dev');
    expect(screen.getByTestId('user-select-option-3')).toBeInTheDocument();
    expect(screen.queryByTestId('user-select-option-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-select-option-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-select-option-4')).not.toBeInTheDocument();
  });

  it('filters by email substring (case-insensitive)', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'BOB@');
    expect(screen.getByTestId('user-select-option-2')).toBeInTheDocument();
    expect(screen.queryByTestId('user-select-option-1')).not.toBeInTheDocument();
  });

  it('shows empty-state message when no users match', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'xyz');
    const empty = screen.getByTestId('user-select-empty');
    expect(empty).toBeInTheDocument();
    expect(empty.textContent).toMatch(/xyz/);
    expect(empty.textContent).toMatch(/No users match/i);
  });

  it('calls onChange when an option is mouseDown-ed', () => {
    const { onChange } = renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByTestId('user-select-option-3'));
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('keyboard: ArrowDown + Enter selects an option', async () => {
    const user = userEvent.setup();
    const { onChange } = renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    // highlight 0 = Alice; ArrowDown twice -> Carol (id 3)
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('keyboard: Escape closes the panel', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    expect(screen.getByTestId('user-select-listbox')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByTestId('user-select-listbox')).not.toBeInTheDocument();
  });

  it('click-outside closes the panel', () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    expect(screen.getByTestId('user-select-listbox')).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId('user-select-listbox')).not.toBeInTheDocument();
  });

  it('shows the loading state while the query is in flight', async () => {
    vi.mocked(usersApi.getAll).mockReturnValueOnce(
      new Promise(() => {}) as never
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <UserSelect value={null} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => {
      expect(screen.getByTestId('user-select-loading')).toBeInTheDocument();
    });
  });

  it('fetches with page=1 and size=100', async () => {
    vi.mocked(usersApi.getAll).mockResolvedValueOnce({
      items: users,
      total: users.length,
      page: 1,
      size: 100,
      pages: 1,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <UserSelect value={null} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    await waitFor(() => {
      expect(usersApi.getAll).toHaveBeenCalledWith(1, 100);
    });
  });

  // ----- clearable -----------------------------------------------
  describe('clearable', () => {
    it('default (clearable=false): no clear option is rendered', () => {
      renderSelect();
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      expect(screen.queryByTestId('user-select-clear')).not.toBeInTheDocument();
    });

    it('clearable=true: dropdown shows the "All users" clear option at the top', () => {
      renderSelect({ clearable: true });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      const clear = screen.getByTestId('user-select-clear');
      expect(clear).toBeInTheDocument();
      expect(clear.textContent).toMatch(/All users/i);
    });

    it('clearable=true: custom clearLabel is rendered', () => {
      renderSelect({ clearable: true, clearLabel: 'Anyone' });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      expect(screen.getByTestId('user-select-clear').textContent).toMatch(/Anyone/);
    });

    it('clearable=true: clicking clear option calls onChange(null)', () => {
      const { onChange } = renderSelect({ clearable: true, value: 3 });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      fireEvent.mouseDown(screen.getByTestId('user-select-clear'));
      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('clearable=true: null value renders an empty input (placeholder visible)', () => {
      renderSelect({ clearable: true, value: null, placeholder: 'All users' });
      const input = screen.getByRole('combobox') as HTMLInputElement;
      expect(input.value).toBe('');
      expect(input.placeholder).toBe('All users');
    });

    it('clearable=true: Enter on clear option (default highlight) calls onChange(null)', async () => {
      const user = userEvent.setup();
      const { onChange } = renderSelect({ clearable: true, value: null });
      const input = screen.getByRole('combobox');
      await user.click(input);
      await user.keyboard('{Enter}');
      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('clearable=true: ArrowDown past clear, Enter selects user', async () => {
      const user = userEvent.setup();
      const { onChange } = renderSelect({ clearable: true, value: null });
      const input = screen.getByRole('combobox');
      await user.click(input);
      // highlight 0 = clear; ArrowDown -> highlight 1 = Alice (id 1).
      await user.keyboard('{ArrowDown}{Enter}');
      expect(onChange).toHaveBeenCalledWith(1);
    });

    it('clearable=true: empty-state still shows when no matches; clear remains', async () => {
      const user = userEvent.setup();
      renderSelect({ clearable: true });
      const input = screen.getByRole('combobox');
      await user.click(input);
      await user.type(input, 'xyz');
      expect(screen.getByTestId('user-select-clear')).toBeInTheDocument();
      expect(screen.getByTestId('user-select-empty')).toBeInTheDocument();
    });
  });
});
