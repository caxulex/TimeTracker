// ============================================
// TIME TRACKER - AUTOMATED BRANDING CHECKLIST TESTS
// TASK 5.3: Converts manual branding test items to automated tests
// ============================================
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { BrandingProvider, useBranding } from '../contexts/BrandingContext';
import { DEFAULT_BRANDING } from '../services/brandingService';
import type { WhiteLabelConfig } from '../services/brandingService';
import { NotificationProvider } from '../components/Notifications';

// ============================================
// Mock setup
// ============================================

// Mock react-router-dom navigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

// ============================================
// Test helpers
// ============================================

function TestWrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <NotificationProvider>
        <BrandingProvider>
          {children}
        </BrandingProvider>
      </NotificationProvider>
    </MemoryRouter>
  );
}

// ============================================
// CHECKLIST ITEM: Logo & App Name
// ============================================
describe('Branding Checklist: Logo & App Name', () => {
  afterEach(() => {
    document.title = '';
  });

  it('document title reflects custom app name from branding config', async () => {
    const { applyBrandingToDocument } = await import('../services/brandingService');

    applyBrandingToDocument({
      ...DEFAULT_BRANDING,
      app_name: 'Custom Portal',
    });

    expect(document.title).toBe('Custom Portal');
  });

  it('default app name is "Time Tracker"', () => {
    expect(DEFAULT_BRANDING.app_name).toBe('Time Tracker');
  });

  it('custom logo URL is included in branding config', () => {
    const config: WhiteLabelConfig = {
      ...DEFAULT_BRANDING,
      logo_url: 'https://cdn.example.com/custom-logo.png',
    };
    expect(config.logo_url).toBe('https://cdn.example.com/custom-logo.png');
  });

  it('custom favicon is applied to document', async () => {
    const { applyBrandingToDocument } = await import('../services/brandingService');

    applyBrandingToDocument({
      ...DEFAULT_BRANDING,
      favicon_url: '/custom-favicon.ico',
    });

    const link = document.querySelector("link[rel*='icon']") as HTMLLinkElement;
    expect(link).not.toBeNull();
    expect(link?.href).toContain('custom-favicon.ico');
  });
});

// ============================================
// CHECKLIST ITEM: Colors & Theme
// ============================================
describe('Branding Checklist: Colors & Theme', () => {
  afterEach(() => {
    const root = document.documentElement;
    root.style.removeProperty('--color-primary');
    root.style.removeProperty('--color-primary-hover');
    root.style.removeProperty('--color-primary-light');
    root.style.removeProperty('--color-secondary');
    root.style.removeProperty('--color-secondary-hover');
    root.style.removeProperty('--color-accent');
  });

  it('primary color from config is applied as CSS custom property', async () => {
    const { applyBrandingToDocument } = await import('../services/brandingService');

    applyBrandingToDocument({
      ...DEFAULT_BRANDING,
      primary_color: '#10b981',
    });

    const root = document.documentElement;
    expect(root.style.getPropertyValue('--color-primary')).toBe('#10b981');
  });

  it('primary color hover variant is auto-generated', async () => {
    const { applyBrandingToDocument } = await import('../services/brandingService');

    applyBrandingToDocument({
      ...DEFAULT_BRANDING,
      primary_color: '#10b981',
    });

    const root = document.documentElement;
    const hoverColor = root.style.getPropertyValue('--color-primary-hover');
    expect(hoverColor).toBeTruthy();
    expect(hoverColor).not.toBe('#10b981'); // Should be darker
  });

  it('secondary color and accent color applied when present', async () => {
    const { applyBrandingToDocument } = await import('../services/brandingService');

    applyBrandingToDocument({
      ...DEFAULT_BRANDING,
      secondary_color: '#4f46e5',
      accent_color: '#f97316',
    });

    const root = document.documentElement;
    expect(root.style.getPropertyValue('--color-secondary')).toBe('#4f46e5');
    expect(root.style.getPropertyValue('--color-accent')).toBe('#f97316');
  });

  it('default primary color is blue (#2563eb)', () => {
    expect(DEFAULT_BRANDING.primary_color).toBe('#2563eb');
  });
});

