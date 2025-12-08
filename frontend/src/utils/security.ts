// ============================================
// TIME TRACKER - SECURITY UTILITIES
// Phase 9: Security Enhancements
// ============================================

/**
 * Input validation and sanitization utilities
 */

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate phone number (flexible format)
 */
export function isValidPhone(phone: string): boolean {
  const phoneRegex = /^[\d\s\-\+\(\)]+$/;
  return phone.length >= 10 && phoneRegex.test(phone);
}

/**
 * Sanitize string input to prevent XSS
 */
export function sanitizeString(input: string): string {
  return input
    .replace(/[<>]/g, '') // Remove < and >
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .replace(/on\w+=/gi, '') // Remove event handlers
    .trim();
}

/**
 * Validate password strength
 */
export function validatePasswordStrength(password: string): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  if (!/[^A-Za-z0-9]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Validate staff name
 */
export function validateStaffName(name: string): {
  valid: boolean;
  error?: string;
} {
  const sanitized = sanitizeString(name);
  
  if (sanitized.length < 2) {
    return { valid: false, error: 'Name must be at least 2 characters long' };
  }
  if (sanitized.length > 100) {
    return { valid: false, error: 'Name must not exceed 100 characters' };
  }
  if (!/^[a-zA-Z\s\-\.]+$/.test(sanitized)) {
    return { valid: false, error: 'Name can only contain letters, spaces, hyphens, and periods' };
  }

  return { valid: true };
}

/**
 * Validate numeric input
 */
export function validateNumericInput(
  value: number,
  min?: number,
  max?: number
): {
  valid: boolean;
  error?: string;
} {
  if (isNaN(value)) {
    return { valid: false, error: 'Must be a valid number' };
  }
  if (min !== undefined && value < min) {
    return { valid: false, error: `Must be at least ${min}` };
  }
  if (max !== undefined && value > max) {
    return { valid: false, error: `Must not exceed ${max}` };
  }

  return { valid: true };
}

/**
 * Validate pay rate
 */
export function validatePayRate(rate: number, type: string): {
  valid: boolean;
  error?: string;
} {
  if (rate <= 0) {
    return { valid: false, error: 'Pay rate must be greater than 0' };
  }

  // Set reasonable limits based on rate type
  const limits: Record<string, { max: number }> = {
    hourly: { max: 500 },
    daily: { max: 2000 },
    monthly: { max: 50000 },
    project_based: { max: 500000 },
  };

  const limit = limits[type];
  if (limit && rate > limit.max) {
    return {
      valid: false,
      error: `${type} rate should not exceed $${limit.max.toLocaleString()}`,
    };
  }

  return { valid: true };
}

/**
 * Validate date range
 */
export function validateDateRange(
  startDate: string,
  endDate: string
): {
  valid: boolean;
  error?: string;
} {
  const start = new Date(startDate);
  const end = new Date(endDate);

  if (isNaN(start.getTime())) {
    return { valid: false, error: 'Invalid start date' };
  }
  if (isNaN(end.getTime())) {
    return { valid: false, error: 'Invalid end date' };
  }
  if (start > end) {
    return { valid: false, error: 'Start date must be before end date' };
  }

  // Prevent queries for excessively long periods (e.g., more than 2 years)
  const daysDiff = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
  if (daysDiff > 730) {
    return { valid: false, error: 'Date range cannot exceed 2 years' };
  }

  return { valid: true };
}

/**
 * Check if user has required permission
 */
export function hasPermission(
  userRole: string | undefined,
  requiredRole: 'super_admin' | 'admin' | 'regular_user'
): boolean {
  const roleHierarchy = {
    super_admin: 3,
    admin: 2,
    regular_user: 1,
  };

  const userLevel = roleHierarchy[userRole as keyof typeof roleHierarchy] || 0;
  const requiredLevel = roleHierarchy[requiredRole];

  return userLevel >= requiredLevel;
}

/**
 * Redact sensitive information from objects for logging
 */
export function redactSensitiveData<T extends Record<string, any>>(
  data: T,
  sensitiveFields: string[] = ['password', 'token', 'secret', 'ssn']
): T {
  const redacted = { ...data };

  sensitiveFields.forEach((field) => {
    if (field in redacted) {
      redacted[field] = '***REDACTED***';
    }
  });

  return redacted;
}

/**
 * Rate limiting helper (client-side tracking)
 */
class RateLimiter {
  private attempts: Map<string, number[]> = new Map();

  /**
   * Check if action is allowed
   * @param key Unique identifier for the action
   * @param maxAttempts Maximum number of attempts allowed
   * @param windowMs Time window in milliseconds
   */
  public isAllowed(key: string, maxAttempts: number, windowMs: number): boolean {
    const now = Date.now();
    const attempts = this.attempts.get(key) || [];

    // Remove old attempts outside the window
    const recentAttempts = attempts.filter(
      (timestamp) => now - timestamp < windowMs
    );

    if (recentAttempts.length >= maxAttempts) {
      return false;
    }

    // Record this attempt
    recentAttempts.push(now);
    this.attempts.set(key, recentAttempts);

    return true;
  }

  /**
   * Reset attempts for a key
   */
  public reset(key: string): void {
    this.attempts.delete(key);
  }

  /**
   * Get remaining attempts
   */
  public getRemainingAttempts(
    key: string,
    maxAttempts: number,
    windowMs: number
  ): number {
    const now = Date.now();
    const attempts = this.attempts.get(key) || [];
    const recentAttempts = attempts.filter(
      (timestamp) => now - timestamp < windowMs
    );

    return Math.max(0, maxAttempts - recentAttempts.length);
  }
}

export const rateLimiter = new RateLimiter();

/**
 * Secure form data before submission
 */
export function secureFormData<T extends Record<string, any>>(data: T): T {
  const secured = { ...data };

  // Sanitize string fields
  Object.keys(secured).forEach((key) => {
    if (typeof secured[key] === 'string') {
      secured[key] = sanitizeString(secured[key]);
    }
  });

  return secured;
}

/**
 * Validate bulk operation size
 */
export function validateBulkOperationSize(
  itemCount: number,
  maxItems: number = 100
): {
  valid: boolean;
  error?: string;
} {
  if (itemCount === 0) {
    return { valid: false, error: 'No items selected' };
  }
  if (itemCount > maxItems) {
    return {
      valid: false,
      error: `Cannot process more than ${maxItems} items at once`,
    };
  }

  return { valid: true };
}

/**
 * Generate secure random string for tokens/IDs
 */
export function generateSecureToken(length: number = 32): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join(
    ''
  );
}

