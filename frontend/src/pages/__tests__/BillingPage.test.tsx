import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { BillingStatus } from '../../api/client';

import { BillingPage } from '../BillingPage';

const getBillingStatus = vi.fn();
const upgradeBilling = vi.fn();
const switchToUnlimited = vi.fn();
const addNotification = vi.fn();

let currentUser: { id: number; role: string } | null = { id: 1, role: 'admin' };

vi.mock('../../api/client', () => ({
  companiesApi: {
    getBillingStatus: (...args: unknown[]) => getBillingStatus(...args),
    upgradeBilling: (...args: unknown[]) => upgradeBilling(...args),
    switchToUnlimited: (...args: unknown[]) => switchToUnlimited(...args),
  },
}));

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({ addNotification }),
}));

vi.mock('../../stores/authStore', () => ({
  useAuthStore: () => ({ user: currentUser }),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BillingPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function makeStatus(overrides: Partial<BillingStatus> = {}): BillingStatus {
  return {
    worker_count: 2,
    free_limit: 3,
    seats_over_free: 0,
    per_seat_monthly_cost_dollars: 0,
    should_recommend_unlimited: false,
    subscription_tier: 'free',
    has_subscription: false,
    is_at_or_over_free_limit: false,
    would_block_next_add: false,
    ...overrides,
  };
}

describe('BillingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentUser = { id: 1, role: 'admin' };
    upgradeBilling.mockResolvedValue({
      success: true,
      status: 'ok',
      company_id: 1,
      subscription_tier: 'standard',
      stripe_subscription_id: null,
      stripe_customer_id: null,
      requires_payment_action: false,
      message: 'updated',
    });
    switchToUnlimited.mockResolvedValue({
      success: true,
      status: 'ok',
      company_id: 1,
      subscription_tier: 'unlimited',
      stripe_subscription_id: 'sub_123',
      requires_payment_action: false,
      message: 'updated',
    });
  });

  it('renders billing status for a free company', async () => {
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'free' }));

    renderPage();

    expect(await screen.findByText('Free')).toBeInTheDocument();
    expect(screen.getByText('$0 / month')).toBeInTheDocument();
  });

  it('renders standard company cost and breakdown', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        worker_count: 5,
        seats_over_free: 2,
        per_seat_monthly_cost_dollars: 10,
        subscription_tier: 'standard',
        is_at_or_over_free_limit: true,
      })
    );

    renderPage();

    expect(await screen.findByText('Standard (per-seat)')).toBeInTheDocument();
    expect(screen.getByText('$10 / month')).toBeInTheDocument();
    expect(screen.getByText('3 free + 2 paid seats x $5')).toBeInTheDocument();
  });

  it('renders unlimited company with flat pricing', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        worker_count: 12,
        subscription_tier: 'unlimited',
        has_subscription: true,
      })
    );

    renderPage();

    expect(await screen.findByText('Unlimited')).toBeInTheDocument();
    expect(screen.getByText('$50 / month (flat)')).toBeInTheDocument();
  });

  it('shows recommendation note when unlimited is recommended', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        worker_count: 15,
        seats_over_free: 12,
        per_seat_monthly_cost_dollars: 60,
        subscription_tier: 'standard',
        should_recommend_unlimited: true,
      })
    );

    renderPage();

    expect(
      await screen.findByText('At your team size, the Unlimited plan ($50/mo flat) may cost less than per-seat.')
    ).toBeInTheDocument();
  });

  it('shows the upgrade-context note when a free company is at the seat limit', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        worker_count: 3,
        subscription_tier: 'free',
        is_at_or_over_free_limit: true,
        would_block_next_add: true,
      })
    );

    renderPage();

    expect(await screen.findByText(/Upgrade to Standard to add more workers/)).toBeInTheDocument();
  });

  it('shows loading state', () => {
    getBillingStatus.mockImplementation(() => new Promise(() => {}));

    renderPage();

    expect(screen.getByText('Loading billing status...')).toBeInTheDocument();
  });

  it('shows error state and notification when query fails', async () => {
    getBillingStatus.mockRejectedValue(new Error('boom'));

    renderPage();

    expect(await screen.findByText('Could not load billing status. Please try again.')).toBeInTheDocument();

    await waitFor(() => {
      expect(addNotification).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          title: 'Billing unavailable',
        })
      );
    });
  });

  it('free company shows both Upgrade and Switch buttons', async () => {
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'free' }));

    renderPage();

    expect(await screen.findByText('Upgrade to Standard')).toBeInTheDocument();
    expect(screen.getByText('Switch to Unlimited')).toBeInTheDocument();
  });

  it('standard company shows only Switch button', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        subscription_tier: 'standard',
        worker_count: 6,
        seats_over_free: 3,
        per_seat_monthly_cost_dollars: 15,
      })
    );

    renderPage();

    expect(await screen.findByText('Switch to Unlimited')).toBeInTheDocument();
    expect(screen.queryByText('Upgrade to Standard')).not.toBeInTheDocument();
  });

  it('unlimited company shows no action buttons', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        subscription_tier: 'unlimited',
        has_subscription: true,
      })
    );

    renderPage();

    expect(await screen.findByText('Unlimited')).toBeInTheDocument();
    expect(screen.queryByText('Upgrade to Standard')).not.toBeInTheDocument();
    expect(screen.queryByText('Switch to Unlimited')).not.toBeInTheDocument();
  });

  it('clicking Upgrade shows confirmation modal', async () => {
    const user = userEvent.setup();
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'free' }));

    renderPage();

    await user.click(await screen.findByText('Upgrade to Standard'));

    expect(await screen.findByRole('dialog', { name: 'Upgrade to Standard' })).toBeInTheDocument();
    expect(
      screen.getByText(/You pay \$0 now\. As you add workers above 3, pricing is \$5\/month per additional worker\./)
    ).toBeInTheDocument();
  });

  it('confirming Upgrade calls upgradeBilling, refetches status, and shows success toast', async () => {
    const user = userEvent.setup();
    getBillingStatus
      .mockResolvedValueOnce(makeStatus({ subscription_tier: 'free' }))
      .mockResolvedValueOnce(
        makeStatus({
          subscription_tier: 'standard',
          worker_count: 4,
          seats_over_free: 1,
          per_seat_monthly_cost_dollars: 5,
          has_subscription: true,
        })
      );

    renderPage();

    await user.click(await screen.findByText('Upgrade to Standard'));
    await user.click(screen.getByRole('button', { name: 'Upgrade' }));

    await waitFor(() => {
      expect(upgradeBilling).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(getBillingStatus).toHaveBeenCalledTimes(2);
    });

    expect(addNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'success',
        message: "You're now on the Standard plan.",
      })
    );
  });

  it('clicking Switch shows confirmation modal with $50/mo copy', async () => {
    const user = userEvent.setup();
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'free' }));

    renderPage();

    await user.click(await screen.findByText('Switch to Unlimited'));

    expect(await screen.findByRole('dialog', { name: 'Switch to Unlimited' })).toBeInTheDocument();
    expect(
      screen.getByText(
        'This will change your plan to Unlimited at $50/month flat and replace per-seat billing.'
      )
    ).toBeInTheDocument();
  });

  it('confirming Switch calls switchToUnlimited, refetches status, and shows success toast', async () => {
    const user = userEvent.setup();
    getBillingStatus
      .mockResolvedValueOnce(
        makeStatus({
          subscription_tier: 'standard',
          worker_count: 8,
          seats_over_free: 5,
          per_seat_monthly_cost_dollars: 25,
        })
      )
      .mockResolvedValueOnce(
        makeStatus({
          subscription_tier: 'unlimited',
          worker_count: 8,
          has_subscription: true,
        })
      );

    renderPage();

    await user.click(await screen.findByText('Switch to Unlimited'));
    const dialog = await screen.findByRole('dialog', { name: 'Switch to Unlimited' });
    await user.click(within(dialog).getByRole('button', { name: 'Switch to Unlimited' }));

    await waitFor(() => {
      expect(switchToUnlimited).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(getBillingStatus).toHaveBeenCalledTimes(2);
    });

    expect(addNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'success',
        message: "You're now on the Unlimited plan.",
      })
    );
  });

  it('Switch 402 shows contact-support message', async () => {
    const user = userEvent.setup();
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'standard' }));
    switchToUnlimited.mockRejectedValue({
      isAxiosError: true,
      response: { status: 402 },
      config: {},
      toJSON: () => ({}),
      name: 'AxiosError',
      message: '402',
    });

    renderPage();

    await user.click(await screen.findByText('Switch to Unlimited'));
    const dialog = await screen.findByRole('dialog', { name: 'Switch to Unlimited' });
    await user.click(within(dialog).getByRole('button', { name: 'Switch to Unlimited' }));

    await waitFor(() => {
      expect(addNotification).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          message:
            "This change needs a payment step we can't complete automatically yet. Please contact support to finish switching to Unlimited.",
        })
      );
    });
  });

  it('Switch 503 shows retry message', async () => {
    const user = userEvent.setup();
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'standard' }));
    switchToUnlimited.mockRejectedValue({
      isAxiosError: true,
      response: { status: 503 },
      config: {},
      toJSON: () => ({}),
      name: 'AxiosError',
      message: '503',
    });

    renderPage();

    await user.click(await screen.findByText('Switch to Unlimited'));
    const dialog = await screen.findByRole('dialog', { name: 'Switch to Unlimited' });
    await user.click(within(dialog).getByRole('button', { name: 'Switch to Unlimited' }));

    await waitFor(() => {
      expect(addNotification).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          message: 'Billing is temporarily unavailable. Please try again in a moment.',
        })
      );
    });
  });

  it('in-flight mutation disables confirm button to prevent double-submit', async () => {
    const user = userEvent.setup();
    getBillingStatus.mockResolvedValue(makeStatus({ subscription_tier: 'standard' }));

    let resolveSwitch: (() => void) | undefined;
    switchToUnlimited.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSwitch = () => resolve(undefined);
        })
    );

    renderPage();

    await user.click(await screen.findByText('Switch to Unlimited'));
    const dialog = await screen.findByRole('dialog', { name: 'Switch to Unlimited' });
    const confirmButton = within(dialog).getByRole('button', { name: 'Switch to Unlimited' });

    await user.click(confirmButton);

    await waitFor(() => {
      expect(confirmButton).toBeDisabled();
      expect(switchToUnlimited).toHaveBeenCalledTimes(1);
    });

    if (resolveSwitch) {
      resolveSwitch();
    }
  });
});
