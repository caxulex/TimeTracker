// ============================================
// TIME TRACKER - LOGIN PAGE
// ============================================
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuthStore } from '../stores/authStore';
import { Button, Input } from '../components/common';
import { useNotifications } from '../hooks/useNotifications';
import { branding } from '../config/branding';
import type { UserLogin } from '../types';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, isLoading, error, clearError } = useAuthStore();
  const { addNotification } = useNotifications();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UserLogin>();

  const onSubmit = async (data: UserLogin) => {
    try {
      await login(data);
      addNotification({
        type: 'success',
        title: 'Welcome back!',
        message: 'You have signed in successfully',
        duration: 3000,
      });
      navigate('/dashboard');
    } catch (error) {
      // Error is handled by the store
    }
  };

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
            Welcome back
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Sign in to your {branding.appName} account
          </p>
        </div>

        {/* Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
              <button
                type="button"
                onClick={clearError}
                className="float-right text-red-500 hover:text-red-700"
              >
                ×
              </button>
            </div>
          )}

          <div className="space-y-4">
            <Input
              label="Email address"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              error={errors.email?.message}
              {...register('email', {
                required: 'Email is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address',
                },
              })}
            />

            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="••••••••"
                error={errors.password?.message}
                {...register('password', {
                  required: 'Password is required',
                })}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
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
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                className="h-4 w-4 border-gray-300 rounded"
                style={{ accentColor: branding.primaryColor }}
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-900">
                Remember me
              </label>
            </div>

            <div className="text-sm">
              <Link 
                to="/forgot-password" 
                className="font-medium hover:opacity-80"
                style={{ color: branding.primaryColor }}
              >
                Forgot your password?
              </Link>
            </div>
          </div>

          <Button
            type="submit"
            className="w-full"
            size="lg"
            isLoading={isLoading}
            style={{ backgroundColor: branding.primaryColor }}
          >
            Sign in
          </Button>

          <p className="mt-2 text-center text-sm text-gray-600">
            Need an account?{' '}
            <Link 
              to="/request-account" 
              className="font-medium hover:opacity-80"
              style={{ color: branding.primaryColor }}
            >
              Request Access
            </Link>
          </p>
        </form>

        {/* Footer with support info */}
        <div className="text-center text-xs text-gray-500 space-y-1">
          <p>© {branding.copyrightYear} {branding.companyName}</p>
          <p>
            Need help?{' '}
            <a 
              href={`mailto:${branding.supportEmail}`}
              className="hover:underline"
              style={{ color: branding.primaryColor }}
            >
              Contact Support
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
