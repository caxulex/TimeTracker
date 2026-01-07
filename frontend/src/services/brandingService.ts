/**
 * White-Label Branding Service
 * Fetches and applies dynamic branding based on company slug/domain
 */

// Get API URL from environment or use /api as default
const API_URL = import.meta.env.VITE_API_URL || '/api';

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
 * Known base domains - requests from these domains are NOT white-labeled
 * Add your production domain(s) here
 */
const BASE_DOMAINS = [
  'timetracker.shaemarcus.com',
  'localhost',
  '127.0.0.1',
];

/**
 * Extract company slug from subdomain
 * e.g., xyz-corp.timetracker.shaemarcus.com -> xyz-corp
 */
function getSlugFromSubdomain(): string | null {
  const hostname = window.location.hostname;
  
  // Skip if localhost or IP address
  if (hostname === 'localhost' || /^\d+\.\d+\.\d+\.\d+$/.test(hostname)) {
    return null;
  }
  
  // Check if this is a subdomain of any base domain
  for (const baseDomain of BASE_DOMAINS) {
    if (hostname === baseDomain) {
      // This is the base domain, no subdomain
      return null;
    }
    
    if (hostname.endsWith(`.${baseDomain}`)) {
      // Extract subdomain: xyz-corp.timetracker.shaemarcus.com -> xyz-corp
      const subdomain = hostname.slice(0, -(baseDomain.length + 1));
      
      // Ignore common subdomains like www, api, staging
      if (['www', 'api', 'staging', 'admin', 'app'].includes(subdomain)) {
        return null;
      }
      
      return subdomain;
    }
  }
  
  // Custom domain - look up by full hostname
  return `domain:${hostname}`;
}

/**
 * Get company slug from subdomain, URL parameter, or storage
 * Priority: subdomain > URL param > stored
 */
export function getCompanySlug(): string | null {
  // First priority: subdomain detection
  const subdomainSlug = getSlugFromSubdomain();
  if (subdomainSlug) {
    // Store for future use within this session
    localStorage.setItem(COMPANY_SLUG_KEY, subdomainSlug);
    return subdomainSlug;
  }
  
  // Second priority: URL parameters (for testing)
  const urlParams = new URLSearchParams(window.location.search);
  const slugFromUrl = urlParams.get('company');
  
  if (slugFromUrl) {
    // Store for future use
    localStorage.setItem(COMPANY_SLUG_KEY, slugFromUrl);
    return slugFromUrl;
  }
  
  // Third: Check stored slug (only if not on base domain)
  // This prevents slug "sticking" when navigating from subdomain to main site
  const hostname = window.location.hostname;
  const isBaseDomain = BASE_DOMAINS.some(d => hostname === d || hostname.startsWith('localhost'));
  
  if (!isBaseDomain) {
    return localStorage.getItem(COMPANY_SLUG_KEY);
  }
  
  return null;
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
 * Supports both slug lookup and custom domain lookup
 */
export async function fetchBranding(slugOrDomain: string): Promise<WhiteLabelConfig | null> {
  try {
    let endpoint: string;
    
    // Check if this is a custom domain lookup (domain:hostname format)
    if (slugOrDomain.startsWith('domain:')) {
      const domain = slugOrDomain.slice(7); // Remove 'domain:' prefix
      endpoint = `${API_URL}/companies/branding/by-domain/${encodeURIComponent(domain)}`;
    } else {
      endpoint = `${API_URL}/companies/branding/${slugOrDomain}`;
    }
    
    const response = await fetch(endpoint);
    
    if (!response.ok) {
      console.warn(`Could not fetch branding for ${slugOrDomain}: ${response.status}`);
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
    const response = await fetch(`${API_URL}/companies/by-slug/${slug}`);
    
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
