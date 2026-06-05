import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import { ProjectsPage } from '../ProjectsPage';

const projectsGetAll = vi.fn();
const projectsUpdate = vi.fn();
const projectsArchive = vi.fn();
const projectsDeletePreview = vi.fn();
const projectsDelete = vi.fn();
const projectsMerge = vi.fn();
const projectsAddTeam = vi.fn();
const teamsGetAll = vi.fn();

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'User', email: 'u@example.com', role: 'regular_user' },
    isAuthenticated: true,
  }),
}));

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({ addNotification: vi.fn() }),
}));

vi.mock('../../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: false }),
}));

vi.mock('../../components/ai/ProjectHealthCard', () => ({
  default: () => null,
}));

vi.mock('../../api/client', () => ({
  projectsApi: {
    getAll: (...args: unknown[]) => projectsGetAll(...args),
    update: (...args: unknown[]) => projectsUpdate(...args),
    archive: (...args: unknown[]) => projectsArchive(...args),
    deletePreview: (...args: unknown[]) => projectsDeletePreview(...args),
    delete: (...args: unknown[]) => projectsDelete(...args),
    merge: (...args: unknown[]) => projectsMerge(...args),
    addTeam: (...args: unknown[]) => projectsAddTeam(...args),
    create: vi.fn(),
    restore: vi.fn(),
    removeTeam: vi.fn(),
    listTeams: vi.fn(),
    mergePreview: vi.fn(),
  },
  teamsApi: {
    getAll: (...args: unknown[]) => teamsGetAll(...args),
  },
}));

const makeProject = (id: number, name: string, archived = false) => ({
  id,
  name,
  description: 'desc',
  color: '#3B82F6',
  team_id: 1,
  team_name: 'Team',
  team_associations: [
    {
      team_id: 1,
      team_name: 'Team',
      is_primary: true,
      added_by_name: null,
      added_at: '2026-01-01T00:00:00Z',
    },
  ],
  is_archived: archived,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
  task_count: 5,
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProjectsPage per-project actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    teamsGetAll.mockResolvedValue({
      items: [{ id: 1, name: 'Team' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    projectsGetAll.mockResolvedValue({
      items: [
        makeProject(1, 'Source Project'),
        makeProject(2, 'Target Project'),
        makeProject(3, 'Archived Target', true),
      ],
      total: 3,
      page: 1,
      page_size: 50,
      pages: 1,
    });

    projectsUpdate.mockResolvedValue(makeProject(1, 'Edited Project'));
    projectsArchive.mockImplementation((id: number, isArchived: boolean) =>
      Promise.resolve(makeProject(id, id === 1 ? 'Source Project' : 'Target Project', isArchived))
    );
    projectsDeletePreview.mockResolvedValue({ tasks: 381, entries: 1247 });
    projectsDelete.mockResolvedValue({ deleted_tasks: 381, deleted_entries: 1247 });
    projectsMerge.mockResolvedValue({ moved_tasks: 5, moved_entries: 12, renamed_tasks: [], archived_source: true });
    projectsAddTeam.mockResolvedValue({ message: 'ok' });
  });

  it('opens kebab menu on click', async () => {
    const user = userEvent.setup();
    renderPage();

    const buttons = await screen.findAllByTestId('project-kebab-button');
    await user.click(buttons[0]);

    expect(await screen.findByTestId('project-kebab-menu')).toBeInTheDocument();
    expect(screen.getByText('Edit')).toBeInTheDocument();
    expect(screen.getByText('Archive')).toBeInTheDocument();
    expect(screen.getByText('Merge with...')).toBeInTheDocument();
    expect(screen.getByText('Delete')).toBeInTheDocument();
  });

  it('edit modal pre-populates and submits updates', async () => {
    const user = userEvent.setup();
    renderPage();

    const buttons = await screen.findAllByTestId('project-kebab-button');
    await user.click(buttons[0]);
    const menu = await screen.findByTestId('project-kebab-menu');
    await user.click(within(menu).getByText('Edit'));

    const nameInput = await screen.findByDisplayValue('Source Project');
    expect(nameInput).toHaveValue('Source Project');

    await user.clear(nameInput);
    await user.type(nameInput, 'Source Project Renamed');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(projectsUpdate).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ name: 'Source Project Renamed' })
      );
    });
  });

  it('archive confirmation appears and archived projects expose Unarchive', async () => {
    const user = userEvent.setup();
    renderPage();

    const buttons = await screen.findAllByTestId('project-kebab-button');
    await user.click(buttons[0]);
    await user.click(screen.getByText('Archive'));

    expect(await screen.findByText(/Archive "Source Project"/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Archive' }));

    await waitFor(() => {
      expect(projectsArchive).toHaveBeenCalledWith(1, true);
    });

    await user.click(screen.getByRole('button', { name: /show archived/i }));

    const archivedMenuButton = (await screen.findAllByTestId('project-kebab-button'))[0];
    await user.click(archivedMenuButton);
    expect(await screen.findByText('Unarchive')).toBeInTheDocument();
  });

  it('delete modal shows counts and requires exact name before enabling delete', async () => {
    const user = userEvent.setup();
    renderPage();

    const buttons = await screen.findAllByTestId('project-kebab-button');
    await user.click(buttons[0]);
    await user.click(screen.getByText('Delete'));

    const modal = await screen.findByRole('dialog');
    expect(modal).toHaveTextContent(/381\s*tasks/);
    expect(modal).toHaveTextContent(/1247\s*time entries/);

    const submit = screen.getByTestId('delete-project-submit');
    expect(submit).toBeDisabled();

    await user.type(screen.getByTestId('delete-project-confirm-name'), 'Source Project');
    expect(submit).toBeEnabled();

    await user.click(submit);
    await waitFor(() => {
      expect(projectsDelete).toHaveBeenCalledWith(1);
    });
  });

  it('merge modal excludes source and archived targets and submits merge', async () => {
    const user = userEvent.setup();
    renderPage();

    const buttons = await screen.findAllByTestId('project-kebab-button');
    await user.click(buttons[0]);
    await user.click(screen.getByText('Merge with...'));

    expect(await screen.findByTestId('merge-target-search')).toBeInTheDocument();
    expect(screen.queryByTestId('merge-target-option-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('merge-target-option-3')).not.toBeInTheDocument();
    expect(screen.getByTestId('merge-target-option-2')).toBeInTheDocument();

    await user.click(screen.getByTestId('merge-project-submit'));

    await waitFor(() => {
      expect(projectsMerge).toHaveBeenCalledWith(1, { target_project_id: 2 });
    });
  });
});
