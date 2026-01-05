// ============================================
// TIME TRACKER - BRANDING CONFIGURATION
// ============================================
// This file centralizes all branding/white-labeling settings.
// Customize these values via environment variables for each client deployment.
//
// Environment Variables (set in .env.local or .env.production):
// - VITE_APP_NAME: Application name displayed in UI
// - VITE_COMPANY_NAME: Company name for footer/legal text
// - VITE_LOGO_URL: Path to custom logo (relative to public folder or absolute URL)
// - VITE_FAVICON_URL: Path to custom favicon
// - VITE_PRIMARY_COLOR: Primary brand color (hex without #)
// - VITE_SUPPORT_EMAIL: Support contact email
// - VITE_SUPPORT_URL: Support/help documentation URL
// - VITE_TERMS_URL: Terms of Service URL
// - VITE_PRIVACY_URL: Privacy Policy URL
// ============================================

/**
 * Branding configuration interface
 */
export interface BrandingConfig {
  // Application Identity
  appName: string;
  companyName: string;
  tagline: string;
  
  // Visual Assets
  logoUrl: string;
  logoAlt: string;
  faviconUrl: string;
  
  // Theme Colors (can be extended for full theme customization)
  primaryColor: string;
  primaryColorHover: string;
  primaryColorLight: string;
  
  // Contact & Support
  supportEmail: string;
  supportUrl: string;
  
  // Legal Links
  termsUrl: string;
  privacyUrl: string;
  
  // Footer
  copyrightYear: number;
  showPoweredBy: boolean;
}

/**
 * Helper to get hex color with proper formatting
 */
function getColorValue(envValue: string | undefined, defaultValue: string): string {
  if (!envValue) return defaultValue;
  // Ensure it starts with # for hex colors
  return envValue.startsWith('#') ? envValue : `#${envValue}`;
}

/**
 * Generate lighter/darker variants of a color
 */
function adjustColorBrightness(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16);
  const amt = Math.round(2.55 * percent);
  const R = (num >> 16) + amt;
  const G = (num >> 8 & 0x00FF) + amt;
  const B = (num & 0x0000FF) + amt;
  
  return '#' + (
    0x1000000 +
    (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
    (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
    (B < 255 ? (B < 1 ? 0 : B) : 255)
  ).toString(16).slice(1);
}

/**
 * Default branding values - override via environment variables
 */
const DEFAULT_CONFIG: BrandingConfig = {
  // Application Identity
  appName: 'Time Tracker',
  companyName: 'Your Company',
  tagline: 'Track time. Boost productivity.',
  
  // Visual Assets
  logoUrl: '/logo.svg',
  logoAlt: 'Time Tracker Logo',
  faviconUrl: '/favicon.svg',
  
  // Theme Colors
  primaryColor: '#2563eb', // Blue-600
  primaryColorHover: '#1d4ed8', // Blue-700
  primaryColorLight: '#dbeafe', // Blue-100
  
  // Contact & Support
  supportEmail: 'support@example.com',
  supportUrl: '/help',
  
  // Legal Links
  termsUrl: '/terms',
  privacyUrl: '/privacy',
  
  // Footer
  copyrightYear: new Date().getFullYear(),
  showPoweredBy: true,
};

/**
 * Get primary color from environment
 */
const primaryColor = getColorValue(
  import.meta.env.VITE_PRIMARY_COLOR,
  DEFAULT_CONFIG.primaryColor
);

/**
 * Branding configuration - reads from environment variables with defaults
 */
export const branding: BrandingConfig = {
  // Application Identity
  appName: import.meta.env.VITE_APP_NAME || DEFAULT_CONFIG.appName,
  companyName: import.meta.env.VITE_COMPANY_NAME || DEFAULT_CONFIG.companyName,
  tagline: import.meta.env.VITE_TAGLINE || DEFAULT_CONFIG.tagline,
  
  // Visual Assets
  logoUrl: import.meta.env.VITE_LOGO_URL || DEFAULT_CONFIG.logoUrl,
  logoAlt: `${import.meta.env.VITE_APP_NAME || DEFAULT_CONFIG.appName} Logo`,
  faviconUrl: import.meta.env.VITE_FAVICON_URL || DEFAULT_CONFIG.faviconUrl,
  
  // Theme Colors
  primaryColor: primaryColor,
  primaryColorHover: adjustColorBrightness(primaryColor, -10),
  primaryColorLight: adjustColorBrightness(primaryColor, 40),
  
  // Contact & Support
  supportEmail: import.meta.env.VITE_SUPPORT_EMAIL || DEFAULT_CONFIG.supportEmail,
  supportUrl: import.meta.env.VITE_SUPPORT_URL || DEFAULT_CONFIG.supportUrl,
  
  // Legal Links
  termsUrl: import.meta.env.VITE_TERMS_URL || DEFAULT_CONFIG.termsUrl,
  privacyUrl: import.meta.env.VITE_PRIVACY_URL || DEFAULT_CONFIG.privacyUrl,
  
  // Footer
  copyrightYear: DEFAULT_CONFIG.copyrightYear,
  showPoweredBy: import.meta.env.VITE_SHOW_POWERED_BY !== 'false',
};

/**
 * CSS custom properties for dynamic theming
 * Apply these to :root in your CSS or inject via JavaScript
 */
export const brandingCssVars = {
  '--color-primary': branding.primaryColor,
  '--color-primary-hover': branding.primaryColorHover,
  '--color-primary-light': branding.primaryColorLight,
};

/**
 * Apply branding CSS variables to document root
 * Call this in your app initialization (e.g., main.tsx)
 */
export function applyBrandingStyles(): void {
  const root = document.documentElement;
  Object.entries(brandingCssVars).forEach(([property, value]) => {
    root.style.setProperty(property, value);
  });
}

/**
 * Update document title with app name
 */
export function setDocumentTitle(pageTitle?: string): void {
  document.title = pageTitle 
    ? `${pageTitle} | ${branding.appName}`
    : branding.appName;
}

/**
 * Get full copyright text
 */
export function getCopyrightText(): string {
  return `© ${branding.copyrightYear} ${branding.companyName}. All rights reserved.`;
}

export default branding;
