// ============================================
// TIME TRACKER - BILLING PAGE (READ-ONLY)
// ============================================
import { useEffect, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Card, CardHeader, LoadingOverlay } from '../components/common';
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
  const isAdmin = isAdminUser(user);
  const hasNotifiedError = useRef(false);

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
          <CardHeader title="Current plan" subtitle="Read-only billing summary" />

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

          {billing.would_block_next_add && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm text-amber-800">Adding another worker will require a plan upgrade.</p>
            </div>
          )}

          {billing.is_at_or_over_free_limit && billing.subscription_tier === 'free' && (
            <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p className="text-sm text-gray-700">You are at the included free-seat limit for the Free plan.</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

export default BillingPage;
