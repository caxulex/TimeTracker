// ============================================
// TIME TRACKER - ACCOUNT REQUESTS MANAGEMENT PAGE (Admin)
// ============================================
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../components/common';
import { accountRequestsApi } from '../api/accountRequests';
import { useNotifications } from '../hooks/useNotifications';
import type { AccountRequestResponse, AccountRequestFilters } from '../types/accountRequest';

type StatusTab = 'pending' | 'approved' | 'rejected' | 'all';

export function AccountRequestsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<StatusTab>('pending');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRequest, setSelectedRequest] = useState<AccountRequestResponse | null>(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [showRejectionModal, setShowRejectionModal] = useState(false);
  const [adminNotes, setAdminNotes] = useState('');
  const [prefillData, setPrefillData] = useState<{
    name: string;
    email: string;
    phone: string | null;
    job_title: string | null;
    department: string | null;
  } | null>(null);
  
  const queryClient = useQueryClient();
  const { addNotification } = useNotifications();

  // Build filters
  const filters: AccountRequestFilters = {
    page: currentPage,
    page_size: 20,
    ...(activeTab !== 'all' && { status: activeTab }),
    ...(searchQuery && { search: searchQuery }),
  };

  // Fetch requests
  const { data, isLoading, error } = useQuery({
    queryKey: ['accountRequests', filters],
    queryFn: () => accountRequestsApi.getAll(filters),
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes?: string }) =>
      accountRequestsApi.approve(id, { admin_notes: notes }),
    onSuccess: (response, variables) => {
      queryClient.invalidateQueries({ queryKey: ['accountRequests'] });
      addNotification({
        type: 'success',
        title: 'Request Approved',
        message: 'Account request approved. Opening staff creation wizard...',
      });
      setShowApprovalModal(false);
      setAdminNotes('');
      setSelectedRequest(null);
      
      // Navigate to staff page with pre-filled data
      navigate('/staff', {
        state: {
          initialData: {
            name: response.prefill_data.name,
            email: response.prefill_data.email,
            phone: response.prefill_data.phone || '',
            job_title: response.prefill_data.job_title || '',
            department: response.prefill_data.department || '',
            role: 'regular_user',
          },
          requestId: variables.id,
          fromAccountRequest: true,
        }
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Approval Failed',
        message: 'Failed to approve request. Please try again.',
      });
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes?: string }) =>
      accountRequestsApi.reject(id, { admin_notes: notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accountRequests'] });
      addNotification({
        type: 'success',
        title: 'Request Rejected',
        message: 'Account request has been rejected.',
      });
      setShowRejectionModal(false);
      setSelectedRequest(null);
      setAdminNotes('');
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Rejection Failed',
        message: 'Failed to reject request. Please try again.',
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => accountRequestsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accountRequests'] });
      addNotification({
        type: 'success',
        title: 'Request Deleted',
        message: 'Account request has been deleted.',
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Deletion Failed',
        message: 'Failed to delete request. Please try again.',
      });
    },
  });

  const handleApprove = (request: AccountRequestResponse) => {
    setSelectedRequest(request);
    setShowApprovalModal(true);
  };

  const handleReject = (request: AccountRequestResponse) => {
    setSelectedRequest(request);
    setShowRejectionModal(true);
  };

  const handleDelete = (id: number) => {
    if (confirm('Are you sure you want to delete this request?')) {
      deleteMutation.mutate(id);
    }
  };

  const confirmApproval = () => {
    if (selectedRequest) {
      approveMutation.mutate({
        id: selectedRequest.id,
        notes: adminNotes || undefined,
      });
    }
  };

  const confirmRejection = () => {
    if (selectedRequest) {
      rejectMutation.mutate({
        id: selectedRequest.id,
        notes: adminNotes || undefined,
      });
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
    };
    return styles[status as keyof typeof styles] || 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const pendingCount = data?.items?.filter(r => r.status === 'pending').length || 0;

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Account Requests</h1>
          <p className="mt-1 text-sm text-gray-500">
            Review and manage account access requests
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {(['pending', 'approved', 'rejected', 'all'] as StatusTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setCurrentPage(1);
              }}
              className={`
                whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {tab === 'pending' && pendingCount > 0 && (
                <span className="ml-2 bg-blue-100 text-blue-600 py-0.5 px-2.5 rounded-full text-xs font-medium">
                  {pendingCount}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-sm text-gray-500">Loading requests...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800">Failed to load account requests. Please try again.</p>
        </div>
      )}

      {/* Requests List */}
      {!isLoading && !error && (
        <>
          {(data?.items?.length ?? 0) === 0 ? (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No requests found</h3>
              <p className="mt-1 text-sm text-gray-500">
                {searchQuery ? 'Try adjusting your search.' : 'No account requests yet.'}
              </p>
            </div>
          ) : (
            <div className="bg-white shadow-sm rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Applicant
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Position
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Submitted
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data?.items?.map((request) => (
                    <tr key={request.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{request.name}</div>
                          <div className="text-sm text-gray-500">{request.email}</div>
                          {request.phone && (
                            <div className="text-xs text-gray-400">{request.phone}</div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">{request.job_title || '—'}</div>
                        <div className="text-sm text-gray-500">{request.department || '—'}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(request.submitted_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadge(request.status)}`}>
                          {request.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                        {request.status === 'pending' && (
                          <>
                            <button
                              onClick={() => handleApprove(request)}
                              className="text-green-600 hover:text-green-900"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(request)}
                              className="text-red-600 hover:text-red-900"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => setSelectedRequest(request)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleDelete(request.id)}
                          className="text-gray-600 hover:text-gray-900"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex items-center justify-between bg-white px-4 py-3 border-t border-gray-200 sm:px-6 rounded-lg">
              <div className="flex-1 flex justify-between sm:hidden">
                <Button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  variant="secondary"
                >
                  Previous
                </Button>
                <Button
                  onClick={() => setCurrentPage(p => Math.min(data.pages, p + 1))}
                  disabled={currentPage === data.pages}
                  variant="secondary"
                >
                  Next
                </Button>
              </div>
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-gray-700">
                    Showing <span className="font-medium">{(currentPage - 1) * 20 + 1}</span> to{' '}
                    <span className="font-medium">{Math.min(currentPage * 20, data.total)}</span> of{' '}
                    <span className="font-medium">{data.total}</span> results
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    variant="secondary"
                    size="sm"
                  >
                    Previous
                  </Button>
                  <Button
                    onClick={() => setCurrentPage(p => Math.min(data.pages, p + 1))}
                    disabled={currentPage === data.pages}
                    variant="secondary"
                    size="sm"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Approval Modal */}
      {showApprovalModal && selectedRequest && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Approve Request</h3>
            <p className="text-sm text-gray-600 mb-4">
              Approving <strong>{selectedRequest.name}</strong>'s request. You'll be able to create their staff account with pre-filled information.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Admin Notes (Optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Add any internal notes..."
              />
            </div>
            <div className="flex gap-3 justify-end">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowApprovalModal(false);
                  setAdminNotes('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={confirmApproval}
                isLoading={approveMutation.isPending}
              >
                Approve & Create Account
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {showRejectionModal && selectedRequest && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Reject Request</h3>
            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to reject <strong>{selectedRequest.name}</strong>'s request?
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Reason for Rejection (Optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Provide a reason for the rejection..."
              />
            </div>
            <div className="flex gap-3 justify-end">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowRejectionModal(false);
                  setAdminNotes('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={confirmRejection}
                isLoading={rejectMutation.isPending}
              >
                Reject Request
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedRequest && !showApprovalModal && !showRejectionModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Request Details</h3>
              <button
                onClick={() => setSelectedRequest(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-gray-500">Name</label>
                  <p className="text-sm text-gray-900">{selectedRequest.name}</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Email</label>
                  <p className="text-sm text-gray-900">{selectedRequest.email}</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Phone</label>
                  <p className="text-sm text-gray-900">{selectedRequest.phone || '—'}</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Status</label>
                  <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadge(selectedRequest.status)}`}>
                    {selectedRequest.status}
                  </span>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Job Title</label>
                  <p className="text-sm text-gray-900">{selectedRequest.job_title || '—'}</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Department</label>
                  <p className="text-sm text-gray-900">{selectedRequest.department || '—'}</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500">Submitted</label>
                  <p className="text-sm text-gray-900">{formatDate(selectedRequest.submitted_at)}</p>
                </div>
                {selectedRequest.reviewed_at && (
                  <div>
                    <label className="text-xs font-medium text-gray-500">Reviewed</label>
                    <p className="text-sm text-gray-900">{formatDate(selectedRequest.reviewed_at)}</p>
                  </div>
                )}
              </div>

              {selectedRequest.message && (
                <div>
                  <label className="text-xs font-medium text-gray-500">Message</label>
                  <p className="text-sm text-gray-900 mt-1 p-3 bg-gray-50 rounded">{selectedRequest.message}</p>
                </div>
              )}

              {selectedRequest.admin_notes && (
                <div>
                  <label className="text-xs font-medium text-gray-500">Admin Notes</label>
                  <p className="text-sm text-gray-900 mt-1 p-3 bg-yellow-50 rounded">{selectedRequest.admin_notes}</p>
                </div>
              )}

              <div className="text-xs text-gray-500">
                <p>IP: {selectedRequest.ip_address || '—'}</p>
                <p className="truncate">User Agent: {selectedRequest.user_agent || '—'}</p>
              </div>
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              {selectedRequest.status === 'pending' && (
                <>
                  <Button
                    variant="primary"
                    onClick={() => {
                      setShowApprovalModal(true);
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setShowRejectionModal(true);
                    }}
                  >
                    Reject
                  </Button>
                </>
              )}
              <Button
                variant="secondary"
                onClick={() => setSelectedRequest(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Prefill Data Display (temporary) */}
      {prefillData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Request Approved</h3>
            <p className="text-sm text-gray-600 mb-4">
              Pre-filled data for staff creation:
            </p>
            <pre className="bg-gray-50 p-4 rounded text-xs overflow-auto">
              {JSON.stringify(prefillData, null, 2)}
            </pre>
            <div className="mt-4">
              <Button
                variant="primary"
                onClick={() => setPrefillData(null)}
                className="w-full"
              >
                Close (TODO: Open Staff Wizard)
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
