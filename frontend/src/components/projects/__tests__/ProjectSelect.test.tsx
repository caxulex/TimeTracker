import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectSelect } from '../ProjectSelect';
import type { Project } from '../../../types';

vi.mock('../../../api/client', () => ({
  projectsApi: {
    getAll: vi.fn(),
    getById: vi.fn(),
  },
}));

import { projectsApi } from '../../../api/client';

const makeProject = (overrides: Partial<Project>): Project =>
  ({
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
  }) as Project;

const projects: Project[] = [
  makeProject({ id: 1, name: 'Alpha', color: '#FF0000' }),
  makeProject({ id: 2, name: 'Bravo', color: '#00FF00' }),
  makeProject({ id: 3, name: 'Development', color: '#0000FF' }),
];

const prefetchedProjects: Project[] = Array.from({ length: 100 }, (_, index) => {
  const id = index + 21;
  return makeProject({
    id,
    name: `Prefetched ${id}`,
    color: '#64748B',
  });
});

const smcProject = makeProject({
  id: 20,
  name: 'SMC Automations',
  color: '#F97316',
});

function renderSelect(props: Partial<React.ComponentProps<typeof ProjectSelect>> = {}) {
  const onChange = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ProjectSelect
        value={props.value ?? null}
        onChange={props.onChange ?? onChange}
        placeholder={props.placeholder ?? 'Select project'}
        {...props}
      />
    </QueryClientProvider>
  );
  return { ...utils, onChange };
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('ProjectSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(projectsApi.getAll).mockResolvedValue({
      items: projects,
      total: projects.length,
      page: 1,
      size: 20,
      pages: 1,
    });
    vi.mocked(projectsApi.getById).mockImplementation(async (id: number) => {
      const project = projects.find((p) => p.id === id);
      if (!project) throw new Error('project not found');
      return project;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('with value=null does not fire search until dropdown opens', () => {
    renderSelect({ value: null });
    expect(projectsApi.getAll).not.toHaveBeenCalled();
  });

  it('with value set fetches by id and shows selected name', async () => {
    renderSelect({ value: 3 });
    await waitFor(() => {
      expect(projectsApi.getById).toHaveBeenCalledWith(3);
      expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Development');
    });
  });

  it('open dropdown fires top-20 request without search', async () => {
    renderSelect();
    fireEvent.focus(screen.getByRole('combobox'));
    await waitFor(() => {
      expect(projectsApi.getAll).toHaveBeenCalledWith({
        include_archived: false,
        page_size: 20,
        search: undefined,
      });
    });
  });

  it('with projects prop and no typing, renders the prefetched list without server search', async () => {
    renderSelect({ projects: prefetchedProjects, value: null });

    await userEvent.click(screen.getByRole('combobox'));

    expect(projectsApi.getAll).not.toHaveBeenCalled();
    expect(screen.getByTestId('project-select-option-21')).toBeInTheDocument();
    expect(screen.getByTestId('project-select-option-120')).toBeInTheDocument();
  });

  it('with projects prop and typing, fires server search and shows the server result', async () => {
    vi.mocked(projectsApi.getAll).mockImplementation(async (filters?: { search?: string }) => {
      if (filters?.search === 'SMC') {
        return {
          items: [smcProject],
          total: 1,
          page: 1,
          size: 20,
          pages: 1,
        };
      }

      return {
        items: prefetchedProjects,
        total: prefetchedProjects.length,
        page: 1,
        size: 20,
        pages: 5,
      };
    });

    renderSelect({ projects: prefetchedProjects, value: null });
    const input = screen.getByRole('combobox');

    await userEvent.click(input);
    await userEvent.type(input, 'SMC');

    await sleep(320);
    await waitFor(() => {
      expect(projectsApi.getAll).toHaveBeenCalledWith({
        include_archived: false,
        page_size: 20,
        search: 'SMC',
      });
    });
    expect(screen.getByTestId('project-select-option-20')).toBeInTheDocument();
    expect(screen.getByText('SMC Automations')).toBeInTheDocument();
  });

  it('fires debounced server search after 250ms', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => expect(projectsApi.getAll).toHaveBeenCalled());
    vi.mocked(projectsApi.getAll).mockClear();

    fireEvent.change(input, { target: { value: 'dev' } });
    await sleep(200);
    expect(projectsApi.getAll).not.toHaveBeenCalled();

    await sleep(120);
    await waitFor(() => {
      expect(projectsApi.getAll).toHaveBeenCalledWith({
        include_archived: false,
        page_size: 20,
        search: 'dev',
      });
    });
  });

  it('rapid typing only issues final debounced request', async () => {
    renderSelect();
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    await waitFor(() => expect(projectsApi.getAll).toHaveBeenCalled());
    vi.mocked(projectsApi.getAll).mockClear();

    fireEvent.change(input, { target: { value: 'd' } });
    await sleep(200);
    fireEvent.change(input, { target: { value: 'de' } });
    await sleep(100);
    expect(projectsApi.getAll).not.toHaveBeenCalled();

    await sleep(180);
    await waitFor(() => expect(projectsApi.getAll).toHaveBeenCalledTimes(1));
    expect(projectsApi.getAll).toHaveBeenCalledWith({
      include_archived: false,
      page_size: 20,
      search: 'de',
    });
  });

  it('selection closes dropdown and calls onChange with id', async () => {
    const user = userEvent.setup();
    const { onChange } = renderSelect();
    await user.click(screen.getByRole('combobox'));
    const option = await screen.findByTestId('project-select-option-3');
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(3);
    expect(screen.queryByTestId('project-select-listbox')).not.toBeInTheDocument();
  });

  it('selected value still displays even when current search result set does not include it', async () => {
    vi.mocked(projectsApi.getAll)
      .mockResolvedValueOnce({
        items: projects,
        total: projects.length,
        page: 1,
        size: 20,
        pages: 1,
      })
      .mockResolvedValueOnce({
        items: [projects[0]],
        total: 1,
        page: 1,
        size: 20,
        pages: 1,
      });

    renderSelect({ value: 3 });
    const input = screen.getByRole('combobox') as HTMLInputElement;

    fireEvent.focus(input);
    await waitFor(() => expect(projectsApi.getAll).toHaveBeenCalled());

    fireEvent.change(input, { target: { value: 'alp' } });
    await sleep(320);
    await waitFor(() => expect(screen.getByTestId('project-select-option-1')).toBeInTheDocument());

    fireEvent.keyDown(input, { key: 'Escape' });
    await waitFor(() => expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Development'));
  });

  it('pre-fed list mode shows the provided projects when search is empty', async () => {
    const user = userEvent.setup();
    renderSelect({ projects, value: null });
    const input = screen.getByRole('combobox');

    await user.click(input);

    expect(projectsApi.getAll).not.toHaveBeenCalled();
    expect(screen.getByTestId('project-select-option-3')).toBeInTheDocument();
    expect(screen.getByTestId('project-select-option-1')).toBeInTheDocument();
  });
});
