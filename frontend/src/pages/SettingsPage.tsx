// ============================================
// TIME TRACKER - SETTINGS PAGE
// ============================================
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, Button, Input, PasswordInput } from '../components/common';
import { AIFeaturePanel } from '../components/ai';
import { useAuthStore } from '../stores/authStore';
import { authApi, companiesApi } from '../api/client';
import { useNotifications } from '../hooks/useNotifications';
import { useTheme } from '../contexts/ThemeContext';
import { isAdminUser } from '../utils/helpers';
import axios from 'axios';

// Common timezone list
const TIMEZONES = [
  { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
  { value: 'America/New_York', label: 'Eastern Time (US & Canada)' },
  { value: 'America/Chicago', label: 'Central Time (US & Canada)' },
  { value: 'America/Denver', label: 'Mountain Time (US & Canada)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (US & Canada)' },
  { value: 'America/Anchorage', label: 'Alaska' },
  { value: 'Pacific/Honolulu', label: 'Hawaii' },
  { value: 'America/Puerto_Rico', label: 'Atlantic Time (Puerto Rico)' },
  { value: 'America/Mexico_City', label: 'Mexico City' },
  { value: 'America/Bogota', label: 'Bogota, Lima' },
  { value: 'America/Sao_Paulo', label: 'Sao Paulo' },
  { value: 'America/Argentina/Buenos_Aires', label: 'Buenos Aires' },
  { value: 'Europe/London', label: 'London, Dublin' },
  { value: 'Europe/Paris', label: 'Paris, Berlin, Amsterdam' },
  { value: 'Europe/Madrid', label: 'Madrid, Barcelona' },
  { value: 'Europe/Rome', label: 'Rome, Milan' },
  { value: 'Europe/Moscow', label: 'Moscow' },
  { value: 'Asia/Dubai', label: 'Dubai' },
  { value: 'Asia/Kolkata', label: 'Mumbai, New Delhi' },
  { value: 'Asia/Bangkok', label: 'Bangkok' },
  { value: 'Asia/Singapore', label: 'Singapore' },
  { value: 'Asia/Hong_Kong', label: 'Hong Kong' },
  { value: 'Asia/Shanghai', label: 'Beijing, Shanghai' },
  { value: 'Asia/Tokyo', label: 'Tokyo' },
  { value: 'Asia/Seoul', label: 'Seoul' },
  { value: 'Australia/Sydney', label: 'Sydney' },
  { value: 'Australia/Melbourne', label: 'Melbourne' },
  { value: 'Pacific/Auckland', label: 'Auckland' },
];

interface ProfileForm {
  name: string;
  email: string;
}

interface PasswordForm {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export function SettingsPage() {
  const { user, setUser } = useAuthStore();
  const { addNotification } = useNotifications();
  const { isDark, toggleTheme } = useTheme();
  const queryClient = useQueryClient();
  const [profileLoading, setProfileLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [selectedTimezone, setSelectedTimezone] = useState('UTC');

  const isAdmin = isAdminUser(user);

  // Fetch company data for admins
  const { data: companyData, isLoading: companyLoading } = useQuery({
    queryKey: ['my-company'],
    queryFn: () => companiesApi.getMyCompany(),
    enabled: isAdmin,
  });

  // Update selected timezone when company data loads
  useEffect(() => {
    if (companyData?.timezone) {
      setSelectedTimezone(companyData.timezone);
    }
  }, [companyData]);

  // Timezone update mutation
  const timezoneMutation = useMutation({
    mutationFn: (timezone: string) => companiesApi.updateMyCompany({ timezone }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-company'] });
      addNotification({
        type: 'success',
        title: 'Timezone Updated',
        message: 'Company timezone has been updated successfully',
      });
    },
    onError: (error: Error) => {
      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: axios.isAxiosError(error) ? (error.response?.data?.detail || 'Failed to update timezone') : 'Failed to update timezone',
      });
    },
  });

  const handleTimezoneChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newTimezone = e.target.value;
    setSelectedTimezone(newTimezone);
    timezoneMutation.mutate(newTimezone);
  };

  const {
    register: registerProfile,
    handleSubmit: handleProfileSubmit,
    formState: { errors: profileErrors },
  } = useForm<ProfileForm>({
    defaultValues: {
      name: user?.name || '',
      email: user?.email || '',
    },
  });

  const {
    register: registerPassword,
    handleSubmit: handlePasswordSubmit,
    formState: { errors: passwordErrors },
    reset: resetPassword,
    watch,
  } = useForm<PasswordForm>();

  const newPassword = watch('newPassword');

  const onProfileSubmit = async (data: ProfileForm) => {
    setProfileLoading(true);

    try {
      const updatedUser = await authApi.updateMe(data);
      setUser(updatedUser);
      addNotification({
        type: 'success',
        title: 'Profile Updated',
        message: 'Your profile has been updated successfully',
      });
    } catch (error: unknown) {
      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: axios.isAxiosError(error) ? (error.response?.data?.detail || 'Failed to update profile') : 'Failed to update profile',
      });
    } finally {
      setProfileLoading(false);
    }
  };

  const onPasswordSubmit = async (data: PasswordForm) => {
    setPasswordLoading(true);

    try {
      await authApi.changePassword(data.currentPassword, data.newPassword);
      addNotification({
        type: 'success',
        title: 'Password Changed',
        message: 'Your password has been changed successfully',
      });
      resetPassword();
    } catch (error: unknown) {
      // Extract error message - check for detailed password requirements
      let errorMessage = 'Failed to change password';
      if (axios.isAxiosError(error)) {
        const responseData = error.response?.data;
      
        if (responseData) {
          // Check if there are password requirement details
          if (responseData.details?.requirements && Array.isArray(responseData.details.requirements)) {
            errorMessage = responseData.details.requirements.join('. ');
          } else if (responseData.message) {
            errorMessage = responseData.message;
          } else if (typeof responseData.detail === 'string') {
            errorMessage = responseData.detail;
          }
        }
      }
      
      addNotification({
        type: 'error',
        title: 'Password Change Failed',
        message: errorMessage,
      });
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Settings</h1>
        <p className="text-gray-500 dark:text-gray-400">Manage your account settings</p>
      </div>

      {/* Profile section */}
      <Card>
        <CardHeader title="Profile" subtitle="Update your personal information" />
        <form onSubmit={handleProfileSubmit(onProfileSubmit)} className="space-y-4">
          <Input
            label="Full Name"
            error={profileErrors.name?.message}
            {...registerProfile('name', {
              required: 'Name is required',
              minLength: { value: 2, message: 'Name must be at least 2 characters' },
            })}
          />

          <Input
            label="Email Address"
            type="email"
            error={profileErrors.email?.message}
            {...registerProfile('email', {
              required: 'Email is required',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Invalid email address',
              },
            })}
          />

          <div className="flex justify-end">
            <Button type="submit" isLoading={profileLoading}>
              Save Changes
            </Button>
          </div>
        </form>
      </Card>

      {/* Password section */}
      <Card>
        <CardHeader title="Change Password" subtitle="Update your password to keep your account secure" />
        <form onSubmit={handlePasswordSubmit(onPasswordSubmit)} className="space-y-4">
          <PasswordInput
            label="Current Password"
            error={passwordErrors.currentPassword?.message}
            {...registerPassword('currentPassword', {
              required: 'Current password is required',
            })}
          />

          <PasswordInput
            label="New Password"
            error={passwordErrors.newPassword?.message}
            {...registerPassword('newPassword', {
              required: 'New password is required',
              minLength: { value: 12, message: 'Min 12 chars with upper, lower, number, special char' },
            })}
          />

          <PasswordInput
            label="Confirm New Password"
            error={passwordErrors.confirmPassword?.message}
            {...registerPassword('confirmPassword', {
              required: 'Please confirm your password',
              validate: (value) => value === newPassword || 'Passwords do not match',
            })}
          />

          <div className="flex justify-end">
            <Button type="submit" isLoading={passwordLoading}>
              Change Password
            </Button>
          </div>
        </form>
      </Card>

      {/* Preferences section */}
      <Card>
        <CardHeader title="Preferences" subtitle="Customize your experience" />
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900 dark:text-gray-100">Dark Mode</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Use dark theme across the application</p>
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                isDark ? 'bg-blue-600' : 'bg-gray-200'
              }`}
              role="switch"
              aria-checked={isDark}
            >
              <span 
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  isDark ? 'translate-x-5' : 'translate-x-0'
                }`} 
              />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900 dark:text-gray-100">Email Notifications</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Receive weekly summary emails</p>
            </div>
            <button
              type="button"
              className="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-blue-600 transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              role="switch"
              aria-checked="true"
            >
              <span className="translate-x-5 pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out" />
            </button>
          </div>
        </div>
      </Card>

      {/* Timezone section - Admin Only */}
      {isAdmin && (
        <Card>
          <CardHeader 
            title="Company Timezone" 
            subtitle="Set the timezone for your company. This affects burnout risk calculations, weekend detection, and reports." 
          />
          <div className="space-y-4">
            <div>
              <label htmlFor="timezone" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Timezone
              </label>
              <select
                id="timezone"
                value={selectedTimezone}
                onChange={handleTimezoneChange}
                disabled={companyLoading || timezoneMutation.isPending}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-4 py-2 text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
              {timezoneMutation.isPending && (
                <p className="text-sm text-blue-600 mt-1">Saving...</p>
              )}
            </div>
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                <strong>Note:</strong> Changing the timezone will affect how time entries are interpreted 
                for weekend work detection, consecutive workday calculations, and late work hours in 
                the AI Burnout Risk Assessment.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* AI Features section */}
      <AIFeaturePanel />

      <Card>
        <CardHeader title="Task Categories" subtitle="Manage reusable task tags for your company" />
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Categories are available to all authenticated users.
          </p>
          <Link
            to="/settings/categories"
            className="inline-flex items-center rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Open Categories
          </Link>
        </div>
      </Card>

      {/* Account info */}
      <Card>
        <CardHeader title="Account Information" />
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">User ID</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{user?.id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Role</span>
            <span className="text-gray-900 dark:text-gray-100 capitalize">{user?.role}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Account Status</span>
            <span className={`font-medium ${user?.is_active ? 'text-green-600' : 'text-red-600'}`}>
              {user?.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>
      </Card>

      {/* Danger zone */}
      <Card className="border-red-200 dark:border-red-800">
        <CardHeader title="Danger Zone" subtitle="Irreversible actions" />
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">Delete Account</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Permanently delete your account and all data</p>
          </div>
          <Button variant="danger" size="sm">
            Delete Account
          </Button>
        </div>
      </Card>
    </div>
  );
}
