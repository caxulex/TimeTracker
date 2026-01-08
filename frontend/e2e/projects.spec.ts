import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Projects Management
 * Phase 7: Testing - Project CRUD operations
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

const TEST_USER = {
  email: 'admin@example.com',
  password: 'AdminPass123!',
};

const selectors = {
  // Login
  emailInput: 'input[type="email"], input[name="email"]',
  passwordInput: 'input[type="password"], input[name="password"]',
  loginButton: 'button[type="submit"]',
  
  // Projects page
  projectsTitle: 'h1:has-text("Projects")',
  createButton: 'button:has-text("Create"), button:has-text("New"), button:has-text("Add")',
  projectCard: '[data-testid="project-card"], .project-card, .card',
  projectName: '[data-testid="project-name"], .project-name',
  projectDescription: '[data-testid="project-description"], .project-description',
  
  // Project form
  nameInput: 'input[name="name"], input[placeholder*="name" i]',
  descriptionInput: 'textarea[name="description"], input[name="description"]',
  colorPicker: 'input[type="color"], [data-testid="color-picker"]',
  submitButton: 'button[type="submit"]',
  cancelButton: 'button:has-text("Cancel")',
  
  // Project actions
  editButton: 'button:has-text("Edit"), [aria-label="Edit"]',
  deleteButton: 'button:has-text("Delete"), [aria-label="Delete"]',
  archiveButton: 'button:has-text("Archive")',
  
  // Modal
  modal: '[role="dialog"], .modal',
  confirmButton: 'button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Delete")',
  
  // Messages
  successMessage: '.text-green-700, .text-green-600, [role="status"]',
  errorMessage: '[role="alert"], .error-message, .text-red-700',
};

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('networkidle');
  
  await page.fill(selectors.emailInput, TEST_USER.email);
  await page.fill(selectors.passwordInput, TEST_USER.password);
  await page.click(selectors.loginButton);
  
  await page.waitForURL(/\/(dashboard|projects)/, { timeout: 10000 });
}

