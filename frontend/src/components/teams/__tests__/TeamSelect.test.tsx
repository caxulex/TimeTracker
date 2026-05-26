// ============================================
// TIME TRACKER - TEAM SELECT TESTS
// Mirrors ProjectSelect.test.tsx — covers the typeahead combobox
// introduced in feat/user-team-select-typeahead.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TeamSelect } from '../TeamSelect';
import type { Team } from '../../../types';

vi.mock('../../../api/client', () => ({
  teamsApi: {
    getAll: vi.fn(),
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
  makeTeam({ id: 4, name: 'Other' }),
];

function renderSelect(
  props: Partial<React.ComponentProps<typeof TeamSelect>> = {}
) {
  const onChange = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <TeamSelect
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        teams={props.teams ?? teams}
        placeholder={props.placeholder ?? 'Select team'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange };
}

describe('TeamSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the currently-selected team name in the input', () => {
    renderSelect({ value: 3 });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    expect(input.value).toBe('Development');
  });

  it('opens the dropdown on focus and renders all teams', () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    expect(screen.getByTestId('team-select-listbox')).toBeInTheDocument();
    expect(screen.getByTestId('team-select-option-1')).toBeInTheDocument();
    expect(screen.getByTestId('team-select-option-2')).toBeInTheDocument();
    expect(screen.getByTestId('team-select-option-3')).toBeInTheDocument();
    expect(screen.getByTestId('team-select-option-4')).toBeInTheDocument();
  });

  it('filters as the user types (case-insensitive substring)', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'dev');
    expect(screen.getByTestId('team-select-option-3')).toBeInTheDocument();
    expect(screen.queryByTestId('team-select-option-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('team-select-option-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('team-select-option-4')).not.toBeInTheDocument();
  });

  it('shows empty-state message when no teams match', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'xyz');
    const empty = screen.getByTestId('team-select-empty');
    expect(empty).toBeInTheDocument();
    expect(empty.textContent).toMatch(/xyz/);
    expect(empty.textContent).toMatch(/No teams match/i);
  });

  it('calls onChange when an option is mouseDown-ed', () => {
    const { onChange } = renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByTestId('team-select-option-3'));
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('keyboard: ArrowDown + Enter selects an option', async () => {
    const user = userEvent.setup();
    const { onChange } = renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('keyboard: Escape closes the panel', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    expect(screen.getByTestId('team-select-listbox')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByTestId('team-select-listbox')).not.toBeInTheDocument();
  });

  it('click-outside closes the panel', () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    expect(screen.getByTestId('team-select-listbox')).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId('team-select-listbox')).not.toBeInTheDocument();
  });

  it('shows the loading state while the query is in flight', async () => {
    vi.mocked(teamsApi.getAll).mockReturnValueOnce(
      new Promise(() => {}) as never
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <TeamSelect value={null} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => {
      expect(screen.getByTestId('team-select-loading')).toBeInTheDocument();
    });
  });

  it('fetches with page=1 and size=100', async () => {
    vi.mocked(teamsApi.getAll).mockResolvedValueOnce({
      items: teams,
      total: teams.length,
      page: 1,
      size: 100,
      pages: 1,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <TeamSelect value={null} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    await waitFor(() => {
      expect(teamsApi.getAll).toHaveBeenCalledWith(1, 100);
    });
  });

  // ----- clearable -----------------------------------------------
  describe('clearable', () => {
    it('default (clearable=false): no clear option is rendered', () => {
      renderSelect();
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      expect(screen.queryByTestId('team-select-clear')).not.toBeInTheDocument();
    });

    it('clearable=true: dropdown shows the "All teams" clear option at the top', () => {
      renderSelect({ clearable: true });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      const clear = screen.getByTestId('team-select-clear');
      expect(clear).toBeInTheDocument();
      expect(clear.textContent).toMatch(/All teams/i);
    });

    it('clearable=true: custom clearLabel is rendered', () => {
      renderSelect({
        clearable: true,
        clearLabel: '(Default: lowest-id team)',
      });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      expect(screen.getByTestId('team-select-clear').textContent).toMatch(
        /Default: lowest-id team/
      );
    });

    it('clearable=true: clicking clear option calls onChange(null)', () => {
      const { onChange } = renderSelect({ clearable: true, value: 3 });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      fireEvent.mouseDown(screen.getByTestId('team-select-clear'));
      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('clearable=true: null value renders an empty input (placeholder visible)', () => {
      renderSelect({ clearable: true, value: null, placeholder: 'All teams' });
      const input = screen.getByRole('combobox') as HTMLInputElement;
      expect(input.value).toBe('');
      expect(input.placeholder).toBe('All teams');
    });

    it('clearable=true: Enter on clear (default highlight) calls onChange(null)', async () => {
      const user = userEvent.setup();
      const { onChange } = renderSelect({ clearable: true, value: null });
      const input = screen.getByRole('combobox');
      await user.click(input);
      await user.keyboard('{Enter}');
      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('clearable=true: ArrowDown past clear, Enter selects team', async () => {
      const user = userEvent.setup();
      const { onChange } = renderSelect({ clearable: true, value: null });
      const input = screen.getByRole('combobox');
      await user.click(input);
      await user.keyboard('{ArrowDown}{Enter}');
      expect(onChange).toHaveBeenCalledWith(1);
    });
  });
});
