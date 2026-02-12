// ============================================
// TIME TRACKER - i18n TESTS
// Phase 9A.4: Translation completeness & consistency
// ============================================
import { describe, it, expect } from 'vitest';
import en from '../i18n/locales/en/translation.json';

// Helper to collect all leaf keys from a nested object
function collectKeys(obj: Record<string, any>, prefix = ''): string[] {
  const keys: string[] = [];
  for (const key in obj) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      keys.push(...collectKeys(obj[key], fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

describe('i18n Translation Completeness', () => {
  const allKeys = collectKeys(en);

  it('should have English translation file loaded', () => {
    expect(en).toBeDefined();
    expect(typeof en).toBe('object');
  });

  it('should have required top-level namespaces', () => {
    const requiredNamespaces = [
      'common',
      'nav',
      'login',
      'dashboard',
      'time',
      'projects',
      'teams',
      'tasks',
      'settings',
      'admin',
      'staff',
      'notFound',
      'connection',
      'timer',
    ];

    for (const ns of requiredNamespaces) {
      expect(en).toHaveProperty(ns);
    }
  });

  it('should have all login page keys', () => {
    const loginKeys = [
      'login.welcomeBack',
      'login.signInTo',
      'login.emailLabel',
      'login.emailPlaceholder',
      'login.emailRequired',
      'login.emailInvalid',
      'login.passwordLabel',
      'login.passwordRequired',
      'login.rememberMe',
      'login.forgotPassword',
      'login.signIn',
      'login.needAccount',
      'login.requestAccess',
      'login.loginFailed',
      'login.poweredBy',
    ];

    for (const key of loginKeys) {
      expect(allKeys).toContain(key);
    }
  });

  it('should have all dashboard page keys', () => {
    const dashboardKeys = [
      'dashboard.title',
      'dashboard.subtitleAdmin',
      'dashboard.subtitleUser',
      'dashboard.teamOverview',
      'dashboard.teamToday',
      'dashboard.teamThisWeek',
      'dashboard.activeUsersToday',
      'dashboard.runningTimers',
      'dashboard.todayActivityByUser',
      'dashboard.noTimeTrackedToday',
      'dashboard.yourPersonalStats',
      'dashboard.yourStats',
      'dashboard.today',
      'dashboard.thisWeek',
      'dashboard.thisMonth',
      'dashboard.activeProjects',
      'dashboard.weeklyActivity',
      'dashboard.timeByProject',
    ];

    for (const key of dashboardKeys) {
      expect(allKeys).toContain(key);
    }
  });

  it('should have all time page keys', () => {
    const timeKeys = [
      'time.title',
      'time.subtitle',
      'time.addManualEntry',
      'time.noEntries',
      'time.loadingEntries',
      'time.allProjects',
      'time.allTime',
      'time.entryCreated',
      'time.entryDeleted',
      'time.entryUpdated',
      'time.editTimeEntry',
      'time.addManualTimeEntry',
      'time.descriptionLabel',
      'time.projectLabel',
      'time.taskLabel',
      'time.dateLabel',
      'time.startTimeLabel',
      'time.endTimeLabel',
    ];

    for (const key of timeKeys) {
      expect(allKeys).toContain(key);
    }
  });

  it('should have all navigation keys', () => {
    const navKeys = [
      'nav.dashboard',
      'nav.timeTracker',
      'nav.projects',
      'nav.tasks',
      'nav.teams',
      'nav.reports',
      'nav.settings',
      'nav.admin',
      'nav.staff',
      'nav.payroll',
      'nav.aiInsights',
    ];

    for (const key of navKeys) {
      expect(allKeys).toContain(key);
    }
  });

  it('should have all common keys', () => {
    const commonKeys = [
      'common.save',
      'common.cancel',
      'common.delete',
      'common.edit',
      'common.loading',
      'common.error',
      'common.success',
      'common.search',
      'common.saveChanges',
    ];

    for (const key of commonKeys) {
      expect(allKeys).toContain(key);
    }
  });

  it('should have no empty string values', () => {
    const emptyKeys: string[] = [];
    
    function checkEmpty(obj: Record<string, any>, prefix = '') {
      for (const key in obj) {
        const fullKey = prefix ? `${prefix}.${key}` : key;
        if (typeof obj[key] === 'object' && obj[key] !== null) {
          checkEmpty(obj[key], fullKey);
        } else if (obj[key] === '') {
          emptyKeys.push(fullKey);
        }
      }
    }

    checkEmpty(en);
    expect(emptyKeys).toEqual([]);
  });

  it('should have consistent interpolation syntax ({{variable}})', () => {
    const badKeys: string[] = [];

    function checkInterpolation(obj: Record<string, any>, prefix = '') {
      for (const key in obj) {
        const fullKey = prefix ? `${prefix}.${key}` : key;
        if (typeof obj[key] === 'object' && obj[key] !== null) {
          checkInterpolation(obj[key], fullKey);
        } else if (typeof obj[key] === 'string') {
          // Check for single-brace interpolation (common mistake)
          const singleBrace = obj[key].match(/(?<!\{)\{[a-zA-Z_]+\}(?!\})/g);
          if (singleBrace) {
            badKeys.push(`${fullKey}: ${singleBrace.join(', ')}`);
          }
        }
      }
    }

    checkInterpolation(en);
    expect(badKeys).toEqual([]);
  });

  it('should have a reasonable number of translation keys', () => {
    // Sanity check - we expect at least 100 keys in a fully extracted app
    expect(allKeys.length).toBeGreaterThan(100);
  });
});
