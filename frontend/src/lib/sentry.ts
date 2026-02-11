// ============================================
// TIME TRACKER - SENTRY INTEGRATION (FRONTEND)
// Phase 3: Production Observability
// ============================================
// Initializes Sentry error tracking for the frontend.
// Only activates when VITE_SENTRY_DSN is set.
// ============================================

import * as Sentry from '@sentry/react';

/**
 * Initialize Sentry for frontend error tracking.
 * Safe to call even without a DSN — it silently skips initialization.
 */
export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN;

  if (!dsn) {
    if (import.meta.env.DEV) {
      console.debug('[Sentry] No VITE_SENTRY_DSN set — skipping initialization.');
    }
    return;
  }

  const environment = import.meta.env.VITE_ENVIRONMENT || 'development';
  const isProduction = environment === 'production';
  const isStaging = environment === 'staging';

  Sentry.init({
    dsn,
    environment,
    release: `timetracker-frontend@${__APP_VERSION__}`,

    // Lower sample rate in production to reduce volume/cost
    tracesSampleRate: isProduction ? 0.1 : isStaging ? 1.0 : 1.0,

    // Don't send PII by default
    sendDefaultPii: false,

    // Filter out noisy errors
    ignoreErrors: [
      'ResizeObserver loop limit exceeded',
      'ResizeObserver loop completed with undelivered notifications',
      'Network Error',
      'Failed to fetch',
      'Load failed',
    ],

    beforeSend(event) {
      // Strip local file paths from stack traces
      if (event.exception?.values) {
        for (const exception of event.exception.values) {
          if (exception.stacktrace?.frames) {
            for (const frame of exception.stacktrace.frames) {
              if (frame.filename) {
                frame.filename = frame.filename.replace(/^.*\/assets\//, '~/assets/');
              }
            }
          }
        }
      }
      return event;
    },
  });
}

/**
 * Capture an exception in Sentry (no-op if Sentry is not initialized).
 */
export function captureException(
  error: unknown,
  context?: Record<string, unknown>,
): void {
  if (context) {
    Sentry.withScope((scope) => {
      scope.setExtras(context);
      Sentry.captureException(error);
    });
  } else {
    Sentry.captureException(error);
  }
}

/**
 * Set user context in Sentry for better error attribution.
 */
export function setUser(user: { id: number; email: string; role?: string } | null): void {
  if (user) {
    Sentry.setUser({
      id: String(user.id),
      email: user.email,
    });
    Sentry.setTag('user.role', user.role || 'unknown');
  } else {
    Sentry.setUser(null);
  }
}

export { Sentry };
