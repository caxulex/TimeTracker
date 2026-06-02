import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TeamSelect } from '../TeamSelect';
import type { Team, TeamMember } from '../../../types';

vi.mock('../../../api/client', () => ({
  teamsApi: {
    getAll: vi.fn(),
    getById: vi.fn(),
  },
}));

import { teamsApi } from '../../../api/client';

const makeTeam = (overrides: Partial<Team>): Team =>
  ({
    id: 1,
    name: 'Team',
    owner_id: 1,
    created_at: new Date().toISOString(),
    member_count: 1,
    ...overrides,
  }) as Team;

const teams: Team[] = [
  makeTeam({ id: 1, name: 'Engineering' }),
  makeTeam({ id: 2, name: 'Sales' }),
  makeTeam({ id: 3, name: 'Development' }),
];

function renderSelect(props: Partial<React.ComponentProps<typeof TeamSelect>> = {}) {
  const onChange = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <TeamSelect
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        placeholder={props.placeholder ?? 'Select team'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange };
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('TeamSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(teamsApi.getAll).mockResolvedValue({
      items: teams,
      total: teams.length,
      page: 1,
      size: 20,
      pages: 1,
    });
    vi.mocked(teamsApi.getById).mockImplementation(async (id: number) => {
      const team = teams.find((t) => t.id === id);
      if (!team) throw new Error('team not found');
      return { ...team, members: [] as TeamMember[] };
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('with value=null does not fire search until dropdown opens', () => {
    renderSelect({ value: null });
    expect(teamsApi.getAll).not.toHaveBeenCalled();
  });

  it('with value set fetches by id and shows selected name', async () => {
    renderSelect({ value: 3 });
    await waitFor(() => {
      expect(teamsApi.getById).toHaveBeenCalledWith(3);
      expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Development');
    });
  });

  it('open dropdown fires request without search', async () => {
    renderSelect();
    fireEvent.focus(screen.getByRole('combobox'));
    await waitFor(() => {
      expect(teamsApi.getAll).toHaveBeenCalledWith({ page: 1, page_size: 20, search: undefined });
    });
  });

  it('debounces search request by 250ms', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => expect(teamsApi.getAll).toHaveBeenCalled());
    vi.mocked(teamsApi.getAll).mockClear();

    fireEvent.change(input, { target: { value: 'dev' } });
    await sleep(200);
    expect(teamsApi.getAll).not.toHaveBeenCalled();

    await sleep(120);
    await waitFor(() => {
      expect(teamsApi.getAll).toHaveBeenCalledWith({ page: 1, page_size: 20, search: 'dev' });
    });
  });

  it('rapid typing only sends one final debounced search', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => expect(teamsApi.getAll).toHaveBeenCalled());
    vi.mocked(teamsApi.getAll).mockClear();

    fireEvent.change(input, { target: { value: 'd' } });
    await sleep(200);
    fireEvent.change(input, { target: { value: 'de' } });
    await sleep(280);

    await waitFor(() => expect(teamsApi.getAll).toHaveBeenCalledTimes(1));
    expect(teamsApi.getAll).toHaveBeenCalledWith({ page: 1, page_size: 20, search: 'de' });
  });

  it('selecting option closes dropdown and calls onChange with id', async () => {
    const { onChange } = renderSelect();
    fireEvent.focus(screen.getByRole('combobox'));
    const option = await screen.findByTestId('team-select-option-3');
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(3);
    expect(screen.queryByTestId('team-select-listbox')).not.toBeInTheDocument();
  });

  it('selected value still displays when current search results do not include it', async () => {
    vi.mocked(teamsApi.getAll)
      .mockResolvedValueOnce({
        items: teams,
        total: teams.length,
        page: 1,
        size: 20,
        pages: 1,
      })
      .mockResolvedValueOnce({
        items: [teams[0]],
        total: 1,
        page: 1,
        size: 20,
        pages: 1,
      });

    renderSelect({ value: 3 });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    fireEvent.focus(input);
    await waitFor(() => expect(teamsApi.getAll).toHaveBeenCalled());

    fireEvent.change(input, { target: { value: 'eng' } });
    await sleep(320);
    await screen.findByTestId('team-select-option-1');

    fireEvent.keyDown(input, { key: 'Escape' });
    await waitFor(() => expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Development'));
  });

  it('pre-fed teams mode skips server search and filters locally', async () => {
    const user = userEvent.setup();
    renderSelect({ teams, value: null });
    const input = screen.getByRole('combobox');

    await user.click(input);
    await user.type(input, 'dev');

    expect(teamsApi.getAll).not.toHaveBeenCalled();
    expect(screen.getByTestId('team-select-option-3')).toBeInTheDocument();
    expect(screen.queryByTestId('team-select-option-1')).not.toBeInTheDocument();
  });
});
