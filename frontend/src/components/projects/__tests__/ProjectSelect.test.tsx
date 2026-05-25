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
});
