// ============================================
// TIME TRACKER - LONG TIMER THRESHOLDS
// Pure threshold-detection helpers for LongTimerBanner (PR-B).
// First banner fires at 6h, then again at every 2h step (8h, 10h, ...).
// ============================================

const SECONDS_PER_HOUR = 3600;
export const FIRST_THRESHOLD_HOURS = 6;
export const THRESHOLD_STEP_HOURS = 2;

/**
 * Given the running timer's elapsedSeconds and the last threshold the user
 * already dismissed for this entry, return the threshold (in hours) that
 * should currently be shown — or null if no banner is due.
 *
 * Threshold ladder: 6h, 8h, 10h, 12h, ... (every 2h after the first 6h).
 */
export function getCurrentBannerLevel(
  elapsedSeconds: number,
  lastDismissedLevel: number | null
): number | null {
  if (!Number.isFinite(elapsedSeconds) || elapsedSeconds < FIRST_THRESHOLD_HOURS * SECONDS_PER_HOUR) {
    return null;
  }
  const hours = elapsedSeconds / SECONDS_PER_HOUR;
  const stepsPast = Math.floor((hours - FIRST_THRESHOLD_HOURS) / THRESHOLD_STEP_HOURS);
  const currentLevel = FIRST_THRESHOLD_HOURS + stepsPast * THRESHOLD_STEP_HOURS;

  if (lastDismissedLevel !== null && currentLevel <= lastDismissedLevel) {
    return null;
  }
  return currentLevel;
}
