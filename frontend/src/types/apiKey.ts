// ============================================
// API KEY TYPES - For AI Provider API Key Management
// SEC-020: Secure API Key Storage
// ============================================

/**
 * Supported AI providers
 */
export type AIProvider = 'gemini' | 'openai' | 'anthropic' | 'azure_openai' | 'other';

/**
 * API Key response from server (never contains actual key)
 */
export interface APIKey {
  id: number;
  provider: AIProvider;
  key_preview: string;  // e.g., "...xxxx"
  label: string | null;
  is_active: boolean;
  created_by: number;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  usage_count: number;
  notes: string | null;
}

/**
 * Request to create a new API key
 */
export interface APIKeyCreate {
  provider: AIProvider;
  api_key: string;
  label?: string;
  notes?: string;
}

/**
 * Request to update an existing API key
 */
export interface APIKeyUpdate {
  api_key?: string;
  label?: string;
  notes?: string;
  is_active?: boolean;
}

/**
 * Paginated list of API keys
 */
export interface APIKeyListResponse {
  items: APIKey[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/**
 * Result of testing an API key's connectivity
 */
export interface APIKeyTestResponse {
  success: boolean;
  provider: string;
  message: string;
  latency_ms?: number;
  model_available?: string;
}

/**
 * Information about a supported AI provider
 */
export interface AIProviderInfo {
  id: AIProvider;
  name: string;
  description: string;
  key_format_hint: string;
  documentation_url?: string;
}

/**
 * List of supported providers
 */
export interface SupportedProvidersResponse {
  providers: AIProviderInfo[];
}

/**
 * Encryption status response
 */
export interface EncryptionStatusResponse {
  configured: boolean;
  message: string;
}

/**
 * Query parameters for listing API keys
 */
export interface APIKeyListParams {
  page?: number;
  page_size?: number;
  provider?: AIProvider;
  active_only?: boolean;
}
