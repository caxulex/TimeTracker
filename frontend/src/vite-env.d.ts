/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_ENVIRONMENT?: string;
  readonly VITE_BASE_DOMAINS?: string;
  readonly VITE_APP_NAME?: string;
  readonly VITE_PRIMARY_COLOR?: string;
  readonly VITE_LOGO_URL?: string;
  readonly VITE_TAGLINE?: string;
  readonly VITE_SHOW_POWERED_BY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Injected by Vite define config — package.json version */
declare const __APP_VERSION__: string;
