// ============================================
// TIME TRACKER - INTEGRATIONS PAGE TESTS
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { IntegrationsPage } from '../IntegrationsPage';
import { useAuthStore } from '../../stores/authStore';
import { NotificationProvider } from '../../components/Notifications';
import { basecampApi } from '../../api/basecamp';

// ---- Mocks ----
vi.mock('../../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../api/basecamp', () => ({
  basecampApi: {
    getStatus: vi.fn(),
    getConnectUrl: vi.fn(),
    sync: vi.fn(),
    disconnect: vi.fn(),
    updateSettings: vi.fn(),
  },
}));

vi.mock('../../hooks/useApi', () => ({
  useTeams: vi.fn(() => ({
    data: {
      items: [
        { id: 1, name: 'Engineering' },
        { id: 2, name: 'Sales' },
      ],
    },
    isLoading: false,
  })),
}));

// Silence WebSocketContext / NotificationProvider backend calls
vi.mock('../../api/notifications', () => ({
  getNotifications: vi.fn().mockResolvedValue({ items: [], unread_count: 0 }),
  deleteNotifications: vi.fn().mockResolvedValue(undefined),
  markNotificationsRead: vi.fn().mockResolvedValue(undefined),
}));

const mockedAuth = useAuthStore as unknown as ReturnType<typeof vi.fn>;
const mockedApi = basecampApi as unknown as {
  getStatus: ReturnType<typeof vi.fn>;
  getConnectUrl: ReturnType<typeof vi.fn>;
  sync: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  updateSettings: ReturnType<typeof vi.fn>;
};

function setUser(role: 'super_admin' | 'admin' | 'regular_user' | 'member' | null) {
  mockedAuth.mockReturnValue({
    user: role ? { id: 1, email: 'u@example.com', role } : null,
    isAuthenticated: !!role,
  });
}

function renderPage(initialPath: string = '/settings/integrations') {
  // TeamSelect always invokes useQuery (even when teams are passed as a prop),
  // so a QueryClientProvider is required at the test root.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <NotificationProvider>
          <Routes>
            <Route path="/settings/integrations" element={<IntegrationsPage />} />
          </Routes>
        </NotificationProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const connectedStatus = {
  connected: true,
  account_name: 'Acme Co',
  last_sync_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
  expires_at: new Date(Date.now() + 7 * 86400 * 1000).toISOString(),
  target_team_id: null,
  target_team_name: null,
  auto_sync_enabled: false,
};

const disconnectedStatus = {
  connected: false,
  account_name: null,
  last_sync_at: null,
  expires_at: null,
  target_team_id: null,
  target_team_name: null,
  auto_sync_enabled: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  setUser('super_admin');
});

describe('IntegrationsPage - rendering', () => {
  it('renders skeleton while loading', () => {
    mockedApi.getStatus.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByTestId('basecamp-skeleton')).toBeInTheDocument();
  });

  it('renders "Not connected" state when status returns connected: false', async () => {
    mockedApi.getStatus.mockResolvedValue(disconnectedStatus);
    renderPage();
    expect(await screen.findByTestId('basecamp-status-badge')).toHaveTextContent(
      /not connected/i
    );
    expect(
      screen.getByRole('button', { name: /connect to basecamp/i })
    ).toBeInTheDocument();
  });

  it('renders connected state with account name when connected', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    expect(await screen.findByTestId('basecamp-account-name')).toHaveTextContent(
      'Acme Co'
    );
    expect(screen.getByTestId('basecamp-status-badge')).toHaveTextContent(
      /connected/i
    );
    expect(screen.getByRole('button', { name: /sync now/i })).toBeInTheDocument();
  });

  it('renders "not configured" message when API returns 503', async () => {
    mockedApi.getStatus.mockRejectedValue({
      isAxiosError: true,
      response: { status: 503 },
    });

    renderPage();
    expect(
      await screen.findByText(/Basecamp integration is not configured/i)
    ).toBeInTheDocument();
  });
});

describe('IntegrationsPage - interactions', () => {
  it('clicking Connect redirects to authorization_url', async () => {
    mockedApi.getStatus.mockResolvedValue(disconnectedStatus);
    mockedApi.getConnectUrl.mockResolvedValue({
      authorization_url: 'https://launchpad.basecamp.com/authorization/new?abc',
    });

    const originalLocation = window.location;
    // Stub assignable href
    delete (window as unknown as { location?: Location }).location;
    const hrefSetter = vi.fn();
    (window as unknown as { location: { href: string } }).location = {
      get href() {
        return '';
      },
      set href(v: string) {
        hrefSetter(v);
      },
    } as unknown as Location;

    try {
      renderPage();
      const btn = await screen.findByRole('button', { name: /connect to basecamp/i });
      await userEvent.click(btn);
      await waitFor(() => {
        expect(mockedApi.getConnectUrl).toHaveBeenCalled();
        expect(hrefSetter).toHaveBeenCalledWith(
          'https://launchpad.basecamp.com/authorization/new?abc'
        );
      });
    } finally {
      (window as unknown as { location: Location }).location = originalLocation;
    }
  });

  it('clicking Sync Now calls API and shows success summary', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    mockedApi.sync.mockResolvedValue({
      created: 12,
      updated: 3,
      unchanged: 5,
      errors: [],
      dry_run: false,
    });
    renderPage();
    const btn = await screen.findByRole('button', { name: /sync now/i });
    await userEvent.click(btn);
    await waitFor(() => {
      expect(mockedApi.sync).toHaveBeenCalledWith(false);
    });
    // Detail panel summary
    expect(
      await screen.findByText(/12 created, 3 updated, 5 unchanged, 0 errors/i)
    ).toBeInTheDocument();
  });

  it('Sync with errors shows warning and lists errors when expanded', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    mockedApi.sync.mockResolvedValue({
      created: 1,
      updated: 0,
      unchanged: 0,
      errors: ['Project X failed: missing slug', 'Project Y forbidden'],
      dry_run: false,
    });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /sync now/i }));

    const viewDetails = await screen.findByRole('button', { name: /view details/i });
    await userEvent.click(viewDetails);

    expect(screen.getByText(/Project X failed: missing slug/)).toBeInTheDocument();
    expect(screen.getByText(/Project Y forbidden/)).toBeInTheDocument();
  });

  it('clicking Disconnect opens a confirmation modal', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    await userEvent.click(
      await screen.findByRole('button', { name: /disconnect/i })
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/Are you sure\?/i)).toBeInTheDocument();
  });

  it('confirming disconnect calls API and refreshes status', async () => {
    mockedApi.getStatus
      .mockResolvedValueOnce(connectedStatus)
      .mockResolvedValueOnce(disconnectedStatus);
    mockedApi.disconnect.mockResolvedValue(undefined);

    renderPage();
    await userEvent.click(
      await screen.findByRole('button', { name: /^disconnect$/i })
    );
    // Confirm button inside modal
    const dialog = screen.getByRole('dialog');
    await userEvent.click(
      within(dialog).getByRole('button', { name: /^disconnect$/i })
    );

    await waitFor(() => {
      expect(mockedApi.disconnect).toHaveBeenCalledTimes(1);
      expect(mockedApi.getStatus).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId('basecamp-status-badge')).toHaveTextContent(
      /not connected/i
    );
  });

  it('cancelling disconnect modal does NOT call API', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    await userEvent.click(
      await screen.findByRole('button', { name: /^disconnect$/i })
    );
    const dialog = screen.getByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));

    expect(mockedApi.disconnect).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});

