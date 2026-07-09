import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { BillingStatus } from '../../api/client';

import { BillingPage } from '../BillingPage';

const getBillingStatus = vi.fn();
const addNotification = vi.fn();

let currentUser: { id: number; role: string } | null = { id: 1, role: 'admin' };

vi.mock('../../api/client', () => ({
  companiesApi: {
    getBillingStatus: (...args: unknown[]) => getBillingStatus(...args),
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

  it('shows block info note when next add would be blocked', async () => {
    getBillingStatus.mockResolvedValue(
      makeStatus({
        worker_count: 3,
        subscription_tier: 'free',
        is_at_or_over_free_limit: true,
        would_block_next_add: true,
      })
    );

    renderPage();

    expect(await screen.findByText('Adding another worker will require a plan upgrade.')).toBeInTheDocument();
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
});
