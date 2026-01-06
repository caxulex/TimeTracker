// ============================================
// TIME TRACKER - RESET PASSWORD PAGE
// ============================================
import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button, Input } from '../components/common';
import { branding } from '../config/branding';
import api from '../api/axios';

interface ResetPasswordForm {
  password: string;
  confirmPassword: string;
}

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [isLoading, setIsLoading] = useState(false);
  const [isValidating, setIsValidating] = useState(true);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokenEmail, setTokenEmail] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ResetPasswordForm>();

  const password = watch('password');

  // Validate token on mount
  useEffect(() => {
    async function validateToken() {
      if (!token) {
        setError('No reset token provided');
        setIsValidating(false);
        return;
      }

      try {
        const response = await api.get(`/api/invitations/verify-reset-token/${token}`);
        setTokenEmail(response.data.email);
        setIsValidating(false);
      } catch (err: unknown) {
        setError('This reset link is invalid or has expired. Please request a new one.');
        setIsValidating(false);
      }
    }

    validateToken();
  }, [token]);

  const onSubmit = async (data: ResetPasswordForm) => {
    setIsLoading(true);
    setError(null);

    try {
      await api.post('/api/invitations/reset-password', {
        token,
        new_password: data.password,
      });
      setIsSuccess(true);
      
      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || 'Failed to reset password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Loading state while validating token
  if (isValidating) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4" 
               style={{ borderColor: branding.primaryColor }} />
          <p className="text-gray-600">Validating reset link...</p>
        </div>
      </div>
    );
  }

  // Invalid token state
  if (error && !tokenEmail) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            {branding.logoUrl.endsWith('.svg') || branding.logoUrl.startsWith('http') ? (
              <img 
                src={branding.logoUrl} 
                alt={branding.logoAlt}
                className="mx-auto w-16 h-16 rounded-xl"
              />
            ) : (
              <div 
                className="mx-auto w-16 h-16 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: branding.primaryColor }}
              >
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )}
          </div>
          
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-red-900 mb-2">Invalid Reset Link</h3>
            <p className="text-sm text-red-700 mb-4">{error}</p>
            <Link
              to="/forgot-password"
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white"
              style={{ backgroundColor: branding.primaryColor }}
            >
              Request a new link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Success state
  if (isSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            {branding.logoUrl.endsWith('.svg') || branding.logoUrl.startsWith('http') ? (
              <img 
                src={branding.logoUrl} 
                alt={branding.logoAlt}
                className="mx-auto w-16 h-16 rounded-xl"
              />
            ) : (
              <div 
                className="mx-auto w-16 h-16 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: branding.primaryColor }}
              >
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )}
          </div>
          
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
            <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-green-900 mb-2">Password Reset Successful!</h3>
            <p className="text-sm text-green-700 mb-4">
              Your password has been changed successfully.
            </p>
            <p className="text-xs text-green-600 mb-4">
              Redirecting to login in 3 seconds...
            </p>
            <Link
              to="/login"
              className="inline-flex items-center text-sm font-medium hover:underline"
              style={{ color: branding.primaryColor }}
            >
              Go to login now →
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Password reset form
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Logo */}
        <div className="text-center">
          {branding.logoUrl.endsWith('.svg') || branding.logoUrl.startsWith('http') ? (
            <img 
              src={branding.logoUrl} 
              alt={branding.logoAlt}
              className="mx-auto w-16 h-16 rounded-xl"
            />
          ) : (
            <div 
              className="mx-auto w-16 h-16 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: branding.primaryColor }}
            >
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          )}
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Create new password
          </h2>
          {tokenEmail && (
            <p className="mt-2 text-sm text-gray-600">
              For <span className="font-medium">{tokenEmail}</span>
            </p>
          )}
        </div>

        {/* Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
              <button
                type="button"
                onClick={() => setError(null)}
                className="float-right text-red-500 hover:text-red-700"
              >
                ×
              </button>
            </div>
          )}

          <div className="space-y-4">
            <div className="relative">
              <Input
                label="New password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                {...register('password', {
                  required: 'Password is required',
                  minLength: {
                    value: 8,
                    message: 'Password must be at least 8 characters',
                  },
                  pattern: {
                    value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
                    message: 'Password must include uppercase, lowercase, and number',
                  },
                })}
                error={errors.password?.message}
              />
              <button
                type="button"
                className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>

            <Input
              label="Confirm password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: (value) =>
                  value === password || 'Passwords do not match',
              })}
              error={errors.confirmPassword?.message}
            />
          </div>

          {/* Password requirements hint */}
          <div className="text-xs text-gray-500 space-y-1">
            <p className="font-medium">Password must:</p>
            <ul className="list-disc list-inside space-y-0.5 pl-2">
              <li>Be at least 8 characters long</li>
              <li>Include at least one uppercase letter</li>
              <li>Include at least one lowercase letter</li>
              <li>Include at least one number</li>
            </ul>
          </div>

          <Button
            type="submit"
            className="w-full"
            isLoading={isLoading}
            style={{ backgroundColor: branding.primaryColor }}
          >
            Reset password
          </Button>

          <div className="text-center">
            <Link
              to="/login"
              className="text-sm font-medium hover:underline"
              style={{ color: branding.primaryColor }}
            >
              ← Back to login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
