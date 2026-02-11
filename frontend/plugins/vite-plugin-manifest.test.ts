// ============================================
// TASK 5.2: Dynamic PWA Manifest Plugin tests
// ============================================
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'fs';
import { resolve } from 'path';
import { tmpdir } from 'os';
import dynamicManifestPlugin from './vite-plugin-manifest';

function createTempPublicDir(): string {
  return mkdtempSync(resolve(tmpdir(), 'manifest-test-'));
}

describe('vite-plugin-dynamic-manifest', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = createTempPublicDir();
  });

  afterEach(() => {
    rmSync(tempDir, { recursive: true, force: true });
  });

  function runPlugin(env: Record<string, string>, existingManifest?: object) {
    if (existingManifest) {
      writeFileSync(
        resolve(tempDir, 'manifest.json'),
        JSON.stringify(existingManifest),
        'utf-8'
      );
    }

    const plugin = dynamicManifestPlugin();

    // Simulate Vite's configResolved hook
    const mockConfig = {
      env,
      publicDir: tempDir,
      command: 'build' as const,
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (plugin as any).configResolved(mockConfig);

    // Simulate buildStart
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (plugin as any).buildStart();

    // Read generated manifest
    const manifestPath = resolve(tempDir, 'manifest.json');
    expect(existsSync(manifestPath)).toBe(true);
    return JSON.parse(readFileSync(manifestPath, 'utf-8'));
  }

  it('should generate manifest with default values when no env vars set', () => {
    const manifest = runPlugin({});

    expect(manifest.name).toBe('Time Tracker');
    expect(manifest.short_name).toBe('Time Tracker');
    expect(manifest.theme_color).toBe('#2563eb');
    expect(manifest.description).toBe('Track time. Boost productivity.');
    expect(manifest.icons.length).toBeGreaterThanOrEqual(2);
    expect(manifest.display).toBe('standalone');
  });

  it('should use VITE_APP_NAME for name and short_name', () => {
    const manifest = runPlugin({ VITE_APP_NAME: 'XYZ Time' });

    expect(manifest.name).toBe('XYZ Time');
    expect(manifest.short_name).toBe('XYZ Time');
  });

  it('should truncate short_name when app name exceeds 12 chars', () => {
    const manifest = runPlugin({ VITE_APP_NAME: 'Very Long Application Name' });

    expect(manifest.name).toBe('Very Long Application Name');
    expect(manifest.short_name).toBe('Very Long Ap');
  });

  it('should use VITE_PRIMARY_COLOR for theme_color', () => {
    const manifest = runPlugin({ VITE_PRIMARY_COLOR: '#7c3aed' });

    expect(manifest.theme_color).toBe('#7c3aed');
  });

  it('should add # prefix to theme_color if missing', () => {
    const manifest = runPlugin({ VITE_PRIMARY_COLOR: '10b981' });

    expect(manifest.theme_color).toBe('#10b981');
  });

  it('should use VITE_TAGLINE for description', () => {
    const manifest = runPlugin({ VITE_TAGLINE: 'Track Time Like a Pro' });

    expect(manifest.description).toBe('Track Time Like a Pro');
  });

  it('should use VITE_LOGO_URL for icons when local path', () => {
    const manifest = runPlugin({ VITE_LOGO_URL: '/custom-logo.png' });

    expect(manifest.icons[0].src).toBe('/custom-logo.png');
    expect(manifest.icons[0].type).toBe('image/png');
  });

  it('should preserve existing manifest fields not related to branding', () => {
    const existing = {
      name: 'Old Name',
      start_url: '/dashboard',
      categories: ['productivity'],
      lang: 'es',
    };

    const manifest = runPlugin({ VITE_APP_NAME: 'New Name' }, existing);

    expect(manifest.name).toBe('New Name'); // Overridden
    expect(manifest.start_url).toBe('/dashboard'); // Preserved
    expect(manifest.categories).toEqual(['productivity']); // Preserved
    expect(manifest.lang).toBe('es'); // Preserved
  });

  it('should keep existing icons when logo is an external URL', () => {
    const existing = {
      icons: [{ src: '/existing-icon.png', sizes: '512x512', type: 'image/png' }],
    };

    const manifest = runPlugin(
      { VITE_LOGO_URL: 'https://cdn.example.com/logo.png' },
      existing
    );

    expect(manifest.icons[0].src).toBe('/existing-icon.png');
  });
});
