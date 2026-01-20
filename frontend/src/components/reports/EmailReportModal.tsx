/**
 * Email Report Modal Component
 * 
 * Modal for sending reports via email with recipient selection
 * and format options.
 */

import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { reportsEmailApi, companiesApi, type EmailReportRequest } from '../../api/client';
import { Button, Input, Card } from '../common';
import { useNotifications } from '../../hooks/useNotifications';

interface EmailReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  reportType: 'time_report' | 'team_timesheet';
  startDate: string;
  endDate: string;
}

export function EmailReportModal({
  isOpen,
  onClose,
  reportType,
  startDate,
  endDate,
}: EmailReportModalProps) {
  const { addNotification } = useNotifications();
  
  // Form state
  const [recipients, setRecipients] = useState<string>('');
  const [format, setFormat] = useState<'pdf' | 'excel' | 'csv'>('pdf');
  const [customMessage, setCustomMessage] = useState('');

  // Check if email is configured
  const { data: emailSettings } = useQuery({
    queryKey: ['email-settings'],
    queryFn: () => companiesApi.getEmailSettings(),
    enabled: isOpen,
  });

  // Send email mutation
  const sendMutation = useMutation({
    mutationFn: (data: EmailReportRequest) => reportsEmailApi.sendReport(data),
    onSuccess: (result) => {
      if (result.success) {
        addNotification({
          type: 'success',
          title: 'Report Sent',
          message: result.message,
        });
        onClose();
        // Reset form
        setRecipients('');
        setCustomMessage('');
      } else {
        addNotification({
          type: 'error',
          title: 'Send Failed',
          message: result.message,
        });
      }
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      addNotification({
        type: 'error',
        title: 'Send Failed',
        message: axiosError.response?.data?.detail || 'Failed to send report',
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Parse recipients
    const recipientList = recipients
      .split(/[,;\n]/)
      .map(email => email.trim())
      .filter(email => email.length > 0);

    if (recipientList.length === 0) {
      addNotification({
        type: 'error',
        title: 'Validation Error',
        message: 'Please enter at least one recipient email address',
      });
      return;
    }

    // Basic email validation
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    const invalidEmails = recipientList.filter(email => !emailPattern.test(email));
    if (invalidEmails.length > 0) {
      addNotification({
        type: 'error',
        title: 'Invalid Email',
        message: `Invalid email address(es): ${invalidEmails.join(', ')}`,
      });
      return;
    }

    sendMutation.mutate({
      report_type: reportType,
      start_date: startDate,
      end_date: endDate,
      recipients: recipientList,
      format: format,
      custom_message: customMessage || undefined,
    });
  };

  const reportTypeName = reportType === 'team_timesheet' ? 'Team Timesheet' : 'Time Report';
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full transform transition-all">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <span className="text-2xl">✉️</span>
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Email Report
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {reportTypeName} • {formatDate(startDate)} - {formatDate(endDate)}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          {!emailSettings?.email_enabled || !emailSettings?.smtp_server ? (
            <div className="p-6">
              <div className="text-center py-8">
                <svg className="w-16 h-16 mx-auto text-amber-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                  Email Not Configured
                </h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">
                  Email settings need to be configured before sending reports.
                </p>
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  Go to Admin Settings → Email Settings to configure SMTP
                </p>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {/* Recipients */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Recipients
                </label>
                <textarea
                  value={recipients}
                  onChange={(e) => setRecipients(e.target.value)}
                  placeholder="Enter email addresses (one per line or comma-separated)"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Separate multiple addresses with commas or new lines
                </p>
              </div>

              {/* Format Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Report Format
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: 'pdf', label: 'PDF', icon: '📄' },
                    { value: 'excel', label: 'Excel', icon: '📊' },
                    { value: 'csv', label: 'CSV', icon: '📋' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setFormat(option.value as 'pdf' | 'excel' | 'csv')}
                      className={`flex flex-col items-center justify-center p-3 rounded-lg border-2 transition-colors ${
                        format === option.value
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                      }`}
                    >
                      <span className="text-xl mb-1">{option.icon}</span>
                      <span className="text-sm font-medium">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Message */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Custom Message (optional)
                </label>
                <textarea
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  placeholder="Add a personal message to the email..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Submit Button */}
              <div className="flex justify-end gap-3 pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={sendMutation.isPending || !recipients.trim()}
                >
                  {sendMutation.isPending ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Sending...
                    </>
                  ) : (
                    <>
                      <span className="mr-2">✉️</span>
                      Send Report
                    </>
                  )}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default EmailReportModal;
