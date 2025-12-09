// ============================================
// TIME TRACKER - ACCOUNT REQUEST PAGE
// Public page for prospective staff members
// ============================================
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button, Input } from '../components/common';
import { accountRequestsApi } from '../api/accountRequests';
import type { AccountRequestCreate } from '../types/accountRequest';

export function AccountRequestPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<AccountRequestCreate>();

  const onSubmit = async (data: AccountRequestCreate) => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await accountRequestsApi.submit(data);
      setIsSuccess(true);
      reset();
      
      // Auto-redirect after 5 seconds
      setTimeout(() => {
        navigate('/login');
      }, 5000);
    } catch (error: unknown) {
      const err = error as { response?: { status?: number; data?: { detail?: string } } };
      if (err.response?.status === 429) {
        setSubmitError('Too many requests. Please try again later.');
      } else if (err.response?.status === 400) {
        setSubmitError(err.response.data?.detail || 'Invalid request. Please check your information.');
      } else {
        setSubmitError('Failed to submit request. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full">
          <div className="bg-white shadow-lg rounded-lg p-8 text-center">
            {/* Success Icon */}
            <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <svg className="w-10 h-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>

            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Request Submitted Successfully!
            </h2>
            <p className="text-gray-600 mb-6">
              Thank you for your interest. An administrator will review your request and contact you soon.
            </p>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-blue-800">
                <strong>What happens next?</strong>
                <br />
                • Our team will review your request within 1-2 business days
                <br />
                • You'll receive an email once your account is approved
                <br />
                • Your login credentials will be provided via secure email
              </p>
            </div>

            <Link to="/login">
              <Button variant="primary" className="w-full">
                Return to Login
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="mx-auto w-16 h-16 bg-blue-600 rounded-xl flex items-center justify-center">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Request an Account
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Fill out the form below to request access to the Time Tracker system
          </p>
        </div>

        {/* Form */}
        <div className="bg-white shadow-lg rounded-lg p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Error Message */}
            {submitError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-red-600 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <p className="text-sm text-red-800">{submitError}</p>
                </div>
              </div>
            )}

            {/* Personal Information */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 border-b pb-2">
                Personal Information
              </h3>

              <Input
                label="Full Name *"
                {...register('name', {
                  required: 'Name is required',
                  minLength: { value: 2, message: 'Name must be at least 2 characters' },
                  maxLength: { value: 100, message: 'Name must be less than 100 characters' },
                })}
                error={errors.name?.message}
                placeholder="John Doe"
              />

              <Input
                label="Email Address *"
                type="email"
                {...register('email', {
                  required: 'Email is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address',
                  },
                })}
                error={errors.email?.message}
                placeholder="john.doe@example.com"
              />

              <Input
                label="Phone Number"
                type="tel"
                {...register('phone', {
                  pattern: {
                    value: /^[\d\s\-+()]+$/,
                    message: 'Invalid phone number format',
                  },
                })}
                error={errors.phone?.message}
                placeholder="+1 (555) 123-4567"
              />
            </div>

            {/* Position Information */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 border-b pb-2">
                Position Information
              </h3>

              <Input
                label="Desired Job Title"
                {...register('job_title', {
                  maxLength: { value: 100, message: 'Job title must be less than 100 characters' },
                })}
                error={errors.job_title?.message}
                placeholder="Software Engineer, Project Manager, etc."
              />

              <Input
                label="Department"
                {...register('department', {
                  maxLength: { value: 100, message: 'Department must be less than 100 characters' },
                })}
                error={errors.department?.message}
                placeholder="Engineering, HR, Marketing, etc."
              />
            </div>

            {/* Additional Message */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 border-b pb-2">
                Additional Information
              </h3>

              <div>
                <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
                  Message (Optional)
                </label>
                <textarea
                  id="message"
                  {...register('message', {
                    maxLength: { value: 500, message: 'Message must be less than 500 characters' },
                  })}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Tell us why you'd like to join the team or any additional information..."
                />
                {errors.message && (
                  <p className="mt-1 text-sm text-red-600">{errors.message.message}</p>
                )}
              </div>
            </div>

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex">
                <svg className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="text-sm text-blue-800">
                  <p className="font-semibold mb-1">Privacy Notice</p>
                  <p>
                    Your information will only be used for account creation and verification purposes.
                    We'll contact you via email once your request is reviewed.
                  </p>
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <div className="flex items-center justify-between pt-4">
              <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900">
                ← Back to Login
              </Link>
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmitting}
                disabled={isSubmitting}
                className="px-8"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Request'}
              </Button>
            </div>
          </form>
        </div>

        {/* Footer Note */}
        <p className="mt-4 text-center text-xs text-gray-500">
          Already have an account?{' '}
          <Link to="/login" className="text-blue-600 hover:text-blue-500 font-medium">
            Sign in here
          </Link>
        </p>
      </div>
    </div>
  );
}
