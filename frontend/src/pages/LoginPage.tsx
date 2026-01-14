// ============================================
// TIME TRACKER - LOGIN PAGE
// ============================================
import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useSearchParams, useParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuthStore } from '../stores/authStore';
import { Button, Input } from '../components/common';
import { useNotifications } from '../hooks/useNotifications';
import { useBranding } from '../contexts/BrandingContext';
import type { UserLogin } from '../types';

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { companySlug: urlCompanySlug } = useParams<{ companySlug?: string }>();
  const { login, isLoading } = useAuthStore();
  const { addNotification } = useNotifications();
  const [showPassword, setShowPassword] = useState(false);
  const { branding, setCompany, isWhiteLabeled } = useBranding();
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Use ref to persist error across re-renders caused by store updates
  const errorRef = useRef<string | null>(null);

  // Check for company slug in URL path or query params and load branding
  useEffect(() => {
    // Priority: URL path param > query param
    const companySlug = urlCompanySlug || searchParams.get('company');
    if (companySlug) {
      setCompany(companySlug);
      // Store for logout redirect
      localStorage.setItem('tt_company_slug', companySlug);
    } else {
      // Clear company slug when on main login (no company in URL)
      // This prevents stale redirect to white-label login on logout
      localStorage.removeItem('tt_company_slug');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlCompanySlug, searchParams]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UserLogin>();

  // Sync error ref to state when it changes (handles re-renders from store updates)
  useEffect(() => {
    if (errorRef.current && !loginError) {
      setLoginError(errorRef.current);
    }
  }, [isLoading, loginError]);

  const onSubmit = async (data: UserLogin) => {
    // Clear previous error only on new submission
    setLoginError(null);
    errorRef.current = null;
    setIsSubmitting(true);
    
    try {
      await login(data);
      addNotification({
        type: 'success',
        title: 'Welcome back!',
        message: 'You have signed in successfully',
        duration: 3000,
      });
      navigate('/dashboard');
    } catch (error: any) {
      // Extract error message and store in both ref and state
      const detail = error?.response?.data?.detail;
      let message = 'Login failed. Please check your credentials.';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map((e: any) => e.msg || e.message || String(e)).join(', ');
      } else if (detail?.msg) {
        message = detail.msg;
      }
      // Store in ref first (survives re-renders), then set state
      errorRef.current = message;
      setLoginError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div 
      className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8"
      style={branding.login_background_url ? { 
        backgroundImage: `url(${branding.login_background_url})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      } : undefined}
    >
      <div className="max-w-md w-full space-y-8 bg-white/95 p-8 rounded-xl shadow-lg backdrop-blur-sm">
        {/* Logo */}
        <div className="text-center">
          {branding.logo_url ? (
            <img 
              src={branding.logo_url} 
              alt={`${branding.app_name} Logo`}
              className="mx-auto w-16 h-16 rounded-xl object-contain"
            />
          ) : (
            <div 
              className="mx-auto w-16 h-16 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: branding.primary_color }}
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
            Sign in to your {branding.app_name} account
          </p>
          {branding.tagline && (
            <p className="mt-1 text-xs text-gray-500 italic">{branding.tagline}</p>
          )}
        </div>

        {/* Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {loginError && (
            <div 
              className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm"
              role="alert"
              aria-live="assertive"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span className="font-medium">{loginError}</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    errorRef.current = null;
                    setLoginError(null);
                  }}
                  className="text-red-500 hover:text-red-700 font-bold text-xl leading-none"
                  aria-label="Dismiss error"
                >
                  ×
                </button>
              </div>
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
                style={{ accentColor: branding.primary_color }}
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-900">
                Remember me
              </label>
            </div>

            <div className="text-sm">
              <Link 
                to="/forgot-password" 
                className="font-medium hover:opacity-80"
                style={{ color: branding.primary_color }}
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
            style={{ backgroundColor: branding.primary_color }}
          >
            Sign in
          </Button>

          <p className="mt-2 text-center text-sm text-gray-600">
            Need an account?{' '}
            <Link 
              to="/request-account" 
              className="font-medium hover:opacity-80"
              style={{ color: branding.primary_color }}
            >
              Request Access
            </Link>
          </p>
        </form>

        {/* Footer with support info */}
        <div className="text-center text-xs text-gray-500 space-y-1">
          <p>© {new Date().getFullYear()} {branding.company_name}</p>
          {branding.support_email && (
            <p>
              Need help?{' '}
              <a 
                href={`mailto:${branding.support_email}`}
                className="hover:underline"
                style={{ color: branding.primary_color }}
              >
                Contact Support
              </a>
            </p>
          )}
          {branding.show_powered_by && (
            <p className="text-gray-400 text-[10px] mt-2">
              Powered by Time Tracker
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
