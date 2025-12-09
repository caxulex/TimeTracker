// ============================================
// ACCOUNT REQUEST TYPES
// ============================================

export interface AccountRequestCreate {
  name: string;
  email: string;
  phone?: string;
  job_title?: string;
  department?: string;
  message?: string;
}

export interface AccountRequestResponse {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  job_title: string | null;
  department: string | null;
  message: string | null;
  status: 'pending' | 'approved' | 'rejected';
  ip_address: string | null;
  user_agent: string | null;
  submitted_at: string;
  reviewed_at: string | null;
  reviewed_by: number | null;
  admin_notes: string | null;
  reviewer?: {
    id: number;
    name: string;
    email: string;
  };
}

export interface ApprovalDecision {
  admin_notes?: string;
}

export interface PaginatedAccountRequests {
  items: AccountRequestResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AccountRequestFilters {
  page?: number;
  page_size?: number;
  status?: 'pending' | 'approved' | 'rejected';
  search?: string;
}
