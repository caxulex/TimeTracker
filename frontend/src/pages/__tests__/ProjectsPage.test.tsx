import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';

import { ProjectsPage } from '../ProjectsPage';
import { findByRoleReliable, findByTestIdReliable, findByTextReliable, waitForReliable } from '../../test/asyncHelpers';

const projectsGetAll = vi.fn();
const projectsUpdate = vi.fn();
const projectsArchive = vi.fn();
const projectsDeletePreview = vi.fn();
const projectsDelete = vi.fn();
const projectsMerge = vi.fn();
const projectsAddTeam = vi.fn();
const projectsGetSimilar = vi.fn();
const projectsCreate = vi.fn();
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
    getSimilar: (...args: unknown[]) => projectsGetSimilar(...args),
    create: (...args: unknown[]) => projectsCreate(...args),
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

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

function renderPage(initialEntry: string = '/projects') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <ProjectsPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProjectsPage per-project actions', () => {
  const sourceProject = makeProject(1, 'Source Project');
  const targetProject = makeProject(2, 'Target Project');
  const archivedTargetProject = makeProject(3, 'Archived Target', true);

  const openCreateModal = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.click(await screen.findByRole('button', { name: /new project/i }));
    const dialog = await screen.findByRole('dialog', { name: 'New Project' });
    const nameInput = within(dialog).getByPlaceholderText('My Project');
    return { dialog, nameInput };
  };

  const findProjectCard = async (projectId: number) => {
    return waitForReliable(() => {
      const card = screen.queryByTestId(`project-card-${projectId}`);
      if (!card) {
        throw new Error(`Card with id ${projectId} not found in DOM`);
      }
      return card;
    });
  };

  const clickKebabForProject = async (
    user: ReturnType<typeof userEvent.setup>,
    projectId: number
  ) => {
    const card = await findProjectCard(projectId);
    const kebabButton = within(card).getByTestId('project-kebab-button');
    await user.click(kebabButton);
  };

  const clickMenuAction = async (
    user: ReturnType<typeof userEvent.setup>,
    actionLabel: string
  ) => {
    const menu = await screen.findByTestId('project-kebab-menu');
    await user.click(within(menu).getByText(actionLabel));
  };

  const clickActionForProject = async (
    user: ReturnType<typeof userEvent.setup>,
    projectId: number,
    actionLabel: string
  ) => {
    await clickKebabForProject(user, projectId);
    await clickMenuAction(user, actionLabel);
  };

  const openMenuForProject = async (
    user: ReturnType<typeof userEvent.setup>,
    projectId: number
  ) => {
    const card = await findProjectCard(projectId);
    const kebabButton = within(card).getByTestId('project-kebab-button');
    await user.click(kebabButton);
    return screen.findByTestId('project-kebab-menu');
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    teamsGetAll.mockResolvedValue({
      items: [{ id: 1, name: 'Team' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    projectsGetAll.mockResolvedValue({
      // Keep fixture ordering explicit to avoid environment-dependent ambiguity.
      items: [sourceProject, targetProject, archivedTargetProject],
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
    projectsGetSimilar.mockResolvedValue({ matches: [] });
    projectsCreate.mockResolvedValue(makeProject(4, 'Created Project'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('opens kebab menu on click', async () => {
    const user = userEvent.setup();
    renderPage();

    await openMenuForProject(user, 1);

    expect(await screen.findByTestId('project-kebab-menu')).toBeInTheDocument();
    expect(screen.getByText('Edit')).toBeInTheDocument();
    expect(screen.getByText('Archive')).toBeInTheDocument();
    expect(screen.getByText('Merge with...')).toBeInTheDocument();
    expect(screen.getByText('Delete')).toBeInTheDocument();
  });

  it('opens edit modal when ?edit={id} param is present and clears param', async () => {
    renderPage('/projects?edit=2');

    expect(await screen.findByRole('dialog', { name: 'Edit Project' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toBe('');
    });
  });

  it('clears ?edit param after opening the edit modal', async () => {
    renderPage('/projects?edit=1');

    await screen.findByRole('dialog', { name: 'Edit Project' });
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toBe('');
    });
  });

  it('opens delete modal when ?delete={id} param is present', async () => {
    renderPage('/projects?delete=2');

    expect(await screen.findByRole('dialog', { name: 'Delete Project' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toBe('');
    });
  });


  it('renders similar warning when API returns matches', async () => {
    const user = userEvent.setup();
    projectsGetSimilar.mockResolvedValue({
      matches: [
        {
          id: 2,
          name: 'Target Project',
          team_id: 1,
          team_name: 'Team',
          is_archived: false,
          match_type: 'substring',
          match_score: 0.9,
        },
      ],
    });

    renderPage();
    const { nameInput } = await openCreateModal(user);
    await user.type(nameInput, 'Target Project');

    expect(await findByTestIdReliable('similar-projects-warning')).toBeInTheDocument();
    expect(await findByTestIdReliable('similar-project-match-2')).toBeInTheDocument();
  });

  it('hides warning when similar matches are empty', async () => {
    const user = userEvent.setup();
    projectsGetSimilar.mockResolvedValue({ matches: [] });

    renderPage();
    const { nameInput } = await openCreateModal(user);
    await user.type(nameInput, 'Completely New Name');

    await waitForReliable(() => {
      expect(screen.queryByTestId('similar-projects-warning')).not.toBeInTheDocument();
    });
  });

  it('submit-time check shows confirmation modal when matches exist', async () => {
    const user = userEvent.setup();
    projectsGetSimilar
      .mockResolvedValueOnce({
        matches: [
          {
            id: 2,
            name: 'Target Project',
            team_id: 1,
            team_name: 'Team',
            is_archived: false,
            match_type: 'exact',
            match_score: 1.0,
          },
        ],
      })
      .mockResolvedValueOnce({
        matches: [
          {
            id: 2,
            name: 'Target Project',
            team_id: 1,
            team_name: 'Team',
            is_archived: false,
            match_type: 'exact',
            match_score: 1.0,
          },
        ],
      });

    renderPage();
    const { dialog, nameInput } = await openCreateModal(user);
    await user.type(nameInput, 'Target Project');
    await user.click(within(dialog).getByRole('button', { name: 'Create Project' }));

    expect(await findByTextReliable(/Similar projects exist/i)).toBeInTheDocument();
  });

  it('Create anyway submits despite warnings', async () => {
    const user = userEvent.setup();
    projectsGetSimilar.mockResolvedValue({
      matches: [
        {
          id: 2,
          name: 'Target Project',
          team_id: 1,
          team_name: 'Team',
          is_archived: false,
          match_type: 'exact',
          match_score: 1.0,
        },
      ],
    });

    renderPage();
    const { dialog, nameInput } = await openCreateModal(user);
    await user.type(nameInput, 'Target Project');
    await user.click(within(dialog).getByRole('button', { name: 'Create Project' }));
    await user.click(await findByTestIdReliable('create-project-create-anyway'));

    await waitForReliable(() => {
      expect(projectsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Target Project',
          force: true,
          similar_project_ids: [2],
        })
      );
    });
  });

  it('Use this instead in create mode closes modal and focuses existing flow', async () => {
    const user = userEvent.setup();
    projectsGetSimilar.mockResolvedValue({
      matches: [
        {
          id: 2,
          name: 'Target Project',
          team_id: 1,
          team_name: 'Team',
          is_archived: false,
          match_type: 'exact',
          match_score: 1.0,
        },
      ],
    });

    renderPage();
    const { nameInput } = await openCreateModal(user);
    await user.type(nameInput, 'Target Project');

    const warning = await findByTestIdReliable('similar-projects-warning');
    await user.click(within(warning).getByTestId('similar-project-action-2'));

    await waitForReliable(() => {
      expect(screen.queryByText('New Project')).not.toBeInTheDocument();
    });
    expect(await findByTestIdReliable('projects-search-input')).toHaveValue('Target Project');
  });

  it('archive confirmation appears and archived projects expose Unarchive', async () => {
    const user = userEvent.setup();
    renderPage();

    await clickActionForProject(user, 1, 'Archive');

    expect(await screen.findByText(/Archive "Source Project"/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Archive' }));

    await waitForReliable(() => {
      expect(projectsArchive).toHaveBeenCalledWith(1, true);
    });

    await user.click(screen.getByRole('button', { name: /show archived/i }));

    await openMenuForProject(user, 3);
    expect(await screen.findByText('Unarchive')).toBeInTheDocument();
  });

  it('delete modal shows counts and requires exact name before enabling delete', { retry: 2 }, async () => {
    const user = userEvent.setup();
    projectsGetSimilar.mockResolvedValue({ matches: [] });
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('project-card-1')).toBeInTheDocument();
    });

    await clickKebabForProject(user, 1);
    await waitFor(() => {
      expect(screen.getByTestId('project-kebab-menu')).toBeInTheDocument();
    });

    await clickMenuAction(user, 'Delete');
    await waitFor(() => {
      expect(screen.getByTestId('delete-project-confirm-name')).toBeInTheDocument();
    });

    const modalTitle = screen.getByTestId('delete-project-modal-title');
    expect(modalTitle).toHaveTextContent('Source Project');

    const modal = await screen.findByRole('dialog');
    expect(modal).toHaveTextContent(/381\s*tasks/);
    expect(modal).toHaveTextContent(/1247\s*time entries/);

    const submit = screen.getByTestId('delete-project-submit');
    expect(submit).toBeDisabled();

    await user.type(screen.getByTestId('delete-project-confirm-name'), 'Source Project');
    await waitFor(() => {
      expect(submit).toBeEnabled();
    });

    await user.click(submit);
    await waitForReliable(() => {
      expect(projectsDelete).toHaveBeenCalledWith(1);
    });
  });

  it('merge modal excludes source and archived targets and submits merge', async () => {
    const user = userEvent.setup();
    renderPage();

    await clickActionForProject(user, 1, 'Merge with...');

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
