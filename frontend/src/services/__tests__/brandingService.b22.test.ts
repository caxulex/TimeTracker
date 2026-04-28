/**
 * B22: brandingService.applyBrandingToDocument validation tests.
 *
 * Verifies:
 *  - Valid https favicon URL is applied to a `<link rel="icon">` node.
 *  - `javascript:` and `data:` favicon URLs are rejected; default kept.
 *  - Invalid hex color (`#xyz`) is rejected; CSS variable left untouched.
 *  - Repeated calls reuse the existing favicon link (no duplicates).
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  applyBrandingToDocument,
  isValidFaviconUrl,
  isValidHexColor,
  type WhiteLabelConfig,
} from '../brandingService';

function baseConfig(overrides: Partial<WhiteLabelConfig> = {}): WhiteLabelConfig {
  return {
    id: 1,
    company_id: 1,
    app_name: 'Test App',
    company_name: 'Test',
    tagline: null,
    subdomain: null,
    custom_domain: null,
    logo_url: null,
    favicon_url: null,
    login_background_url: null,
    primary_color: '#2563eb',
    secondary_color: null,
    accent_color: null,
    support_email: null,
    support_url: null,
    terms_url: null,
    privacy_url: null,
    show_powered_by: true,
    ...overrides,
  };
}

beforeEach(() => {
  // Reset the document head to a known state before each test.
  document.head.innerHTML = '';
  // Clear inline styles on <html> set by previous tests.
  document.documentElement.removeAttribute('style');
});

describe('isValidFaviconUrl', () => {
  it('accepts https URLs with image extensions', () => {
    expect(isValidFaviconUrl('https://cdn.example.com/icon.png')).toBe(true);
    expect(isValidFaviconUrl('https://x.test/favicon.ico?v=2')).toBe(true);
    expect(isValidFaviconUrl('https://x.test/logo.SVG')).toBe(true);
  });

  it('accepts same-origin paths starting with /', () => {
    expect(isValidFaviconUrl('/favicon.ico')).toBe(true);
    expect(isValidFaviconUrl('/static/img/icon.png')).toBe(true);
  });

  it('rejects javascript: / data: / vbscript: / http: URLs', () => {
    expect(isValidFaviconUrl('javascript:alert(1)')).toBe(false);
    expect(isValidFaviconUrl('data:image/png;base64,iVBORw0KG')).toBe(false);
    expect(isValidFaviconUrl('vbscript:msgbox(1)')).toBe(false);
    expect(isValidFaviconUrl('http://example.com/icon.png')).toBe(false);
  });

  it('rejects non-string input', () => {
    expect(isValidFaviconUrl(undefined)).toBe(false);
    expect(isValidFaviconUrl(null)).toBe(false);
    expect(isValidFaviconUrl(123)).toBe(false);
    expect(isValidFaviconUrl('')).toBe(false);
  });
});

describe('isValidHexColor', () => {
  it('accepts #RRGGBB and #RRGGBBAA', () => {
    expect(isValidHexColor('#2563eb')).toBe(true);
    expect(isValidHexColor('#ABCDEF')).toBe(true);
    expect(isValidHexColor('#11223344')).toBe(true);
  });

  it('rejects shorthand, named colors, and garbage', () => {
    expect(isValidHexColor('#fff')).toBe(false);
    expect(isValidHexColor('#xyz')).toBe(false);
    expect(isValidHexColor('red')).toBe(false);
    expect(isValidHexColor('rgb(0,0,0)')).toBe(false);
    expect(isValidHexColor('')).toBe(false);
    expect(isValidHexColor(undefined)).toBe(false);
  });
});

describe('applyBrandingToDocument', () => {
  it('applies a valid https favicon URL to a single <link rel="icon">', () => {
    applyBrandingToDocument(
      baseConfig({ favicon_url: 'https://cdn.example.com/icon.png' })
    );

    const links = document.querySelectorAll('link[rel="icon"]');
    expect(links.length).toBe(1);
    expect((links[0] as HTMLLinkElement).href).toContain('icon.png');
  });

  it('rejects a javascript: favicon URL and does not mutate the DOM', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    applyBrandingToDocument(
      baseConfig({ favicon_url: 'javascript:alert(1)' })
    );

    expect(document.querySelectorAll('link[rel="icon"]').length).toBe(0);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('rejects a data: favicon URL', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    applyBrandingToDocument(
      baseConfig({ favicon_url: 'data:image/png;base64,AAAA' })
    );

    expect(document.querySelectorAll('link[rel="icon"]').length).toBe(0);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('rejects an invalid #xyz primary color and leaves --color-primary unset', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    applyBrandingToDocument(
      baseConfig({ primary_color: '#xyz' as unknown as string })
    );

    expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe('');
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('reuses the existing favicon link on a second call (no duplicates)', () => {
    applyBrandingToDocument(
      baseConfig({ favicon_url: 'https://cdn.example.com/first.png' })
    );
    applyBrandingToDocument(
      baseConfig({ favicon_url: 'https://cdn.example.com/second.png' })
    );

    const links = document.querySelectorAll('link[rel="icon"]');
    expect(links.length).toBe(1);
    expect((links[0] as HTMLLinkElement).href).toContain('second.png');
  });

  it('reuses a pre-existing rel="shortcut icon" node instead of duplicating', () => {
    const existing = document.createElement('link');
    existing.rel = 'shortcut icon';
    existing.href = 'https://cdn.example.com/legacy.png';
    document.head.appendChild(existing);

    applyBrandingToDocument(
      baseConfig({ favicon_url: 'https://cdn.example.com/new.png' })
    );

    const allIcons = document.querySelectorAll(
      'link[rel="icon"], link[rel="shortcut icon"]'
    );
    expect(allIcons.length).toBe(1);
    expect((allIcons[0] as HTMLLinkElement).href).toContain('new.png');
  });
});
