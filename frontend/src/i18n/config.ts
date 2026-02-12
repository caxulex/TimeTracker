// ============================================
// TIME TRACKER — i18n CONFIGURATION
// Phase 9A.1: Initialize react-i18next
// ============================================
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import translation resources
import en from './locales/en/translation.json';

export const defaultNS = 'translation';
export const resources = {
  en: { translation: en },
} as const;

i18n.use(initReactI18next).init({
  // Default and fallback language
  lng: 'en',
  fallbackLng: 'en',

  // Namespace configuration
  defaultNS,
  ns: [defaultNS],
  resources,

  // React already escapes output — no need for i18next to double-escape
  interpolation: {
    escapeValue: false,
  },

  // Don't suspend on initial load — we bundle the translations
  react: {
    useSuspense: false,
  },
});

export default i18n;
