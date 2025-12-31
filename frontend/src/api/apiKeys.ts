// ============================================
// API KEYS API CLIENT
// SEC-020: Secure API Key Storage
// ============================================
import apiClient from './client';
import type {
  APIKey,
  APIKeyCreate,
  APIKeyUpdate,
  APIKeyListResponse,
  APIKeyTestResponse,
  SupportedProvidersResponse,
  EncryptionStatusResponse,
  APIKeyListParams,
  AIProvider,
} from '../types/apiKey';

const BASE_URL = '/api/admin/api-keys';

export const apiKeysApi = {
  /**
   * Get all API keys (Super Admin only)
   */
  async getAll(params?: APIKeyListParams): Promise<APIKeyListResponse> {
    const response = await apiClient.get(BASE_URL, { params });
    return response.data;
  },

  /**
   * Get a single API key by ID (Super Admin only)
   */
  async getById(id: number): Promise<APIKey> {
    const response = await apiClient.get(`${BASE_URL}/${id}`);
    return response.data;
  },

  /**
   * Create a new API key (Super Admin only)
   */
  async create(data: APIKeyCreate): Promise<APIKey> {
    const response = await apiClient.post(BASE_URL, data);
    return response.data;
  },

  /**
   * Update an existing API key (Super Admin only)
   */
  async update(id: number, data: APIKeyUpdate): Promise<APIKey> {
    const response = await apiClient.put(`${BASE_URL}/${id}`, data);
    return response.data;
  },

  /**
   * Delete an API key (Super Admin only)
   */
  async delete(id: number): Promise<void> {
    await apiClient.delete(`${BASE_URL}/${id}`);
  },

  /**
   * Test an API key's connectivity (Super Admin only)
   */
  async test(id: number): Promise<APIKeyTestResponse> {
    const response = await apiClient.post(`${BASE_URL}/${id}/test`);
    return response.data;
  },

  /**
   * Get list of supported AI providers
   */
  async getSupportedProviders(): Promise<SupportedProvidersResponse> {
    const response = await apiClient.get(`${BASE_URL}/providers`);
    return response.data;
  },

  /**
   * Check encryption configuration status (Super Admin only)
   */
  async getEncryptionStatus(): Promise<EncryptionStatusResponse> {
    const response = await apiClient.get(`${BASE_URL}/encryption-status`);
    return response.data;
  },

  /**
   * Utility: Format provider name for display
   */
  formatProviderName(provider: AIProvider): string {
    const names: Record<AIProvider, string> = {
      gemini: 'Google Gemini',
      openai: 'OpenAI',
      anthropic: 'Anthropic',
      azure_openai: 'Azure OpenAI',
      other: 'Other',
    };
    return names[provider] || provider;
  },

  /**
   * Utility: Get provider icon class
   */
  getProviderIcon(provider: AIProvider): string {
    const icons: Record<AIProvider, string> = {
      gemini: '✨',
      openai: '🤖',
      anthropic: '🧠',
      azure_openai: '☁️',
      other: '🔑',
    };
    return icons[provider] || '🔑';
  },
};
