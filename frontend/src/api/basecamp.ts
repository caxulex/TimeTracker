// ============================================
// TIME TRACKER - BASECAMP INTEGRATION API
// ============================================
// Typed wrappers around /api/integrations/basecamp/* endpoints.
// Backend auth: super_admin for connect/sync/disconnect; admin or super_admin for status.
// ============================================

import api from './client';

export interface BasecampStatus {
  connected: boolean;
  account_name: string | null;
  last_sync_at: string | null;
  expires_at: string | null;
}

export interface BasecampSyncResult {
  created: number;
  updated: number;
  unchanged: number;
  errors: string[];
  dry_run: boolean;
}

export interface BasecampConnectResponse {
  authorization_url: string;
}

const BASE = '/api/integrations/basecamp';

export const basecampApi = {
  async getStatus(): Promise<BasecampStatus> {
    const { data } = await api.get<BasecampStatus>(`${BASE}/status`);
    return data;
  },

  async getConnectUrl(): Promise<BasecampConnectResponse> {
    const { data } = await api.get<BasecampConnectResponse>(`${BASE}/connect`);
    return data;
  },

  async sync(dryRun: boolean = false): Promise<BasecampSyncResult> {
    const { data } = await api.post<BasecampSyncResult>(`${BASE}/sync`, {
      dry_run: dryRun,
    });
    return data;
  },

  async disconnect(): Promise<void> {
    await api.delete(`${BASE}/disconnect`);
  },
};

export default basecampApi;
