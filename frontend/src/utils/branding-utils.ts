/**
 * Branding Utility Functions
 * Non-component exports for branding functionality
 * Moved from BrandingContext.tsx to fix Fast Refresh warning
 */

import { WhiteLabelConfig, DEFAULT_BRANDING } from '../services/brandingService';

/**
 * Get current branding values (for use outside React components)
 */
export function getCurrentBranding(): WhiteLabelConfig {
  const cached = localStorage.getItem('tt_branding_config');
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch {
      return DEFAULT_BRANDING;
    }
  }
  return DEFAULT_BRANDING;
}

/**
 * Get company slug from local storage
 */
export function getStoredCompanySlug(): string | null {
  return localStorage.getItem('tt_company_slug');
}

/**
 * Get login path based on current branding
 */
export function getLoginPath(): string {
  const slug = getStoredCompanySlug();
  return slug ? `/${slug}/login` : '/login';
}
