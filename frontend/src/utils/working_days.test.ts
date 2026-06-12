import { describe, expect, it } from 'vitest';

import { formatWorkingDays } from './working_days';

describe('formatWorkingDays', () => {
  it('formats Mon-Fri as a range', () => {
    expect(formatWorkingDays([0, 1, 2, 3, 4])).toBe('Mon-Fri');
  });

  it('formats Mon-Sat as a range', () => {
    expect(formatWorkingDays([0, 1, 2, 3, 4, 5])).toBe('Mon-Sat');
  });

  it('formats non-consecutive weekdays as a list', () => {
    expect(formatWorkingDays([0, 2, 4])).toBe('Mon, Wed, Fri');
  });

  it('formats empty list as none configured', () => {
    expect(formatWorkingDays([])).toBe('(none configured)');
  });

  it('formats Sunday-only schedule', () => {
    expect(formatWorkingDays([6])).toBe('Sun');
  });
});
