// ============================================
// TIME TRACKER - SETTINGS PAGE
// ============================================
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Card, CardHeader, Button, Input, PasswordInput } from '../components/common';
import { useAuthStore } from '../stores/authStore';
import { authApi } from '../api/client';
import { useNotifications } from '../hooks/useNotifications';
import { useTheme } from '../contexts/ThemeContext';

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
  const [profileLoading, setProfileLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);

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
    } catch (error: any) {
      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error.response?.data?.detail || 'Failed to update profile',
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
    } catch (error: any) {
      // Extract error message - check for detailed password requirements
      let errorMessage = 'Failed to change password';
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
