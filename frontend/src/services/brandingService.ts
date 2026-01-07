/**
 * White-Label Branding Service
 * Fetches and applies dynamic branding based on company slug/domain
 */

// Get API URL from environment or use relative path
const API_URL = import.meta.env.VITE_API_URL || '';

/**
 * White-label configuration from API
 */
export interface WhiteLabelConfig {
  id: number;
  company_id: number;
  app_name: string;
  company_name: string;
  tagline: string | null;
  subdomain: string | null;
  custom_domain: string | null;
  logo_url: string | null;
  favicon_url: string | null;
  login_background_url: string | null;
  primary_color: string;
  secondary_color: string | null;
  accent_color: string | null;
  support_email: string | null;
  support_url: string | null;
  terms_url: string | null;
  privacy_url: string | null;
  show_powered_by: boolean;
}

/**
 * Company info from API
 */
export interface CompanyInfo {
  id: number;
  name: string;
  slug: string;
  email: string;
  phone: string | null;
  subscription_tier: string;
  status: string;
  trial_ends_at: string | null;
  max_users: number;
  max_projects: number;
  created_at: string;
}

/**
 * Local storage key for cached branding
 */
const BRANDING_CACHE_KEY = 'tt_branding_config';
const COMPANY_SLUG_KEY = 'tt_company_slug';

/**
 * Get company slug from URL parameter or storage
 */
export function getCompanySlug(): string | null {
  // First check URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const slugFromUrl = urlParams.get('company');
  
  if (slugFromUrl) {
    // Store for future use
    localStorage.setItem(COMPANY_SLUG_KEY, slugFromUrl);
    return slugFromUrl;
  }
  
  // Check stored slug
  return localStorage.getItem(COMPANY_SLUG_KEY);
}

/**
 * Set company slug in storage
 */
export function setCompanySlug(slug: string): void {
  localStorage.setItem(COMPANY_SLUG_KEY, slug);
}

/**
 * Clear company slug
 */
export function clearCompanySlug(): void {
  localStorage.removeItem(COMPANY_SLUG_KEY);
  localStorage.removeItem(BRANDING_CACHE_KEY);
}

/**
 * Fetch branding configuration for a company
 */
export async function fetchBranding(slug: string): Promise<WhiteLabelConfig | null> {
  try {
    const response = await fetch(`${API_URL}/api/companies/branding/${slug}`);
    
    if (!response.ok) {
      console.warn(`Could not fetch branding for ${slug}: ${response.status}`);
      return null;
    }
    
    const config: WhiteLabelConfig = await response.json();
    
    // Cache the config
    localStorage.setItem(BRANDING_CACHE_KEY, JSON.stringify(config));
    
    return config;
  } catch (error) {
    console.error('Error fetching branding:', error);
    return null;
  }
}

/**
 * Get cached branding config
 */
export function getCachedBranding(): WhiteLabelConfig | null {
  try {
    const cached = localStorage.getItem(BRANDING_CACHE_KEY);
    return cached ? JSON.parse(cached) : null;
  } catch {
    return null;
  }
}

/**
 * Fetch company info by slug
 */
export async function fetchCompanyInfo(slug: string): Promise<CompanyInfo | null> {
  try {
    const response = await fetch(`${API_URL}/api/companies/by-slug/${slug}`);
    
    if (!response.ok) {
      console.warn(`Could not fetch company info for ${slug}: ${response.status}`);
      return null;
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching company info:', error);
    return null;
  }
}

/**
 * Generate color variants
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
 * Apply branding to document
 */
export function applyBrandingToDocument(config: WhiteLabelConfig): void {
  const root = document.documentElement;
  
  // Apply primary color and variants
  root.style.setProperty('--color-primary', config.primary_color);
  root.style.setProperty('--color-primary-hover', adjustColorBrightness(config.primary_color, -10));
  root.style.setProperty('--color-primary-light', adjustColorBrightness(config.primary_color, 40));
  
  // Apply secondary and accent colors if present
  if (config.secondary_color) {
    root.style.setProperty('--color-secondary', config.secondary_color);
    root.style.setProperty('--color-secondary-hover', adjustColorBrightness(config.secondary_color, -10));
  }
  
  if (config.accent_color) {
    root.style.setProperty('--color-accent', config.accent_color);
  }
  
  // Update document title
  document.title = config.app_name;
  
  // Update favicon if provided
  if (config.favicon_url) {
    const link = document.querySelector("link[rel*='icon']") as HTMLLinkElement || document.createElement('link');
    link.type = 'image/x-icon';
    link.rel = 'shortcut icon';
    link.href = config.favicon_url;
    document.getElementsByTagName('head')[0].appendChild(link);
  }
  
  // Store for meta tag updates
  const metaDescription = document.querySelector('meta[name="description"]');
  if (metaDescription && config.tagline) {
    metaDescription.setAttribute('content', config.tagline);
  }
}

/**
 * Initialize branding on app load
 */
export async function initializeBranding(): Promise<WhiteLabelConfig | null> {
  const slug = getCompanySlug();
  
  if (!slug) {
    return null;
  }
  
  // Try cached first
  let config = getCachedBranding();
  
  // Fetch fresh in background
  const freshConfig = await fetchBranding(slug);
  
  if (freshConfig) {
    config = freshConfig;
    applyBrandingToDocument(config);
  } else if (config) {
    // Use cached if fresh failed
    applyBrandingToDocument(config);
  }
  
  return config;
}

/**
 * Default branding for non-white-labeled access
 */
export const DEFAULT_BRANDING: WhiteLabelConfig = {
  id: 0,
  company_id: 0,
  app_name: 'Time Tracker',
  company_name: 'Time Tracker',
  tagline: 'Track time. Boost productivity.',
  subdomain: null,
  custom_domain: null,
  logo_url: '/logo.svg',
  favicon_url: '/favicon.svg',
  login_background_url: null,
  primary_color: '#2563eb',
  secondary_color: '#1d4ed8',
  accent_color: '#f97316',
  support_email: 'support@example.com',
  support_url: '/help',
  terms_url: '/terms',
  privacy_url: '/privacy',
  show_powered_by: true,
};
