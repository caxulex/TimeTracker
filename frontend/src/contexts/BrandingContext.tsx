/**
 * Branding Context
 * Provides dynamic white-label branding throughout the app
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
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

  // Initialize branding on mount
  useEffect(() => {
    async function loadBranding() {
      setIsLoading(true);
      try {
        const config = await initializeBranding();
        if (config) {
          setBranding(config);
          setIsWhiteLabeled(true);
          setSlug(getCompanySlug());
        }
      } catch (error) {
        console.error('Failed to load branding:', error);
      } finally {
        setIsLoading(false);
      }
    }
    
    loadBranding();
  }, []);

  // Set company and fetch branding
  const setCompany = async (slug: string) => {
    setIsLoading(true);
    setCompanySlug(slug);
    setSlug(slug);
    
    try {
      const config = await fetchBranding(slug);
      if (config) {
        setBranding(config);
        applyBrandingToDocument(config);
        setIsWhiteLabeled(true);
      }
    } catch (error) {
      console.error('Failed to fetch branding:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Clear branding and reset to default
  const clearBranding = () => {
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
  };

  // Refresh branding from API
  const refreshBranding = async () => {
    const slug = getCompanySlug();
    if (slug) {
      await setCompany(slug);
    }
  };

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