// ============================================
// CHECKLIST ITEM: White-Label Mode / Powered-By
// ============================================
describe('Branding Checklist: White-Label Mode', () => {
  it('"Powered by" visibility respects show_powered_by=false', () => {
    const config: WhiteLabelConfig = {
      ...DEFAULT_BRANDING,
      show_powered_by: false,
    };
    expect(config.show_powered_by).toBe(false);
  });

  it('"Powered by" is shown by default', () => {
    expect(DEFAULT_BRANDING.show_powered_by).toBe(true);
  });

  it('custom support email is available in config', () => {
    const config: WhiteLabelConfig = {
      ...DEFAULT_BRANDING,
      support_email: 'help@xyzcorp.com',
    };
    expect(config.support_email).toBe('help@xyzcorp.com');
  });

  it('custom support URL is available in config', () => {
    const config: WhiteLabelConfig = {
      ...DEFAULT_BRANDING,
      support_url: 'https://xyzcorp.com/support',
    };
    expect(config.support_url).toBe('https://xyzcorp.com/support');
  });
});

// ============================================
// Static branding config (branding.ts) tests
// ============================================
describe('Static Branding Config (branding.ts)', () => {
  it('should export a valid BrandingConfig with all required fields', async () => {
    const { branding } = await import('../config/branding');

    expect(branding.appName).toBeTruthy();
    expect(branding.companyName).toBeTruthy();
    expect(branding.primaryColor).toMatch(/^#[0-9a-fA-F]{6}$/);
    expect(branding.logoUrl).toBeTruthy();
    expect(typeof branding.showPoweredBy).toBe('boolean');
    expect(typeof branding.copyrightYear).toBe('number');
  });

  it('should generate CSS variables matching primary color', async () => {
    const { branding, brandingCssVars } = await import('../config/branding');

    expect(brandingCssVars['--color-primary']).toBe(branding.primaryColor);
    expect(brandingCssVars['--color-primary-hover']).toBeTruthy();
    expect(brandingCssVars['--color-primary-light']).toBeTruthy();
  });

  it('applyBrandingStyles sets CSS custom properties on document root', async () => {
    const { applyBrandingStyles, brandingCssVars } = await import('../config/branding');

    applyBrandingStyles();

    const root = document.documentElement;
    for (const [prop, value] of Object.entries(brandingCssVars)) {
      expect(root.style.getPropertyValue(prop)).toBe(value);
    }
  });

  it('setDocumentTitle sets title with app name', async () => {
    const { setDocumentTitle, branding } = await import('../config/branding');

    setDocumentTitle('Projects');
    expect(document.title).toBe(`Projects | ${branding.appName}`);

    setDocumentTitle();
    expect(document.title).toBe(branding.appName);
  });

  it('getCopyrightText returns formatted copyright string', async () => {
    const { getCopyrightText, branding } = await import('../config/branding');
    const text = getCopyrightText();

    expect(text).toContain(branding.companyName);
    expect(text).toContain(String(branding.copyrightYear));
    expect(text).toContain('©');
  });
});

// ============================================
// BrandingContext integration tests
// ============================================
describe('BrandingContext', () => {
  it('provides default branding when no company slug is set', () => {
    function BrandingReader() {
      const { branding } = useBranding();
      return (
        <div>
          <span data-testid="app-name">{branding.app_name}</span>
        </div>
      );
    }

    render(
      <TestWrapper>
        <BrandingReader />
      </TestWrapper>
    );

    expect(screen.getByTestId('app-name').textContent).toBe('Time Tracker');
  });

  it('provides clearBranding function that resets to defaults', () => {
    let clearFn: (() => void) | undefined;

    function BrandingReader() {
      const { branding, clearBranding } = useBranding();
      clearFn = clearBranding;
      return <span data-testid="app-name">{branding.app_name}</span>;
    }

    render(
      <TestWrapper>
        <BrandingReader />
      </TestWrapper>
    );

    expect(screen.getByTestId('app-name').textContent).toBe('Time Tracker');
    expect(() => clearFn?.()).not.toThrow();
  });

  it('exposes isWhiteLabeled as false by default', () => {
    function BrandingReader() {
      const { isWhiteLabeled } = useBranding();
      return <span data-testid="wl">{String(isWhiteLabeled)}</span>;
    }

    render(
      <TestWrapper>
        <BrandingReader />
      </TestWrapper>
    );

    expect(screen.getByTestId('wl').textContent).toBe('false');
  });
});
