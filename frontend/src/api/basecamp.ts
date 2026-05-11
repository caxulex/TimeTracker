// ============================================
// TIME TRACKER - BASECAMP INTEGRATION API
// ============================================
// Typed wrappers around /api/integrations/basecamp/* endpoints.
// Backend auth: super_admin for connect/sync/settings/disconnect;
// admin or super_admin for status.
// ============================================

import api from './client';

export interface BasecampStatus {
  connected: boolean;
  account_name: string | null;
  last_sync_at: string | null;
  expires_at: string | null;
  target_team_id: number | null;
  target_team_name: string | null;
  auto_sync_enabled: boolean;
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

export interface BasecampSettingsUpdate {
  target_team_id?: number | null;
  auto_sync_enabled?: boolean;
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

  async updateSettings(settings: BasecampSettingsUpdate): Promise<BasecampStatus> {
    const { data } = await api.patch<BasecampStatus>(
      `${BASE}/settings`,
      settings
    );
    return data;
  },

  async disconnect(): Promise<void> {
    await api.delete(`${BASE}/disconnect`);
  },
};

export default basecampApi;
