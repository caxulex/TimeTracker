// ============================================
// TIME TRACKER - FORGOT PASSWORD PAGE
// ============================================
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button, Input } from '../components/common';
import { branding } from '../config/branding';
import api from '../api/axios';

interface ForgotPasswordForm {
  email: string;
}

export function ForgotPasswordPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordForm>();

  const onSubmit = async (data: ForgotPasswordForm) => {
    setIsLoading(true);
    setError(null);
    
    try {
      await api.post('/api/invitations/forgot-password', { email: data.email });
      setIsSubmitted(true);
    } catch (err: unknown) {
      // Even if there's an error, show success to prevent email enumeration
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
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
            Reset your password
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Enter your email and we'll send you a reset link
          </p>
        </div>

        {isSubmitted ? (
          /* Success State */
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
            <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-green-900 mb-2">Check your email</h3>
            <p className="text-sm text-green-700 mb-4">
              If an account exists with that email, we've sent password reset instructions.
            </p>
            <p className="text-xs text-green-600 mb-4">
              Don't see the email? Check your spam folder.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center text-sm font-medium hover:underline"
              style={{ color: branding.primaryColor }}
            >
              ← Back to login
            </Link>
          </div>
        ) : (
          /* Form */
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
              <Input
                label="Email address"
                type="email"
                autoComplete="email"
                {...register('email', {
                  required: 'Email is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address',
                  },
                })}
                error={errors.email?.message}
              />
            </div>

            <Button
              type="submit"
              className="w-full"
              isLoading={isLoading}
              style={{ backgroundColor: branding.primaryColor }}
            >
              Send reset link
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
        )}

        {/* Footer */}
        <div className="text-center text-xs text-gray-500 mt-8">
          <p>
            Need help?{' '}
            <a 
              href={`mailto:${branding.supportEmail}`} 
              className="hover:underline"
              style={{ color: branding.primaryColor }}
            >
              Contact support
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
