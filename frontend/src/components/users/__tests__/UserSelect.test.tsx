import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserSelect } from '../UserSelect';
import type { User } from '../../../types';

vi.mock('../../../api/client', () => ({
  usersApi: {
    getAll: vi.fn(),
    getById: vi.fn(),
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
];

function renderSelect(props: Partial<React.ComponentProps<typeof UserSelect>> = {}) {
  const onChange = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <UserSelect
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        placeholder={props.placeholder ?? 'Select user'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange };
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('UserSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usersApi.getAll).mockResolvedValue({
      items: users,
      total: users.length,
      page: 1,
      size: 20,
      pages: 1,
    });
    vi.mocked(usersApi.getById).mockImplementation(async (id: number) => {
      const user = users.find((u) => u.id === id);
      if (!user) throw new Error('user not found');
      return user;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('with value=null does not fire search until dropdown opens', () => {
    renderSelect({ value: null });
    expect(usersApi.getAll).not.toHaveBeenCalled();
  });

  it('with value set fetches by id and shows selected name', async () => {
    renderSelect({ value: 3 });
    await waitFor(() => {
      expect(usersApi.getById).toHaveBeenCalledWith(3);
      expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Carol Developer');
    });
  });

  it('open dropdown fires request without search', async () => {
    renderSelect();
    fireEvent.focus(screen.getByRole('combobox'));
    await waitFor(() => {
      expect(usersApi.getAll).toHaveBeenCalledWith({ page: 1, page_size: 20, search: undefined });
    });
  });

  it('debounces search request by 250ms', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => expect(usersApi.getAll).toHaveBeenCalled());
    vi.mocked(usersApi.getAll).mockClear();

    fireEvent.change(input, { target: { value: 'bob' } });
    await sleep(200);
    expect(usersApi.getAll).not.toHaveBeenCalled();

    await sleep(120);
    await waitFor(() => {
      expect(usersApi.getAll).toHaveBeenCalledWith({ page: 1, page_size: 20, search: 'bob' });
    });
  });

  it('rapid typing only sends one final debounced search', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => expect(usersApi.getAll).toHaveBeenCalled());
    vi.mocked(usersApi.getAll).mockClear();

    fireEvent.change(input, { target: { value: 'b' } });
    await sleep(200);
    fireEvent.change(input, { target: { value: 'bo' } });
    await sleep(280);

    await waitFor(() => expect(usersApi.getAll).toHaveBeenCalledTimes(1));
    expect(usersApi.getAll).toHaveBeenCalledWith({ page: 1, page_size: 20, search: 'bo' });
  });

  it('selecting an option closes dropdown and calls onChange with id', async () => {
    const { onChange } = renderSelect();
    fireEvent.focus(screen.getByRole('combobox'));
    const option = await screen.findByTestId('user-select-option-3');
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(3);
    expect(screen.queryByTestId('user-select-listbox')).not.toBeInTheDocument();
  });

  it('selected value still displays when current search results do not include it', async () => {
    vi.mocked(usersApi.getAll)
      .mockResolvedValueOnce({
        items: users,
        total: users.length,
        page: 1,
        size: 20,
        pages: 1,
      })
      .mockResolvedValueOnce({
        items: [users[0]],
        total: 1,
        page: 1,
        size: 20,
        pages: 1,
      });

    renderSelect({ value: 3 });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    fireEvent.focus(input);
    await waitFor(() => expect(usersApi.getAll).toHaveBeenCalled());

    fireEvent.change(input, { target: { value: 'alice' } });
    await sleep(320);
    await screen.findByTestId('user-select-option-1');

    fireEvent.keyDown(input, { key: 'Escape' });
    await waitFor(() => expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Carol Developer'));
  });

  it('pre-fed users mode skips server search and filters locally', async () => {
    const user = userEvent.setup();
    renderSelect({ users, value: null });
    const input = screen.getByRole('combobox');

    await user.click(input);
    await user.type(input, 'carol');

    expect(usersApi.getAll).not.toHaveBeenCalled();
    expect(screen.getByTestId('user-select-option-3')).toBeInTheDocument();
    expect(screen.queryByTestId('user-select-option-1')).not.toBeInTheDocument();
  });
});
