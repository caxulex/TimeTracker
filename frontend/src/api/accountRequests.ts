// ============================================
// ACCOUNT REQUESTS API CLIENT
// ============================================
import apiClient from './client';
import type {
  AccountRequestCreate,
  AccountRequestResponse,
  ApprovalDecision,
  PaginatedAccountRequests,
  AccountRequestFilters,
} from '../types/accountRequest';

const BASE_URL = '/account-requests';

export const accountRequestsApi = {
  /**
   * Submit a new account request (Public - no auth required)
   */
  async submit(data: AccountRequestCreate): Promise<AccountRequestResponse> {
    const response = await apiClient.post(BASE_URL, data);
    return response.data;
  },

  /**
   * Get all account requests with filters (Admin only)
   */
  async getAll(filters?: AccountRequestFilters): Promise<PaginatedAccountRequests> {
    const response = await apiClient.get(BASE_URL, { params: filters });
    return response.data;
  },

  /**
   * Get a single account request by ID (Admin only)
   */
  async getById(id: number): Promise<AccountRequestResponse> {
    const response = await apiClient.get(`${BASE_URL}/${id}`);
    return response.data;
  },

  /**
   * Approve an account request (Admin only)
   * Returns pre-filled data for staff creation wizard
   */
  async approve(id: number, decision: ApprovalDecision): Promise<{
    request_id: number;
    prefill_data: {
      name: string;
      email: string;
      phone: string | null;
      job_title: string | null;
      department: string | null;
    };
  }> {
    const response = await apiClient.post(`${BASE_URL}/${id}/approve`, decision);
    return response.data;
  },

  /**
   * Reject an account request (Admin only)
   */
  async reject(id: number, decision: ApprovalDecision): Promise<AccountRequestResponse> {
    const response = await apiClient.post(`${BASE_URL}/${id}/reject`, decision);
    return response.data;
  },

  /**
   * Delete an account request (Admin only)
   */
  async delete(id: number): Promise<void> {
    await apiClient.delete(`${BASE_URL}/${id}`);
  },
};
