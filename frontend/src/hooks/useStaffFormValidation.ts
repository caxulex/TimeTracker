// ============================================
// TIME TRACKER - FORM VALIDATION HOOK
// Phase 9: Security Enhancements
// ============================================
import { useState, useCallback } from 'react';
import {
  isValidEmail,
  isValidPhone,
  validateStaffName,
  validatePasswordStrength,
  validatePayRate,
  validateNumericInput,
  validateDateRange,
  detectInjectionAttempt,
  secureFormData,
  securityLogger,
} from '../utils/security';

export interface ValidationError {
  field: string;
  message: string;
}

export interface StaffFormData {
  // Basic Info
  name: string;
  email: string;
  password?: string;
  
  // Contact
  phone?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  
  // Employment
  job_title?: string;
  department?: string;
  employment_type?: string;
  start_date?: string;
  expected_hours_per_week?: number;
  
  // Payroll
  pay_rate?: number;
  pay_rate_type?: string;
  overtime_multiplier?: number;
}

/**
 * Hook for validating staff forms with security checks
 */
export function useStaffFormValidation() {
  const [errors, setErrors] = useState<ValidationError[]>([]);

  /**
   * Validate entire staff creation form
   */
  const validateStaffForm = useCallback((data: StaffFormData, isUpdate: boolean = false): boolean => {
    const newErrors: ValidationError[] = [];

    // Name validation
    if (!data.name || data.name.trim().length === 0) {
      newErrors.push({ field: 'name', message: 'Name is required' });
    } else {
      const nameValidation = validateStaffName(data.name);
      if (!nameValidation.valid) {
        newErrors.push({ field: 'name', message: nameValidation.error! });
      }
      
      // Check for injection attempts
      if (detectInjectionAttempt(data.name)) {
        newErrors.push({ field: 'name', message: 'Invalid characters detected' });
        securityLogger.log({
          type: 'suspicious_activity',
          action: 'injection_attempt_detected',
          details: `Name field: ${data.name}`,
        });
      }
    }

    // Email validation
    if (!data.email || data.email.trim().length === 0) {
      newErrors.push({ field: 'email', message: 'Email is required' });
    } else if (!isValidEmail(data.email)) {
      newErrors.push({ field: 'email', message: 'Invalid email format' });
    }

    // Password validation (only for creation)
    if (!isUpdate && data.password) {
      const passwordValidation = validatePasswordStrength(data.password);
      if (!passwordValidation.valid) {
        passwordValidation.errors.forEach((error) => {
          newErrors.push({ field: 'password', message: error });
        });
      }
    }

    // Phone validation (optional)
    if (data.phone && data.phone.trim().length > 0) {
      if (!isValidPhone(data.phone)) {
        newErrors.push({ field: 'phone', message: 'Invalid phone number format' });
      }
    }

    // Emergency contact phone validation (optional)
    if (data.emergency_contact_phone && data.emergency_contact_phone.trim().length > 0) {
      if (!isValidPhone(data.emergency_contact_phone)) {
        newErrors.push({ field: 'emergency_contact_phone', message: 'Invalid phone number format' });
      }
    }

    // Expected hours validation
    if (data.expected_hours_per_week !== undefined) {
      const hoursValidation = validateNumericInput(data.expected_hours_per_week, 1, 168);
      if (!hoursValidation.valid) {
        newErrors.push({ field: 'expected_hours_per_week', message: hoursValidation.error! });
      }
    }

    // Pay rate validation
    if (data.pay_rate !== undefined && data.pay_rate_type) {
      if (data.pay_rate === 0) {
        // Only show error on final submission (when isUpdate is explicitly false)
        if (isUpdate === false) {
          newErrors.push({ field: 'pay_rate', message: 'Pay rate is required' });
        }
      } else {
        const rateValidation = validatePayRate(data.pay_rate, data.pay_rate_type);
        if (!rateValidation.valid) {
          newErrors.push({ field: 'pay_rate', message: rateValidation.error! });
        }
      }
    }

    // Overtime multiplier validation
    if (data.overtime_multiplier !== undefined) {
      const multiplierValidation = validateNumericInput(data.overtime_multiplier, 1, 5);
      if (!multiplierValidation.valid) {
        newErrors.push({ field: 'overtime_multiplier', message: multiplierValidation.error! });
      }
    }

    // Check all text fields for injection attempts
    const textFields = ['job_title', 'department', 'address', 'emergency_contact_name'] as const;
    textFields.forEach((field) => {
      const value = data[field];
      if (value && detectInjectionAttempt(value)) {
        newErrors.push({ field, message: 'Invalid characters detected' });
        securityLogger.log({
          type: 'suspicious_activity',
          action: 'injection_attempt_detected',
          details: `${field} field`,
        });
      }
    });

    setErrors(newErrors);
    return newErrors.length === 0;
  }, []);

  /**
   * Validate pay rate update
   */
  const validatePayRateUpdate = useCallback((
    rate: number,
    type: string,
    overtimeMultiplier: number
  ): boolean => {
    const newErrors: ValidationError[] = [];

    const rateValidation = validatePayRate(rate, type);
    if (!rateValidation.valid) {
      newErrors.push({ field: 'pay_rate', message: rateValidation.error! });
    }

    const multiplierValidation = validateNumericInput(overtimeMultiplier, 1, 5);
    if (!multiplierValidation.valid) {
      newErrors.push({ field: 'overtime_multiplier', message: multiplierValidation.error! });
    }

    setErrors(newErrors);
    return newErrors.length === 0;
  }, []);

  /**
   * Validate time entry date range
   */
  const validateTimeEntryRange = useCallback((startDate: string, endDate: string): boolean => {
    const newErrors: ValidationError[] = [];

    const rangeValidation = validateDateRange(startDate, endDate);
    if (!rangeValidation.valid) {
      newErrors.push({ field: 'date_range', message: rangeValidation.error! });
    }

    setErrors(newErrors);
    return newErrors.length === 0;
  }, []);

  /**
   * Get error message for specific field
   */
  const getFieldError = useCallback((field: string): string | undefined => {
    const error = errors.find((e) => e.field === field);
    return error?.message;
  }, [errors]);

  /**
   * Check if field has error
   */
  const hasFieldError = useCallback((field: string): boolean => {
    return errors.some((e) => e.field === field);
  }, [errors]);

  /**
   * Clear all errors
   */
  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);

  /**
   * Clear specific field error
   */
  const clearFieldError = useCallback((field: string) => {
    setErrors((prev) => prev.filter((e) => e.field !== field));
  }, []);

  /**
   * Secure and validate form data before submission
   */
  const secureAndValidate = useCallback((data: StaffFormData | Record<string, unknown>, isUpdate: boolean = false): {
    valid: boolean;
    securedData: Record<string, unknown>;
  } => {
    const valid = validateStaffForm(data as StaffFormData, isUpdate);
    const securedData = secureFormData(data as Record<string, unknown>);

    return { valid, securedData };
  }, [validateStaffForm]);

  return {
    errors,
    validateStaffForm,
    validatePayRateUpdate,
    validateTimeEntryRange,
    getFieldError,
    hasFieldError,
    clearErrors,
    clearFieldError,
    secureAndValidate,
  };
}
