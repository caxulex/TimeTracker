// ============================================
// TIME TRACKER - BILLING PAGE (READ-ONLY)
// ============================================
import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Button, Card, CardHeader, LoadingOverlay, Modal } from '../components/common';
import { companiesApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { useNotifications } from '../hooks/useNotifications';
import { isAdminUser } from '../utils/helpers';

function planLabel(tier: 'free' | 'standard' | 'unlimited'): string {
  if (tier === 'free') return 'Free';
  if (tier === 'standard') return 'Standard (per-seat)';
  return 'Unlimited';
}

export function BillingPage() {
  const { user } = useAuthStore();
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  const isAdmin = isAdminUser(user);
  const hasNotifiedError = useRef(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showUnlimitedModal, setShowUnlimitedModal] = useState(false);

  const {
    data: billing,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['billing-status'],
    queryFn: () => companiesApi.getBillingStatus(),
    enabled: isAdmin,
  });

  const upgradeMutation = useMutation({
    mutationFn: () => companiesApi.upgradeBilling(),
    onSuccess: () => {
      setShowUpgradeModal(false);
      queryClient.invalidateQueries({ queryKey: ['billing-status'] });
      addNotification({
        type: 'success',
        title: 'Plan updated',
        message: "You're now on the Standard plan.",
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Upgrade failed',
        message: "Couldn't complete the upgrade. Please try again or contact support.",
      });
    },
  });

  const switchMutation = useMutation({
    mutationFn: () => companiesApi.switchToUnlimited(),
    onSuccess: () => {
      setShowUnlimitedModal(false);
      queryClient.invalidateQueries({ queryKey: ['billing-status'] });
      addNotification({
        type: 'success',
        title: 'Plan updated',
        message: "You're now on the Unlimited plan.",
      });
    },
    onError: (mutationError: unknown) => {
      const status = axios.isAxiosError(mutationError) ? mutationError.response?.status : undefined;

      let message = 'Could not switch to Unlimited. Please try again or contact support.';
      if (status === 402) {
        message = "This change needs a payment step we can't complete automatically yet. Please contact support to finish switching to Unlimited.";
      } else if (status === 503) {
        message = 'Billing is temporarily unavailable. Please try again in a moment.';
      } else if (status === 500) {
        message = 'Something went wrong on our end. Please contact support.';
      }

      addNotification({
        type: 'error',
        title: 'Switch failed',
        message,
      });
    },
  });

  const errorMessage = useMemo(() => {
    if (!isError) return '';
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        return 'Could not load billing status. Company record not found.';
      }
      const detail = error.response?.data?.detail;
      if (typeof detail === 'string' && detail.trim().length > 0) {
        return `Could not load billing status. ${detail}`;
      }
    }
    return 'Could not load billing status. Please try again.';
  }, [isError, error]);

  useEffect(() => {
    if (!isError || !errorMessage || hasNotifiedError.current) {
      return;
    }

    hasNotifiedError.current = true;
    addNotification({
      type: 'error',
      title: 'Billing unavailable',
      message: errorMessage,
    });
  }, [isError, errorMessage, addNotification]);

  const isMutating = upgradeMutation.isPending || switchMutation.isPending;

  const canUpgradeToStandard = billing?.subscription_tier === 'free';
  const canSwitchToUnlimited = billing?.subscription_tier === 'free' || billing?.subscription_tier === 'standard';

  const handleConfirmUpgrade = () => {
    if (isMutating || upgradeMutation.isPending) {
      return;
    }
    upgradeMutation.mutate();
  };

  const handleConfirmUnlimited = () => {
    if (isMutating || switchMutation.isPending) {
      return;
    }
    switchMutation.mutate();
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card>
          <div className="text-center p-8">
            <svg
              className="w-16 h-16 mx-auto text-red-500 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Access Restricted</h2>
            <p className="text-gray-500 dark:text-gray-400">Only Administrators can access this page.</p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Billing</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">View your current plan, monthly cost, and team size.</p>
      </div>

      {isLoading && <LoadingOverlay message="Loading billing status..." />}

      {isError && (
        <Card>
          <CardHeader title="Billing" subtitle="Could not load billing status" />
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{errorMessage}</p>
        </Card>
      )}

      {!isLoading && !isError && billing && (
        <Card>
          <CardHeader title="Current plan" subtitle="Billing summary" />

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">Current plan</span>
              <span className="text-base font-semibold text-gray-900 dark:text-white">
                {planLabel(billing.subscription_tier)}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">Monthly cost</span>
              <div className="text-right">
                {billing.subscription_tier === 'free' && (
                  <>
                    <p className="text-base font-semibold text-gray-900 dark:text-white">$0 / month</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Up to {billing.free_limit} included seats</p>
                  </>
                )}
                {billing.subscription_tier === 'standard' && (
                  <>
                    <p className="text-base font-semibold text-gray-900 dark:text-white">
                      ${billing.per_seat_monthly_cost_dollars} / month
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {billing.free_limit} free + {billing.seats_over_free} paid seats x $5
                    </p>
                  </>
                )}
                {billing.subscription_tier === 'unlimited' && (
                  <>
                    <p className="text-base font-semibold text-gray-900 dark:text-white">$50 / month (flat)</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Unlimited seats included</p>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">Team size</span>
              <div className="text-right">
                <p className="text-base font-semibold text-gray-900 dark:text-white">
                  {billing.worker_count} workers
                </p>
                {billing.seats_over_free > 0 ? (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {billing.worker_count} workers, {billing.free_limit} included free ({billing.seats_over_free} paid seats)
                  </p>
                ) : (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {billing.worker_count} of {billing.free_limit} free seats used
                  </p>
                )}
              </div>
            </div>
          </div>

          {billing.should_recommend_unlimited && billing.subscription_tier !== 'unlimited' && (
            <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3">
              <p className="text-sm text-blue-800">
                At your team size, the Unlimited plan ($50/mo flat) may cost less than per-seat.
              </p>
            </div>
          )}

          {billing.subscription_tier === 'free' && (billing.would_block_next_add || billing.is_at_or_over_free_limit) && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm text-amber-800">
                You are at the free-seat limit. Upgrade to Standard to add more workers. You pay $0 today and
                $5/month only for each worker above {billing.free_limit}.
              </p>
            </div>
          )}

          {(canUpgradeToStandard || canSwitchToUnlimited) && (
            <div className="mt-5 flex flex-wrap gap-3">
              {canUpgradeToStandard && (
                <Button
                  type="button"
                  variant="primary"
                  onClick={() => setShowUpgradeModal(true)}
                  disabled={isMutating}
                >
                  Upgrade to Standard
                </Button>
              )}
              {canSwitchToUnlimited && (
                <Button
                  type="button"
                  variant={canUpgradeToStandard ? 'secondary' : 'primary'}
                  onClick={() => setShowUnlimitedModal(true)}
                  disabled={isMutating}
                >
                  Switch to Unlimited
                </Button>
              )}
            </div>
          )}
        </Card>
      )}

      {billing && (
        <>
          <Modal
            isOpen={showUpgradeModal}
            onClose={() => {
              if (!isMutating) setShowUpgradeModal(false);
            }}
            title="Upgrade to Standard"
            size="md"
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                Upgrading to Standard enables adding workers beyond the {billing.free_limit} free seats.
              </p>
              <p className="text-sm text-gray-700">
                You pay $0 now. As you add workers above {billing.free_limit}, pricing is $5/month per additional
                worker. There is no charge today.
              </p>
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowUpgradeModal(false)}
                  disabled={isMutating}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  onClick={handleConfirmUpgrade}
                  isLoading={upgradeMutation.isPending}
                  disabled={isMutating}
                >
                  Upgrade
                </Button>
              </div>
            </div>
          </Modal>

          <Modal
            isOpen={showUnlimitedModal}
            onClose={() => {
              if (!isMutating) setShowUnlimitedModal(false);
            }}
            title="Switch to Unlimited"
            size="md"
          >
            <div className="space-y-4">
              <p className="text-sm text-gray-700">
                This will change your plan to Unlimited at $50/month flat and replace per-seat billing.
              </p>
              <p className="text-sm text-gray-700">
                The change takes effect now, with proration applied on your next invoice.
              </p>
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowUnlimitedModal(false)}
                  disabled={isMutating}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  onClick={handleConfirmUnlimited}
                  isLoading={switchMutation.isPending}
                  disabled={isMutating}
                >
                  Switch to Unlimited
                </Button>
              </div>
            </div>
          </Modal>
        </>
      )}
    </div>
  );
}

export default BillingPage;