describe('IntegrationsPage - role-based visibility', () => {
  it('super_admin sees Connect/Sync/Disconnect buttons', async () => {
    setUser('super_admin');
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    expect(await screen.findByRole('button', { name: /sync now/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^disconnect$/i })).toBeInTheDocument();
  });

  it('admin sees status but no mutating buttons (read-only)', async () => {
    setUser('admin');
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    expect(await screen.findByTestId('basecamp-account-name')).toHaveTextContent(
      'Acme Co'
    );
    expect(screen.queryByRole('button', { name: /sync now/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^disconnect$/i })).not.toBeInTheDocument();
    expect(screen.getByText(/read-only view/i)).toBeInTheDocument();
  });

  it('non-admin user sees access denied', async () => {
    setUser('member');
    renderPage();
    expect(await screen.findByText(/access denied/i)).toBeInTheDocument();
    expect(mockedApi.getStatus).not.toHaveBeenCalled();
  });
});

describe('IntegrationsPage - OAuth callback handling', () => {
  it('shows success toast and clears ?status=connected query param', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage('/settings/integrations?status=connected');

    // Toast title appears in NotificationProvider toast container
    expect(
      await screen.findByText(/Successfully connected to Basecamp/i)
    ).toBeInTheDocument();
  });
});

describe('IntegrationsPage - sync settings (target team + auto-sync)', () => {
  it('displays team picker when connected', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    const select = await screen.findByTestId('basecamp-target-team-select');
    expect(select).toBeInTheDocument();
    // Open the combobox; options are rendered lazily by TeamSelect.
    const combobox = within(select).getByRole('combobox');
    await userEvent.click(combobox);
    const listbox = await screen.findByTestId('team-select-listbox');
    expect(within(listbox).getByText('Engineering')).toBeInTheDocument();
    expect(within(listbox).getByText('Sales')).toBeInTheDocument();
  });

  it('displays auto-sync toggle when connected', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    renderPage();
    const toggle = await screen.findByTestId('basecamp-auto-sync-toggle');
    expect(toggle).toBeInTheDocument();
    expect(toggle).not.toBeChecked();
  });

  it('updates target team on dropdown change', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    mockedApi.updateSettings.mockResolvedValue({
      ...connectedStatus,
      target_team_id: 2,
      target_team_name: 'Sales',
    });
    renderPage();
    const select = await screen.findByTestId('basecamp-target-team-select');
    const combobox = within(select).getByRole('combobox');
    await userEvent.click(combobox);
    // mouseDown on the option to mirror TeamSelect's commit path.
    fireEvent.mouseDown(await screen.findByTestId('team-select-option-2'));
    await waitFor(() => {
      expect(mockedApi.updateSettings).toHaveBeenCalledWith({ target_team_id: 2 });
    });
  });

  it('toggles auto-sync on checkbox change', async () => {
    mockedApi.getStatus.mockResolvedValue(connectedStatus);
    mockedApi.updateSettings.mockResolvedValue({
      ...connectedStatus,
      auto_sync_enabled: true,
    });
    renderPage();
    const toggle = await screen.findByTestId('basecamp-auto-sync-toggle');
    await userEvent.click(toggle);
    await waitFor(() => {
      expect(mockedApi.updateSettings).toHaveBeenCalledWith({ auto_sync_enabled: true });
    });
  });

  it('renders read-only sync settings for admin (non-super)', async () => {
    setUser('admin');
    mockedApi.getStatus.mockResolvedValue({
      ...connectedStatus,
      target_team_id: 1,
      target_team_name: 'Engineering',
      auto_sync_enabled: true,
    });
    renderPage();
    const select = await screen.findByTestId('basecamp-target-team-select');
    const combobox = within(select).getByRole('combobox') as HTMLInputElement;
    const toggle = screen.getByTestId('basecamp-auto-sync-toggle') as HTMLInputElement;
    expect(combobox).toBeDisabled();
    expect(toggle).toBeDisabled();
    expect(toggle).toBeChecked();
  });
});