/**
 * Check if data contains potential injection attacks
 */
export function detectInjectionAttempt(input: string): boolean {
  const sqlInjectionPatterns = [
    /(\bUNION\b|\bSELECT\b|\bDROP\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b)/i,
    /(-{2}|\/\*|\*\/|;)/,
    /(\bOR\b|\bAND\b)\s+[\d\w]+=[\d\w]+/i,
  ];

  const xssPatterns = [
    /<script[^>]*>.*?<\/script>/gi,
    /javascript:/gi,
    /on\w+\s*=/gi,
  ];

  return (
    sqlInjectionPatterns.some((pattern) => pattern.test(input)) ||
    xssPatterns.some((pattern) => pattern.test(input))
  );
}

/**
 * Mask sensitive data for display
 */
export function maskSensitiveData(
  data: string,
  visibleChars: number = 4,
  maskChar: string = '*'
): string {
  if (data.length <= visibleChars) {
    return maskChar.repeat(data.length);
  }

  const masked = maskChar.repeat(data.length - visibleChars);
  const visible = data.slice(-visibleChars);

  return masked + visible;
}

/**
 * Security event logger (for audit trail)
 */
export interface SecurityEvent {
  type: 'access_denied' | 'permission_check' | 'validation_failed' | 'suspicious_activity';
  action: string;
  details?: string;
  timestamp: string;
  userId?: number;
}

class SecurityLogger {
  private events: SecurityEvent[] = [];
  private maxEvents: number = 100;

  public log(event: Omit<SecurityEvent, 'timestamp'>): void {
    const fullEvent: SecurityEvent = {
      ...event,
      timestamp: new Date().toISOString(),
    };

    this.events.push(fullEvent);

    // Keep only recent events
    if (this.events.length > this.maxEvents) {
      this.events = this.events.slice(-this.maxEvents);
    }

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.warn('[Security Event]', fullEvent);
    }
  }

  public getEvents(type?: SecurityEvent['type']): SecurityEvent[] {
    if (type) {
      return this.events.filter((e) => e.type === type);
    }
    return [...this.events];
  }

  public clear(): void {
    this.events = [];
  }
}

export const securityLogger = new SecurityLogger();
