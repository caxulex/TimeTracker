// ============================================
// TIME TRACKER - LONG TIMER THRESHOLDS TESTS
// ============================================
import { describe, it, expect } from 'vitest';
import { getCurrentBannerLevel } from './longTimerThresholds';

const H = 3600;

describe('getCurrentBannerLevel', () => {
  it('returns_null_when_elapsed_under_6h', () => {
    expect(getCurrentBannerLevel(5 * H + 59 * 60, null)).toBeNull();
    expect(getCurrentBannerLevel(0, null)).toBeNull();
    expect(getCurrentBannerLevel(6 * H - 1, null)).toBeNull();
  });

  it('returns_6_when_elapsed_just_over_6h', () => {
    expect(getCurrentBannerLevel(6 * H + 1, null)).toBe(6);
    expect(getCurrentBannerLevel(6 * H, null)).toBe(6);
  });

  it('returns_null_when_6h_already_dismissed', () => {
    expect(getCurrentBannerLevel(7 * H, 6)).toBeNull();
    expect(getCurrentBannerLevel(6 * H + 30 * 60, 6)).toBeNull();
  });

  it('returns_8_when_8h_crossed_and_6_was_dismissed', () => {
    expect(getCurrentBannerLevel(8 * H + 1, 6)).toBe(8);
  });

  it('returns_correct_threshold_at_each_step', () => {
    expect(getCurrentBannerLevel(10 * H + 5, 8)).toBe(10);
    expect(getCurrentBannerLevel(12 * H + 5, 10)).toBe(12);
    expect(getCurrentBannerLevel(14 * H + 5, 12)).toBe(14);
  });

  it('handles_extreme_durations', () => {
    // 100h -> 6 + 2*floor((100-6)/2) = 6 + 2*47 = 100
    expect(getCurrentBannerLevel(100 * H, null)).toBe(100);
    expect(getCurrentBannerLevel(100 * H, 98)).toBe(100);
    expect(getCurrentBannerLevel(100 * H, 100)).toBeNull();
  });

  it('returns_null_for_non_finite_elapsed', () => {
    expect(getCurrentBannerLevel(NaN, null)).toBeNull();
    expect(getCurrentBannerLevel(Infinity, null)).toBeNull();
  });
});
