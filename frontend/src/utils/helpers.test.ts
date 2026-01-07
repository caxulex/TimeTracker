// ============================================
// TIME TRACKER - HELPER FUNCTIONS TESTS
// TASK-050: Unit tests for utility functions
// ============================================
import { describe, it, expect } from 'vitest';
import {
  formatTime,
  formatDuration,
  formatDate,
  cn,
  truncate,
  secondsToHours,
  getInitials,
  formatDistanceToNow,
} from '../utils/helpers';

describe('formatTime', () => {
  it('should format 0 seconds as 00:00:00', () => {
    expect(formatTime(0)).toBe('00:00:00');
  });

  it('should format 3661 seconds as 01:01:01', () => {
    expect(formatTime(3661)).toBe('01:01:01');
  });

  it('should format 36000 seconds as 10:00:00', () => {
    expect(formatTime(36000)).toBe('10:00:00');
  });
});

describe('formatDuration', () => {
  it('should format 0 seconds as 0m', () => {
    expect(formatDuration(0)).toBe('0m');
  });

  it('should format 3600 seconds as 1h', () => {
    expect(formatDuration(3600)).toBe('1h');
  });

  it('should format 5400 seconds as 1h 30m', () => {
    expect(formatDuration(5400)).toBe('1h 30m');
  });
});

describe('formatDate', () => {
  it('should format a date string correctly', () => {
    const result = formatDate('2025-12-06T10:00:00Z');
    expect(result).toContain('Dec');
    expect(result).toContain('6');
    expect(result).toContain('2025');
  });
});

describe('cn', () => {
  it('should join class names', () => {
    expect(cn('class1', 'class2')).toBe('class1 class2');
  });

  it('should filter out falsy values', () => {
    expect(cn('class1', false, null, undefined, 'class2')).toBe('class1 class2');
  });
});

describe('truncate', () => {
  it('should truncate long strings', () => {
    expect(truncate('This is a long string', 10)).toBe('This is a ...');
  });

  it('should not truncate short strings', () => {
    expect(truncate('Short', 10)).toBe('Short');
  });
});

describe('secondsToHours', () => {
  it('should convert seconds to hours', () => {
    expect(secondsToHours(3600)).toBe(1);
    expect(secondsToHours(7200)).toBe(2);
    expect(secondsToHours(5400)).toBe(1.5);
  });
});

describe('getInitials', () => {
  it('should get initials from full name', () => {
    expect(getInitials('John Doe')).toBe('JD');
    expect(getInitials('Jane')).toBe('J');
    expect(getInitials('John Paul Smith')).toBe('JP');
  });
});

describe('formatDistanceToNow', () => {
  it('should return "just now" for recent dates', () => {
    const now = new Date();
    expect(formatDistanceToNow(now)).toBe('just now');
  });

  it('should return minutes ago for recent times', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
    expect(formatDistanceToNow(fiveMinutesAgo)).toBe('5 minutes ago');
  });

  it('should return hours ago', () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
    expect(formatDistanceToNow(twoHoursAgo)).toBe('2 hours ago');
  });
});
