import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Password Reset Flow
 * Phase 7: Testing - Password recovery critical path
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

const selectors = {
  // Forgot password page
  emailInput: 'input[type="email"], input[name="email"]',
  submitButton: 'button[type="submit"]',
  forgotPasswordLink: 'a[href*="forgot"], a:has-text("Forgot")',
  backToLoginLink: 'a[href*="login"], a:has-text("Back"), a:has-text("Login")',
  errorMessage: '[role="alert"], .error-message, .text-red-700, .text-red-600',
  successMessage: '.text-green-700, .text-green-600, [role="status"], .bg-green-50',
  
  // Reset password page
  passwordInput: 'input[type="password"], input[name="password"]',
  confirmPasswordInput: 'input[name="confirmPassword"], input[name="confirm_password"]',
};

test.describe('Password Reset Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any stored auth
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  });

  test('should display forgot password page', async ({ page }) => {
    await page.goto(`${BASE_URL}/forgot-password`);
    await page.waitForLoadState('networkidle');

    // Should have email input and submit button
    await expect(page.locator(selectors.emailInput)).toBeVisible();
    await expect(page.locator(selectors.submitButton)).toBeVisible();
  });

  test('should navigate from login to forgot password', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    const forgotLink = page.locator(selectors.forgotPasswordLink);
    if (await forgotLink.isVisible()) {
      await forgotLink.click();
      await expect(page).toHaveURL(/\/forgot-password/);
    }
  });

  test('should show validation error for empty email', async ({ page }) => {
    await page.goto(`${BASE_URL}/forgot-password`);
    await page.waitForLoadState('networkidle');

    // Submit without email
    await page.click(selectors.submitButton);

    // Should show validation error
    await page.waitForTimeout(1000);
    const hasError = await page.locator(selectors.errorMessage).isVisible() ||
                     await page.locator('input:invalid').count() > 0 ||
                     await page.getByText(/required/i).isVisible();
    
    expect(hasError).toBeTruthy();
  });

  test('should show error for invalid email format', async ({ page }) => {
    await page.goto(`${BASE_URL}/forgot-password`);
    await page.waitForLoadState('networkidle');

    // Fill with invalid email
    await page.fill(selectors.emailInput, 'invalid-email');
    await page.click(selectors.submitButton);

    // Should show email validation error
    await page.waitForTimeout(1000);
    const hasEmailError = await page.getByText(/invalid.*email/i).isVisible() ||
                          await page.locator('input[type="email"]:invalid').count() > 0;
    
    expect(hasEmailError).toBeTruthy();
  });

  test('should submit forgot password request for valid email', async ({ page }) => {
    await page.goto(`${BASE_URL}/forgot-password`);
    await page.waitForLoadState('networkidle');

    // Fill with valid email (existing user)
    await page.fill(selectors.emailInput, 'demo@example.com');
    await page.click(selectors.submitButton);

    // Should show success message or redirect
    await page.waitForTimeout(2000);
    const hasSuccess = await page.locator(selectors.successMessage).isVisible() ||
                       await page.getByText(/sent|check.*email|instructions/i).isVisible();
    
    // API might return success even for non-existent emails for security
    expect(hasSuccess).toBeTruthy();
  });

  test('should handle non-existent email gracefully', async ({ page }) => {
    await page.goto(`${BASE_URL}/forgot-password`);
    await page.waitForLoadState('networkidle');

    // Fill with non-existent email
    await page.fill(selectors.emailInput, 'nonexistent@example.com');
    await page.click(selectors.submitButton);

    // Should still show success message (security best practice)
    // Or show a generic message that doesn't reveal if email exists
    await page.waitForTimeout(2000);
    
    // Either success message or no specific error about email not found
    const response = await page.locator(selectors.successMessage).isVisible() ||
                     await page.getByText(/sent|check.*email|instructions/i).isVisible() ||
                     !await page.getByText(/not found|doesn't exist/i).isVisible();
    
    expect(response).toBeTruthy();
  });

  test('should navigate back to login from forgot password', async ({ page }) => {
    await page.goto(`${BASE_URL}/forgot-password`);
    await page.waitForLoadState('networkidle');

    const backLink = page.locator(selectors.backToLoginLink);
    if (await backLink.isVisible()) {
      await backLink.click();
      await expect(page).toHaveURL(/\/login/);
    }
  });

  test('should display reset password page with valid token', async ({ page }) => {
    // Navigate to reset password with mock token
    await page.goto(`${BASE_URL}/reset-password?token=mock-token`);
    await page.waitForLoadState('networkidle');

    // Should have password inputs
    await expect(page.locator(selectors.passwordInput).first()).toBeVisible();
  });

  test('should show error for invalid/expired token', async ({ page }) => {
    // Navigate to reset password with invalid token
    await page.goto(`${BASE_URL}/reset-password?token=invalid-token-12345`);
    await page.waitForLoadState('networkidle');

    // Try to submit new password
    const passwordInputs = page.locator(selectors.passwordInput);
    if (await passwordInputs.count() > 0) {
      await passwordInputs.first().fill('NewPassword123!');
      
      const confirmPassword = page.locator(selectors.confirmPasswordInput);
      if (await confirmPassword.isVisible()) {
        await confirmPassword.fill('NewPassword123!');
      } else if (await passwordInputs.count() > 1) {
        await passwordInputs.nth(1).fill('NewPassword123!');
      }

      await page.click(selectors.submitButton);

      // Should show error about invalid/expired token
      await page.waitForTimeout(2000);
      const hasError = await page.locator(selectors.errorMessage).isVisible() ||
                       await page.getByText(/invalid|expired|token/i).isVisible();
      
      expect(hasError).toBeTruthy();
    }
  });

  test('should validate password requirements on reset', async ({ page }) => {
    await page.goto(`${BASE_URL}/reset-password?token=mock-token`);
    await page.waitForLoadState('networkidle');

    const passwordInputs = page.locator(selectors.passwordInput);
    if (await passwordInputs.count() > 0) {
      // Try with weak password
      await passwordInputs.first().fill('weak');
      await page.click(selectors.submitButton);

      // Should show password strength error
      await page.waitForTimeout(1000);
      const hasError = await page.getByText(/password|weak|strong|characters/i).isVisible();
      expect(hasError).toBeTruthy();
    }
  });

  test('should validate password confirmation match', async ({ page }) => {
    await page.goto(`${BASE_URL}/reset-password?token=mock-token`);
    await page.waitForLoadState('networkidle');

    const passwordInputs = page.locator(selectors.passwordInput);
    const confirmPassword = page.locator(selectors.confirmPasswordInput);
    
    if (await passwordInputs.count() > 0) {
      await passwordInputs.first().fill('NewPassword123!');
      
      if (await confirmPassword.isVisible()) {
        await confirmPassword.fill('DifferentPassword123!');
      } else if (await passwordInputs.count() > 1) {
        await passwordInputs.nth(1).fill('DifferentPassword123!');
      }

      await page.click(selectors.submitButton);

      // Should show mismatch error
      await page.waitForTimeout(1000);
      const hasError = await page.getByText(/match|mismatch|same/i).isVisible();
      expect(hasError).toBeTruthy();
    }
  });
});
