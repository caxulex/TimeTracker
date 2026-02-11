/**
 * Vite Plugin: Dynamic PWA Manifest Generator
 * TASK 5.2: Generates manifest.json from environment variables at build time.
 *
 * Reads:
 *   - VITE_APP_NAME → manifest.name and short_name
 *   - VITE_PRIMARY_COLOR → manifest.theme_color
 *   - VITE_LOGO_URL → manifest.icons (if set and local)
 *   - VITE_TAGLINE → manifest.description
 *
 * Falls back to sensible defaults so existing behavior is preserved
 * when no custom env vars are set.
 */
import type { Plugin, ResolvedConfig } from 'vite';
import { writeFileSync, existsSync, readFileSync } from 'fs';
import { resolve } from 'path';

interface ManifestIcon {
  src: string;
  sizes: string;
  type: string;
  purpose?: string;
}

interface WebAppManifest {
  name: string;
  short_name: string;
  description: string;
  start_url: string;
  display: string;
  background_color: string;
  theme_color: string;
  orientation: string;
  icons: ManifestIcon[];
  [key: string]: unknown;
}

/**
 * Truncate a string for short_name (max 12 chars recommended by spec)
 */
function truncateShortName(name: string, maxLength = 12): string {
  if (name.length <= maxLength) return name;
  return name.slice(0, maxLength).trim();
}

/**
 * Determine icon type from URL/path extension
 */
function getIconType(url: string): string {
  if (url.endsWith('.svg')) return 'image/svg+xml';
  if (url.endsWith('.png')) return 'image/png';
  if (url.endsWith('.ico')) return 'image/x-icon';
  if (url.endsWith('.jpg') || url.endsWith('.jpeg')) return 'image/jpeg';
  if (url.endsWith('.webp')) return 'image/webp';
  return 'image/png';
}

/**
 * Read existing manifest.json and merge with env-driven values.
 * This preserves any hand-edited fields while overriding branding ones.
 */
function readExistingManifest(publicDir: string): Partial<WebAppManifest> {
  const manifestPath = resolve(publicDir, 'manifest.json');
  if (existsSync(manifestPath)) {
    try {
      return JSON.parse(readFileSync(manifestPath, 'utf-8'));
    } catch {
      // Corrupted manifest — start fresh
      return {};
    }
  }
  return {};
}

export default function dynamicManifestPlugin(): Plugin {
  let config: ResolvedConfig;

  return {
    name: 'vite-plugin-dynamic-manifest',
    configResolved(resolvedConfig) {
      config = resolvedConfig;
    },
    buildStart() {
      const env = config.env || {};
      const publicDir = config.publicDir;

      const appName = env.VITE_APP_NAME || 'Time Tracker';
      const primaryColor = env.VITE_PRIMARY_COLOR || '#2563eb';
      const logoUrl = env.VITE_LOGO_URL || '/logo.svg';
      const tagline = env.VITE_TAGLINE || 'Track time. Boost productivity.';

      // Read existing manifest to preserve non-branding fields
      const existing = readExistingManifest(publicDir);

      // Build icons array
      const icons: ManifestIcon[] = [];

      // If logo is a local path (starts with /), use it
      if (logoUrl.startsWith('/')) {
        const iconType = getIconType(logoUrl);
        icons.push(
          { src: logoUrl, sizes: 'any', type: iconType, purpose: 'any maskable' },
          { src: logoUrl, sizes: '192x192', type: iconType },
          { src: logoUrl, sizes: '512x512', type: iconType },
        );
      } else if (existing.icons && existing.icons.length > 0) {
        // Keep existing icons if logo is an external URL
        icons.push(...existing.icons);
      } else {
        // Absolute fallback
        icons.push(
          { src: '/logo.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
          { src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
        );
      }

      const themeColor = primaryColor.startsWith('#') ? primaryColor : `#${primaryColor}`;

      const manifest: WebAppManifest = {
        // Preserve any extra fields from existing manifest
        ...existing,
        // Override branding fields
        name: appName,
        short_name: truncateShortName(appName),
        description: tagline,
        start_url: (existing.start_url as string) || '/',
        display: (existing.display as string) || 'standalone',
        background_color: (existing.background_color as string) || '#ffffff',
        theme_color: themeColor,
        orientation: (existing.orientation as string) || 'portrait-primary',
        icons,
      };

      const manifestPath = resolve(publicDir, 'manifest.json');
      writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');

      // Log in dev for visibility
      if (config.command === 'serve') {
        console.log(`[manifest] Generated manifest.json → name="${appName}", theme_color="${themeColor}"`);
      }
    },
  };
}