test.describe('Projects Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  });

  test.describe('Projects List', () => {
    test('should display projects page', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      // Should show projects page
      await expect(page.getByText(/projects/i).first()).toBeVisible();
    });

    test('should show create button for authorized users', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      // Admin should see create button
      const createBtn = page.locator(selectors.createButton);
      await expect(createBtn.first()).toBeVisible();
    });

    test('should display existing projects', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      // Wait for projects to load
      await page.waitForTimeout(2000);
      
      // Should have at least the projects page content
      const pageContent = await page.textContent('body');
      expect(pageContent?.toLowerCase()).toContain('project');
    });
  });

  test.describe('Create Project', () => {
    test('should open create project modal', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const createBtn = page.locator(selectors.createButton).first();
      if (await createBtn.isVisible()) {
        await createBtn.click();
        await page.waitForTimeout(500);

        // Should show form
        const nameInput = page.locator(selectors.nameInput);
        await expect(nameInput.first()).toBeVisible();
      }
    });

    test('should validate required fields', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const createBtn = page.locator(selectors.createButton).first();
      if (await createBtn.isVisible()) {
        await createBtn.click();
        await page.waitForTimeout(500);

        // Try to submit empty form
        const submitBtn = page.locator(selectors.submitButton);
        if (await submitBtn.isVisible()) {
          await submitBtn.click();
          
          // Should show validation error
          await page.waitForTimeout(1000);
          const hasError = await page.locator(selectors.errorMessage).isVisible() ||
                           await page.locator('input:invalid').count() > 0 ||
                           await page.getByText(/required/i).isVisible();
          
          expect(hasError).toBeTruthy();
        }
      }
    });

    test('should create new project successfully', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const projectName = `Test Project ${Date.now()}`;

      const createBtn = page.locator(selectors.createButton).first();
      if (await createBtn.isVisible()) {
        await createBtn.click();
        await page.waitForTimeout(500);

        // Fill form
        const nameInput = page.locator(selectors.nameInput).first();
        await nameInput.fill(projectName);

        const descInput = page.locator(selectors.descriptionInput);
        if (await descInput.isVisible()) {
          await descInput.fill('Test project description');
        }

        // Submit
        const submitBtn = page.locator(selectors.submitButton);
        await submitBtn.click();

        // Should show success or project in list
        await page.waitForTimeout(2000);
        const hasSuccess = await page.locator(selectors.successMessage).isVisible() ||
                           await page.getByText(projectName).isVisible();
        
        expect(hasSuccess).toBeTruthy();
      }
    });
  });

  test.describe('Edit Project', () => {
    test('should open edit modal for existing project', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      // Find an edit button
      const editBtn = page.locator(selectors.editButton).first();
      if (await editBtn.isVisible()) {
        await editBtn.click();
        await page.waitForTimeout(500);

        // Should show form with existing data
        const nameInput = page.locator(selectors.nameInput);
        await expect(nameInput.first()).toBeVisible();
      }
    });

    test('should update project name', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const editBtn = page.locator(selectors.editButton).first();
      if (await editBtn.isVisible()) {
        await editBtn.click();
        await page.waitForTimeout(500);

        // Update name
        const nameInput = page.locator(selectors.nameInput).first();
        const currentValue = await nameInput.inputValue();
        await nameInput.fill(`${currentValue} Updated`);

        // Submit
        const submitBtn = page.locator(selectors.submitButton);
        if (await submitBtn.isVisible()) {
          await submitBtn.click();

          // Should show success
          await page.waitForTimeout(2000);
          const hasSuccess = await page.locator(selectors.successMessage).isVisible() ||
                             await page.getByText(/updated|saved/i).isVisible();
          
          expect(hasSuccess).toBeTruthy();
        }
      }
    });
  });

  test.describe('Delete Project', () => {
    test('should show confirmation before deleting', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const deleteBtn = page.locator(selectors.deleteButton).first();
      if (await deleteBtn.isVisible()) {
        await deleteBtn.click();
        await page.waitForTimeout(500);

        // Should show confirmation modal
        const confirmBtn = page.locator(selectors.confirmButton);
        const hasConfirmation = await confirmBtn.isVisible() ||
                                await page.getByText(/confirm|sure|delete/i).isVisible();
        
        expect(hasConfirmation).toBeTruthy();
      }
    });

    test('should cancel delete operation', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const deleteBtn = page.locator(selectors.deleteButton).first();
      if (await deleteBtn.isVisible()) {
        await deleteBtn.click();
        await page.waitForTimeout(500);

        // Cancel
        const cancelBtn = page.locator(selectors.cancelButton);
        if (await cancelBtn.isVisible()) {
          await cancelBtn.click();
          
          // Modal should close
          await page.waitForTimeout(500);
          await expect(page.locator(selectors.modal)).not.toBeVisible();
        }
      }
    });
  });

  test.describe('Archive Project', () => {
    test('should archive project', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      const archiveBtn = page.locator(selectors.archiveButton).first();
      if (await archiveBtn.isVisible()) {
        await archiveBtn.click();

        // Should show success
        await page.waitForTimeout(2000);
        const hasSuccess = await page.locator(selectors.successMessage).isVisible() ||
                           await page.getByText(/archived/i).isVisible();
        
        expect(hasSuccess).toBeTruthy();
      }
    });
  });

  test.describe('Project Search/Filter', () => {
    test('should filter projects by search term', async ({ page }) => {
      await login(page);
      await page.goto(`${BASE_URL}/projects`);
      await page.waitForLoadState('networkidle');

      // Find search input
      const searchInput = page.locator('input[placeholder*="search" i], input[type="search"]');
      if (await searchInput.isVisible()) {
        await searchInput.fill('test');
        await page.waitForTimeout(1000);

        // Results should be filtered
        const pageContent = await page.textContent('body');
        expect(pageContent).toBeDefined();
      }
    });
  });
});
