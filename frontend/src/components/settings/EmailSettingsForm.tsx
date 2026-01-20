/**
 * Email Settings Form Component
 * 
 * Admin panel for configuring company SMTP settings.
 * Supports white-label email configuration.
 */

import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { companiesApi, type EmailSettings, type EmailSettingsUpdate } from '../../api/client';
import { Card, Button, Input, LoadingOverlay } from '../common';
import { useNotifications } from '../../hooks/useNotifications';

interface EmailSettingsFormProps {
  className?: string;
}

export const EmailSettingsForm: React.FC<EmailSettingsFormProps> = ({ 
  className = '',
}) => {
  const queryClient = useQueryClient();
  const { addNotification } = useNotifications();
  
  // Form state
  const [formData, setFormData] = useState<EmailSettingsUpdate>({
    email_enabled: false,
    smtp_server: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    smtp_from_email: '',
    smtp_from_name: '',
    smtp_use_tls: true,
  });
  const [testEmail, setTestEmail] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Fetch current settings
  const { data: settings, isLoading, error } = useQuery({
    queryKey: ['email-settings'],
    queryFn: () => companiesApi.getEmailSettings(),
  });

  // Update form when settings load
  useEffect(() => {
    if (settings) {
      setFormData({
        email_enabled: settings.email_enabled,
        smtp_server: settings.smtp_server || '',
        smtp_port: settings.smtp_port || 587,
        smtp_username: settings.smtp_username || '',
        smtp_password: '', // Don't populate password
        smtp_from_email: settings.smtp_from_email || '',
        smtp_from_name: settings.smtp_from_name || '',
        smtp_use_tls: settings.smtp_use_tls,
      });
    }
  }, [settings]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: EmailSettingsUpdate) => companiesApi.updateEmailSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-settings'] });
      addNotification({
        type: 'success',
        title: 'Settings Saved',
        message: 'Email settings have been updated successfully',
      });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      addNotification({
        type: 'error',
        title: 'Failed to Save',
        message: axiosError.response?.data?.detail || 'An error occurred',
      });
    },
  });

  // Test email mutation
  const testMutation = useMutation({
    mutationFn: (recipient: string) => companiesApi.sendTestEmail({ recipient }),
    onSuccess: (result) => {
      if (result.success) {
        addNotification({
          type: 'success',
          title: 'Test Email Sent',
          message: result.message,
        });
      } else {
        addNotification({
          type: 'error',
          title: 'Test Failed',
          message: result.message,
        });
      }
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      addNotification({
        type: 'error',
        title: 'Test Failed',
        message: axiosError.response?.data?.detail || 'Failed to send test email',
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Build update data - only include password if provided
    const updateData: EmailSettingsUpdate = { ...formData };
    if (!updateData.smtp_password) {
      delete updateData.smtp_password;
    }
    
    updateMutation.mutate(updateData);
  };

  const handleTestEmail = () => {
    if (!testEmail.trim()) {
      addNotification({
        type: 'error',
        title: 'Validation Error',
        message: 'Please enter an email address',
      });
      return;
    }
    testMutation.mutate(testEmail);
  };

  const handleInputChange = (field: keyof EmailSettingsUpdate, value: string | number | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  if (isLoading) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 ${className}`}>
        <LoadingOverlay message="Loading email settings..." />
      </div>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <div className="p-6 text-center">
          <svg className="w-12 h-12 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Failed to Load Settings
          </h3>
          <p className="text-gray-500 dark:text-gray-400">
            Unable to load email settings. Please try again later.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Status Banner */}
      <div className={`rounded-xl p-6 text-white shadow-lg ${
        formData.email_enabled 
          ? 'bg-gradient-to-br from-green-600 to-green-800' 
          : 'bg-gradient-to-br from-gray-600 to-gray-800'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">✉️</span>
            <div>
              <h3 className="text-lg font-semibold">Email Configuration</h3>
              <p className="text-white/80 text-sm">
                {formData.email_enabled 
                  ? 'Email is enabled for your organization' 
                  : 'Email is currently disabled'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm">{formData.email_enabled ? 'Enabled' : 'Disabled'}</span>
            <button
              type="button"
              onClick={() => handleInputChange('email_enabled', !formData.email_enabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.email_enabled ? 'bg-white/30' : 'bg-white/10'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.email_enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* SMTP Configuration Form */}
      <Card>
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span>⚙️</span> SMTP Server Configuration
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure your SMTP server to send emails from your organization's domain
          </p>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* SMTP Server Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                SMTP Server
              </label>
              <Input
                type="text"
                value={formData.smtp_server || ''}
                onChange={(e) => handleInputChange('smtp_server', e.target.value)}
                placeholder="smtp.example.com"
                className="w-full"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                e.g., smtp.gmail.com, smtp.office365.com
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                SMTP Port
              </label>
              <Input
                type="number"
                value={formData.smtp_port || 587}
                onChange={(e) => handleInputChange('smtp_port', parseInt(e.target.value) || 587)}
                placeholder="587"
                className="w-full"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Common ports: 587 (TLS), 465 (SSL), 25
              </p>
            </div>
          </div>

          {/* Credentials Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                SMTP Username
              </label>
              <Input
                type="text"
                value={formData.smtp_username || ''}
                onChange={(e) => handleInputChange('smtp_username', e.target.value)}
                placeholder="your-email@example.com"
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                SMTP Password {settings?.smtp_password_set && '(saved)'}
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={formData.smtp_password || ''}
                  onChange={(e) => handleInputChange('smtp_password', e.target.value)}
                  placeholder={settings?.smtp_password_set ? '••••••••' : 'Enter password'}
                  className="w-full pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? '🙈' : '👁️'}
                </button>
              </div>
              {settings?.smtp_password_set && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Leave blank to keep existing password
                </p>
              )}
            </div>
          </div>

          {/* From Address Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                From Email
              </label>
              <Input
                type="email"
                value={formData.smtp_from_email || ''}
                onChange={(e) => handleInputChange('smtp_from_email', e.target.value)}
                placeholder="noreply@yourcompany.com"
                className="w-full"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Emails will be sent from this address
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                From Name
              </label>
              <Input
                type="text"
                value={formData.smtp_from_name || ''}
                onChange={(e) => handleInputChange('smtp_from_name', e.target.value)}
                placeholder="Your Company Name"
                className="w-full"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Display name for outgoing emails
              </p>
            </div>
          </div>

          {/* TLS Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <div>
              <p className="font-medium text-gray-900 dark:text-white">Use TLS Encryption</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Enable TLS/STARTTLS for secure email transmission (recommended)
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleInputChange('smtp_use_tls', !formData.smtp_use_tls)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.smtp_use_tls ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.smtp_use_tls ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Submit Button */}
          <div className="flex justify-end">
            <Button
              type="submit"
              disabled={updateMutation.isPending}
              className="min-w-[150px]"
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </form>
      </Card>

      {/* Test Email Section */}
      <Card>
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span>🧪</span> Test Email Configuration
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Send a test email to verify your SMTP settings are working correctly
          </p>
        </div>
        
        <div className="p-6">
          {!settings?.smtp_server ? (
            <div className="text-center py-6">
              <svg className="w-12 h-12 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <p className="text-gray-500 dark:text-gray-400">
                Configure SMTP settings above before testing
              </p>
            </div>
          ) : (
            <div className="flex gap-4">
              <div className="flex-1">
                <Input
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="Enter email address to test"
                  className="w-full"
                />
              </div>
              <Button
                type="button"
                onClick={handleTestEmail}
                disabled={testMutation.isPending || !testEmail.trim()}
                variant="secondary"
              >
                {testMutation.isPending ? 'Sending...' : 'Send Test Email'}
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Help Section */}
      <Card>
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span>📚</span> SMTP Setup Guides
          </h3>
        </div>
        
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Gmail / Google Workspace</h4>
            <ul className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <li>Server: smtp.gmail.com</li>
              <li>Port: 587 (TLS)</li>
              <li>Use App Password if 2FA enabled</li>
            </ul>
          </div>
          <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Microsoft 365</h4>
            <ul className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <li>Server: smtp.office365.com</li>
              <li>Port: 587 (TLS)</li>
              <li>Use your Microsoft credentials</li>
            </ul>
          </div>
          <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Amazon SES</h4>
            <ul className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <li>Server: email-smtp.{'{region}'}.amazonaws.com</li>
              <li>Port: 587 (TLS)</li>
              <li>Use IAM SMTP credentials</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default EmailSettingsForm;
