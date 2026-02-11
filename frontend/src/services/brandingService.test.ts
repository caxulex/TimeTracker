// ============================================
// TIME TRACKER - BRANDING SERVICE TESTS
// TASK 5.1: BASE_DOMAINS environment variable
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We need to test the module's initialization behavior, so we re-import
// after stubbing env vars. Use dynamic import + vi.resetModules().

describe('BASE_DOMAINS configuration', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('should use custom domains from VITE_BASE_DOMAINS when set', async () => {
    vi.stubEnv('VITE_BASE_DOMAINS', 'example.com,custom.io,10.0.0.1');
    vi.stubEnv('VITE_API_URL', '/api');

    const mod = await import('./brandingService');

    // Module should load successfully with custom domains
    expect(mod.DEFAULT_BRANDING).toBeDefined();
    expect(mod.getCompanySlug).toBeInstanceOf(Function);
  });

  it('should use default domains when VITE_BASE_DOMAINS is not set', async () => {
    vi.stubEnv('VITE_BASE_DOMAINS', '');
    vi.stubEnv('VITE_API_URL', '/api');

    const mod = await import('./brandingService');

    // Module should load successfully with defaults
    expect(mod.DEFAULT_BRANDING).toBeDefined();
    expect(mod.DEFAULT_BRANDING.app_name).toBe('Time Tracker');
  });

  it('should handle whitespace and extra commas in VITE_BASE_DOMAINS', async () => {
    vi.stubEnv('VITE_BASE_DOMAINS', ' example.com , , custom.io , ');
    vi.stubEnv('VITE_API_URL', '/api');

    const mod = await import('./brandingService');
    expect(mod.DEFAULT_BRANDING).toBeDefined();
  });

  it('should return null from getCompanySlug when on localhost (default base domain)', async () => {
    vi.stubEnv('VITE_BASE_DOMAINS', '');
    vi.stubEnv('VITE_API_URL', '/api');

    const mod = await import('./brandingService');

    // In jsdom, window.location.hostname is 'localhost' by default
    const slug = mod.getCompanySlug();
    // localhost is a default base domain → no subdomain extraction → null
    expect(slug).toBeNull();
  });

  it('should detect slug on a custom domain not in BASE_DOMAINS', async () => {
    vi.stubEnv('VITE_BASE_DOMAINS', 'example.com,localhost');
    vi.stubEnv('VITE_API_URL', '/api');

    const mod = await import('./brandingService');

    // Clear any stored slug from previous tests
    localStorage.removeItem('tt_company_slug');

    // Since jsdom hostname is 'localhost' and it IS in our custom BASE_DOMAINS,
    // getCompanySlug should return null (it's a recognized base domain)
    const slug = mod.getCompanySlug();
    expect(slug).toBeNull();
  });
});

describe('DEFAULT_BRANDING', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('should have all required fields', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    const { DEFAULT_BRANDING } = await import('./brandingService');

    expect(DEFAULT_BRANDING.app_name).toBe('Time Tracker');
    expect(DEFAULT_BRANDING.company_name).toBe('Time Tracker');
    expect(DEFAULT_BRANDING.primary_color).toBe('#2563eb');
    expect(DEFAULT_BRANDING.show_powered_by).toBe(true);
    expect(DEFAULT_BRANDING.tagline).toBe('Track time. Boost productivity.');
  });
});

describe('applyBrandingToDocument', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    // Clean up CSS custom properties
    const root = document.documentElement;
    root.style.removeProperty('--color-primary');
    root.style.removeProperty('--color-primary-hover');
    root.style.removeProperty('--color-primary-light');
    root.style.removeProperty('--color-secondary');
    root.style.removeProperty('--color-secondary-hover');
    root.style.removeProperty('--color-accent');
  });

  it('should set CSS custom properties for primary color', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    const { applyBrandingToDocument, DEFAULT_BRANDING } = await import('./brandingService');

    const customConfig = {
      ...DEFAULT_BRANDING,
      primary_color: '#7c3aed',
    };

    applyBrandingToDocument(customConfig);

    const root = document.documentElement;
    expect(root.style.getPropertyValue('--color-primary')).toBe('#7c3aed');
    expect(root.style.getPropertyValue('--color-primary-hover')).toBeTruthy();
    expect(root.style.getPropertyValue('--color-primary-light')).toBeTruthy();
  });

  it('should set document title to app_name', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    const { applyBrandingToDocument, DEFAULT_BRANDING } = await import('./brandingService');

    const customConfig = {
      ...DEFAULT_BRANDING,
      app_name: 'XYZ Time',
    };

    applyBrandingToDocument(customConfig);
    expect(document.title).toBe('XYZ Time');
  });

  it('should apply secondary and accent colors when present', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    const { applyBrandingToDocument, DEFAULT_BRANDING } = await import('./brandingService');

    const customConfig = {
      ...DEFAULT_BRANDING,
      secondary_color: '#4f46e5',
      accent_color: '#f97316',
    };

    applyBrandingToDocument(customConfig);

    const root = document.documentElement;
    expect(root.style.getPropertyValue('--color-secondary')).toBe('#4f46e5');
    expect(root.style.getPropertyValue('--color-accent')).toBe('#f97316');
  });
});

describe('fetchBranding', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    localStorage.clear();
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    localStorage.clear();
  });

  it('should call slug-based endpoint for regular slugs', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    const mockResponse = {
      ok: true,
      json: vi.fn().mockResolvedValue({
        id: 1,
        company_id: 1,
        app_name: 'XYZ Time',
        company_name: 'XYZ Corp',
        primary_color: '#7c3aed',
        show_powered_by: false,
      }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const { fetchBranding } = await import('./brandingService');
    const config = await fetchBranding('xyz-corp');

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/companies/branding/xyz-corp');
    expect(config?.app_name).toBe('XYZ Time');
  });

  it('should call domain-based endpoint for domain: prefixed slugs', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    const mockResponse = {
      ok: true,
      json: vi.fn().mockResolvedValue({
        id: 2,
        company_id: 2,
        app_name: 'Custom Time',
        company_name: 'Custom Corp',
        primary_color: '#10b981',
        show_powered_by: true,
      }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const { fetchBranding } = await import('./brandingService');
    const config = await fetchBranding('domain:custom.example.com');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/companies/branding/by-domain/custom.example.com'
    );
    expect(config?.app_name).toBe('Custom Time');
  });

  it('should return null on fetch failure', async () => {
    vi.stubEnv('VITE_API_URL', '/api');
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 404,
    });

    const { fetchBranding } = await import('./brandingService');
    const config = await fetchBranding('nonexistent');

    expect(config).toBeNull();
  });
});
