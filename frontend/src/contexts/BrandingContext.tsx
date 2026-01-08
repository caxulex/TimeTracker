/**
 * Branding Context
 * Provides dynamic white-label branding throughout the app
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import {
  WhiteLabelConfig,
  DEFAULT_BRANDING,
  initializeBranding,
  getCompanySlug,
  setCompanySlug,
  clearCompanySlug,
  applyBrandingToDocument,
  fetchBranding,
} from '../services/brandingService';

interface BrandingContextType {
  branding: WhiteLabelConfig;
  companySlug: string | null;
  isLoading: boolean;
  isWhiteLabeled: boolean;
  setCompany: (slug: string) => Promise<void>;
  clearBranding: () => void;
  refreshBranding: () => Promise<void>;
}

const BrandingContext = createContext<BrandingContextType | undefined>(undefined);

interface BrandingProviderProps {
  children: ReactNode;
}

export function BrandingProvider({ children }: BrandingProviderProps) {
  const [branding, setBranding] = useState<WhiteLabelConfig>(DEFAULT_BRANDING);
  const [companySlug, setSlug] = useState<string | null>(getCompanySlug());
  const [isLoading, setIsLoading] = useState(true);
  const [isWhiteLabeled, setIsWhiteLabeled] = useState(false);
  const [loadAttempted, setLoadAttempted] = useState(false);
  const lastFetchedSlugRef = useRef<string | null>(null);

  // Initialize branding on mount
  useEffect(() => {
    // Only attempt to load branding once to prevent infinite loops
    if (loadAttempted) return;

    async function loadBranding() {
      setIsLoading(true);
      setLoadAttempted(true);
      try {
        const config = await initializeBranding();
        if (config) {
          setBranding(config);
          setIsWhiteLabeled(true);
          setSlug(getCompanySlug());
        }
      } catch (error) {
        console.error('Failed to load branding:', error);
        // Use default branding on error - don't retry
        setBranding(DEFAULT_BRANDING);
      } finally {
        setIsLoading(false);
      }
    }
    
    loadBranding();
  }, [loadAttempted]);

  // Set company and fetch branding - memoized to prevent infinite loops
  const setCompany = useCallback(async (slug: string) => {
    // Prevent duplicate fetches for the same slug
    if (lastFetchedSlugRef.current === slug) {
      return;
    }
    lastFetchedSlugRef.current = slug;

    setIsLoading(true);
    setCompanySlug(slug);
    setSlug(slug);
    
    try {
      const config = await fetchBranding(slug);
      if (config) {
        setBranding(config);
        applyBrandingToDocument(config);
        setIsWhiteLabeled(true);
      } else {
        // If fetch failed, try to use default branding
        console.warn('Using default branding due to fetch failure');
        setBranding(DEFAULT_BRANDING);
      }
    } catch (error) {
      console.error('Failed to fetch branding:', error);
      // Use default branding on error
      setBranding(DEFAULT_BRANDING);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Clear branding and reset to default - memoized
  const clearBranding = useCallback(() => {
    lastFetchedSlugRef.current = null;
    clearCompanySlug();
    setBranding(DEFAULT_BRANDING);
    setSlug(null);
    setIsWhiteLabeled(false);
    
    // Reset document
    document.title = DEFAULT_BRANDING.app_name;
    const root = document.documentElement;
    root.style.setProperty('--color-primary', DEFAULT_BRANDING.primary_color);
    root.style.setProperty('--color-primary-hover', '#1d4ed8');
    root.style.setProperty('--color-primary-light', '#dbeafe');
  }, []);

  // Refresh branding from API - memoized
  const refreshBranding = useCallback(async () => {
    const slug = getCompanySlug();
    if (slug) {
      // Reset the ref to allow re-fetch
      lastFetchedSlugRef.current = null;
      await setCompany(slug);
    }
  }, [setCompany]);

  return (
    <BrandingContext.Provider
      value={{
        branding,
        companySlug,
        isLoading,
        isWhiteLabeled,
        setCompany,
        clearBranding,
        refreshBranding,
      }}
    >
      {children}
    </BrandingContext.Provider>
  );
}

/**
 * Hook to access branding context
 * Note: Hooks are allowed exports with Fast Refresh
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useBranding() {
  const context = useContext(BrandingContext);
  if (context === undefined) {
    throw new Error('useBranding must be used within a BrandingProvider');
  }
  return context;
}

export default BrandingContext;
