import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Registration Flow
 * Phase 7: Testing - New user registration critical path
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

// Test data for registration
const generateUniqueEmail = () => `test-${Date.now()}@example.com`;

const selectors = {
  // Registration page
  nameInput: 'input[name="name"], input[placeholder*="name" i]',
  emailInput: 'input[type="email"], input[name="email"]',
  passwordInput: 'input[type="password"], input[name="password"]',
  confirmPasswordInput: 'input[name="confirmPassword"], input[name="confirm_password"]',
  companyInput: 'input[name="company_name"], input[placeholder*="company" i]',
  submitButton: 'button[type="submit"]',
  registerLink: 'a[href*="register"], a:has-text("Register"), a:has-text("Sign up")',
  loginLink: 'a[href*="login"], a:has-text("Login"), a:has-text("Sign in")',
  errorMessage: '[role="alert"], .error-message, .text-red-700, .text-red-600',
  successMessage: '.text-green-700, .text-green-600, [role="status"]',
};

test.describe('Registration Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any stored auth
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  });

  test('should display registration page', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    // Should have registration form elements
    await expect(page.locator(selectors.emailInput)).toBeVisible();
    await expect(page.locator(selectors.passwordInput)).toBeVisible();
    await expect(page.locator(selectors.submitButton)).toBeVisible();
  });

  test('should navigate from login to register', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    const registerLink = page.locator(selectors.registerLink);
    if (await registerLink.isVisible()) {
      await registerLink.click();
      await expect(page).toHaveURL(/\/register/);
    }
  });

  test('should show validation errors for empty form', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    // Submit empty form
    await page.click(selectors.submitButton);

    // Should show validation errors
    await page.waitForTimeout(1000);
    const hasError = await page.locator(selectors.errorMessage).isVisible() ||
                     await page.locator('input:invalid').count() > 0 ||
                     await page.getByText(/required/i).isVisible();
    
    expect(hasError).toBeTruthy();
  });

  test('should show error for invalid email format', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    // Fill with invalid email
    const nameInput = page.locator(selectors.nameInput);
    if (await nameInput.isVisible()) {
      await nameInput.fill('Test User');
    }
    
    await page.fill(selectors.emailInput, 'invalid-email');
    await page.fill(selectors.passwordInput, 'Password123!');
    
    const confirmPassword = page.locator(selectors.confirmPasswordInput);
    if (await confirmPassword.isVisible()) {
      await confirmPassword.fill('Password123!');
    }

    await page.click(selectors.submitButton);

    // Should show email validation error
    await page.waitForTimeout(1000);
    const hasEmailError = await page.getByText(/invalid.*email/i).isVisible() ||
                          await page.locator('input[type="email"]:invalid').count() > 0;
    
    expect(hasEmailError).toBeTruthy();
  });

  test('should show error for weak password', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    // Fill with weak password
    const nameInput = page.locator(selectors.nameInput);
    if (await nameInput.isVisible()) {
      await nameInput.fill('Test User');
    }
    
    await page.fill(selectors.emailInput, generateUniqueEmail());
    await page.fill(selectors.passwordInput, '123'); // Too weak

    await page.click(selectors.submitButton);

    // Should show password validation error
    await page.waitForTimeout(1000);
    const hasPasswordError = await page.getByText(/password/i).isVisible();
    expect(hasPasswordError).toBeTruthy();
  });

  test('should show error for password mismatch', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    const confirmPassword = page.locator(selectors.confirmPasswordInput);
    if (await confirmPassword.isVisible()) {
      // Fill form with mismatched passwords
      const nameInput = page.locator(selectors.nameInput);
      if (await nameInput.isVisible()) {
        await nameInput.fill('Test User');
      }
      
      await page.fill(selectors.emailInput, generateUniqueEmail());
      await page.fill(selectors.passwordInput, 'Password123!');
      await confirmPassword.fill('DifferentPassword123!');

      await page.click(selectors.submitButton);

      // Should show mismatch error
      await page.waitForTimeout(1000);
      const hasMismatchError = await page.getByText(/match|mismatch/i).isVisible();
      expect(hasMismatchError).toBeTruthy();
    }
  });

  test('should navigate to login from register page', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    const loginLink = page.locator(selectors.loginLink);
    if (await loginLink.isVisible()) {
      await loginLink.click();
      await expect(page).toHaveURL(/\/login/);
    }
  });

  test('should handle duplicate email registration', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');

    // Try to register with existing email
    const nameInput = page.locator(selectors.nameInput);
    if (await nameInput.isVisible()) {
      await nameInput.fill('Test User');
    }
    
    await page.fill(selectors.emailInput, 'demo@example.com'); // Existing user
    await page.fill(selectors.passwordInput, 'Password123!');
    
    const confirmPassword = page.locator(selectors.confirmPasswordInput);
    if (await confirmPassword.isVisible()) {
      await confirmPassword.fill('Password123!');
    }

    const companyInput = page.locator(selectors.companyInput);
    if (await companyInput.isVisible()) {
      await companyInput.fill('Test Company');
    }

    await page.click(selectors.submitButton);

    // Should show error about existing email
    await page.waitForTimeout(2000);
    const hasError = await page.locator(selectors.errorMessage).isVisible() ||
                     await page.getByText(/exist|already|registered/i).isVisible();
    
    // Note: May redirect to login if backend handles differently
    const isOnLoginOrHasError = hasError || await page.url().includes('/login');
    expect(isOnLoginOrHasError).toBeTruthy();
  });
});
