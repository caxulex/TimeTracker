// ============================================
// TIME TRACKER - PROJECT SELECT TESTS
// Covers the typeahead combobox introduced in
// fix/project-selectors-typeahead-and-pagination.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectSelect } from '../ProjectSelect';
import type { Project } from '../../../types';

vi.mock('../../../api/client', () => ({
  projectsApi: {
    getAll: vi.fn(),
  },
}));

import { projectsApi } from '../../../api/client';

const makeProject = (overrides: Partial<Project>): Project => ({
  id: 1,
  name: 'Project',
  description: null,
  team_id: 1,
  team_name: 'Team',
  color: '#3B82F6',
  is_archived: false,
  created_at: new Date().toISOString(),
  updated_at: null,
  task_count: 0,
  ...overrides,
} as Project);

const projects: Project[] = [
  makeProject({ id: 1, name: 'Alpha', color: '#FF0000' }),
  makeProject({ id: 2, name: 'Bravo', color: '#00FF00' }),
  makeProject({ id: 3, name: 'Development', color: '#0000FF' }),
  makeProject({ id: 4, name: 'Other thing', color: '#FFFF00' }),
];

function renderSelect(props: Partial<React.ComponentProps<typeof ProjectSelect>> = {}) {
  const onChange = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ProjectSelect
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        projects={props.projects ?? projects}
        placeholder={props.placeholder ?? 'Select project'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange };
}

describe('ProjectSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the currently-selected project name in the input', () => {
    renderSelect({ value: 3 });
    const input = screen.getByRole('combobox') as HTMLInputElement;
    expect(input.value).toBe('Development');
    // Colored dot for the selected project should be present
    expect(screen.getByTestId('project-select-dot')).toBeInTheDocument();
  });

  it('opens the dropdown on focus', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    expect(screen.getByTestId('project-select-listbox')).toBeInTheDocument();
    // All four projects render as options
    expect(screen.getByTestId('project-select-option-1')).toBeInTheDocument();
    expect(screen.getByTestId('project-select-option-2')).toBeInTheDocument();
    expect(screen.getByTestId('project-select-option-3')).toBeInTheDocument();
    expect(screen.getByTestId('project-select-option-4')).toBeInTheDocument();
  });

  it('filters options as the user types (case-insensitive substring)', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);

    await user.type(input, 'dev');
    // "Development" matches, others do not
    expect(screen.getByTestId('project-select-option-3')).toBeInTheDocument();
    expect(screen.queryByTestId('project-select-option-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('project-select-option-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('project-select-option-4')).not.toBeInTheDocument();
  });

  it('case-insensitive: uppercase query still matches', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'DEV');
    expect(screen.getByTestId('project-select-option-3')).toBeInTheDocument();
  });

  it('shows empty-state message when no projects match', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'xyz');
    const empty = screen.getByTestId('project-select-empty');
    expect(empty).toBeInTheDocument();
    expect(empty.textContent).toMatch(/xyz/);
    expect(empty.textContent).toMatch(/No projects match/i);
  });

  it('calls onChange when an option is clicked', async () => {
    const { onChange } = renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    const option = screen.getByTestId('project-select-option-3');
    // ProjectSelect commits on mousedown so blur/click race is safe.
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('keyboard: ArrowDown + Enter selects an option', async () => {
    const user = userEvent.setup();
    const { onChange } = renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    // Highlight starts at index 0 (Alpha). ArrowDown twice -> Development (idx 2).
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it('keyboard: Escape closes the panel', async () => {
    const user = userEvent.setup();
    renderSelect();
    const input = screen.getByRole('combobox');
    await user.click(input);
    expect(screen.getByTestId('project-select-listbox')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByTestId('project-select-listbox')).not.toBeInTheDocument();
  });

  it('click-outside closes the panel', () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    expect(screen.getByTestId('project-select-listbox')).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId('project-select-listbox')).not.toBeInTheDocument();
  });

  it('shows the loading state while the query is in flight', async () => {
    // Don't pass `projects` prop so the component drives its own query.
    // Returning an unresolved promise keeps the query in flight.
    vi.mocked(projectsApi.getAll).mockReturnValueOnce(new Promise(() => {}));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectSelect value={null} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => {
      expect(screen.getByTestId('project-select-loading')).toBeInTheDocument();
    });
  });

  it('fetches with include_archived=false and page_size=100', async () => {
    vi.mocked(projectsApi.getAll).mockResolvedValueOnce({
      items: projects,
      total: projects.length,
      page: 1,
      size: 100,
      pages: 1,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectSelect value={null} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    await waitFor(() => {
      expect(projectsApi.getAll).toHaveBeenCalledWith({
        include_archived: false,
        page_size: 100,
      });
    });
  });

  // ----- clearable -----------------------------------------------
  describe('clearable', () => {
    it('default (clearable=false): no clear option is rendered', () => {
      renderSelect();
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      expect(screen.queryByTestId('project-select-clear')).not.toBeInTheDocument();
    });

    it('clearable=true: dropdown shows the "All projects" clear option at the top', () => {
      renderSelect({ clearable: true });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      const clear = screen.getByTestId('project-select-clear');
      expect(clear).toBeInTheDocument();
      expect(clear.textContent).toMatch(/All projects/i);
    });

    it('clearable=true: custom clearLabel is rendered', () => {
      renderSelect({ clearable: true, clearLabel: 'Any project' });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      expect(screen.getByTestId('project-select-clear').textContent).toMatch(
        /Any project/
      );
    });

    it('clearable=true: clicking clear option calls onChange(null)', () => {
      const { onChange } = renderSelect({ clearable: true, value: 3 });
      const input = screen.getByRole('combobox');
      fireEvent.focus(input);
      fireEvent.mouseDown(screen.getByTestId('project-select-clear'));
      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('clearable=true: null value renders an empty input (placeholder visible)', () => {
      renderSelect({ clearable: true, value: null, placeholder: 'All projects' });
      const input = screen.getByRole('combobox') as HTMLInputElement;
      expect(input.value).toBe('');
      expect(input.placeholder).toBe('All projects');
    });

    it('clearable=true: keyboard nav Enter on clear option calls onChange(null)', async () => {
      const user = userEvent.setup();
      const { onChange } = renderSelect({ clearable: true, value: null });
      const input = screen.getByRole('combobox');
      await user.click(input);
      // With no selection, default highlight should be the clear
      // option (index 0). Enter commits it.
      await user.keyboard('{Enter}');
      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('clearable=true: ArrowDown moves past clear into projects, Enter selects project', async () => {
      const user = userEvent.setup();
      const { onChange } = renderSelect({ clearable: true, value: null });
      const input = screen.getByRole('combobox');
      await user.click(input);
      // highlight 0 = clear. ArrowDown -> highlight 1 = Alpha (id 1).
      await user.keyboard('{ArrowDown}{Enter}');
      expect(onChange).toHaveBeenCalledWith(1);
    });

    it('clearable=true: still renders project options when query has no matches', async () => {
      const user = userEvent.setup();
      renderSelect({ clearable: true });
      const input = screen.getByRole('combobox');
      await user.click(input);
      await user.type(input, 'xyz');
      // Clear is still reachable even when nothing matches.
      expect(screen.getByTestId('project-select-clear')).toBeInTheDocument();
      expect(screen.getByTestId('project-select-empty')).toBeInTheDocument();
    });
  });
});
