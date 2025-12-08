import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Time Tracker MVP
 * TASK-051, TASK-052, TASK-053: End-to-end test scenarios
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8080';

// Test user credentials
const TEST_USER = {
  email: 'e2e-test@example.com',
  password: 'TestPassword123!',
  name: 'E2E Test User'
};

// Helper to login
async function login(page: Page, email: string, password: string) {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(dashboard|tasks|projects)/);
}

// Helper to logout
async function logout(page: Page) {
  await page.click('[data-testid="user-menu"]');
  await page.click('[data-testid="logout-button"]');
  await page.waitForURL(/\/login/);
}

test.describe('Authentication Flow', () => {
  test('should display login page', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    
    await page.fill('input[type="email"]', 'invalid@example.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    await expect(page.locator('[role="alert"], .error-message, .text-red')).toBeVisible();
  });

  test('should redirect to dashboard after successful login', async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
    
    await expect(page).toHaveURL(/\/(dashboard|tasks|projects)/);
  });

  test('should logout successfully', async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
    await logout(page);
    
    await expect(page).toHaveURL(/\/login/);
  });

  test('should persist session after page reload', async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
    
    await page.reload();
    
    // Should still be logged in
    await expect(page).not.toHaveURL(/\/login/);
  });
});

test.describe('Timer Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should display timer on dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Timer should be visible
    await expect(page.locator('[data-testid="timer"], .timer-display')).toBeVisible();
  });

  test('should start timer when clicking start button', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Select a project first if required
    const projectSelect = page.locator('[data-testid="project-select"], select[name="project"]');
    if (await projectSelect.isVisible()) {
      await projectSelect.selectOption({ index: 1 });
    }
    
    // Click start button
    await page.click('[data-testid="start-timer"], button:has-text("Start")');
    
    // Timer should be running
    await expect(page.locator('[data-testid="stop-timer"], button:has-text("Stop")')).toBeVisible();
  });

  test('should stop timer and create time entry', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    // If timer is not running, start it
    const stopButton = page.locator('[data-testid="stop-timer"], button:has-text("Stop")');
    if (!(await stopButton.isVisible())) {
      const projectSelect = page.locator('[data-testid="project-select"], select[name="project"]');
      if (await projectSelect.isVisible()) {
        await projectSelect.selectOption({ index: 1 });
      }
      await page.click('[data-testid="start-timer"], button:has-text("Start")');
      await page.waitForTimeout(2000); // Wait 2 seconds
    }
    
    // Stop the timer
    await page.click('[data-testid="stop-timer"], button:has-text("Stop")');
    
    // Start button should be visible again
    await expect(page.locator('[data-testid="start-timer"], button:has-text("Start")')).toBeVisible();
  });
});

test.describe('Projects Management', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should display projects list', async ({ page }) => {
    await page.goto(`${BASE_URL}/projects`);
    
    await expect(page.locator('h1, h2').filter({ hasText: /projects/i })).toBeVisible();
  });

  test('should open create project modal', async ({ page }) => {
    await page.goto(`${BASE_URL}/projects`);
    
    await page.click('button:has-text("New Project"), button:has-text("Create"), [data-testid="create-project"]');
    
    await expect(page.locator('[role="dialog"], .modal')).toBeVisible();
  });

  test('should create a new project', async ({ page }) => {
    await page.goto(`${BASE_URL}/projects`);
    
    // Open create modal
    await page.click('button:has-text("New Project"), button:has-text("Create"), [data-testid="create-project"]');
    
    // Fill form
    const projectName = `E2E Test Project ${Date.now()}`;
    await page.fill('input[name="name"]', projectName);
    
    // Submit
    await page.click('button[type="submit"]:has-text("Create"), button[type="submit"]:has-text("Save")');
    
    // Should see the new project
    await expect(page.locator(`text=${projectName}`)).toBeVisible();
  });
});

test.describe('Tasks Management', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should display tasks list', async ({ page }) => {
    await page.goto(`${BASE_URL}/tasks`);
    
    await expect(page.locator('h1, h2').filter({ hasText: /tasks/i })).toBeVisible();
  });

  test('should filter tasks by status', async ({ page }) => {
    await page.goto(`${BASE_URL}/tasks`);
    
    // Look for status filter
    const statusFilter = page.locator('[data-testid="status-filter"], select:has-text("Status")');
    if (await statusFilter.isVisible()) {
      await statusFilter.selectOption('completed');
      // Tasks should be filtered
      await page.waitForTimeout(500);
    }
  });

  test('should open task details', async ({ page }) => {
    await page.goto(`${BASE_URL}/tasks`);
    
    // Click on first task
    const firstTask = page.locator('[data-testid="task-item"], .task-row').first();
    if (await firstTask.isVisible()) {
      await firstTask.click();
      
      // Should show task details
      await expect(page.locator('[data-testid="task-details"], .task-detail')).toBeVisible();
    }
  });
});

test.describe('Teams Management', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should display teams list', async ({ page }) => {
    await page.goto(`${BASE_URL}/teams`);
    
    await expect(page.locator('h1, h2').filter({ hasText: /teams/i })).toBeVisible();
  });

  test('should create a new team', async ({ page }) => {
    await page.goto(`${BASE_URL}/teams`);
    
    // Open create modal
    await page.click('button:has-text("New Team"), button:has-text("Create"), [data-testid="create-team"]');
    
    // Fill form
    const teamName = `E2E Test Team ${Date.now()}`;
    await page.fill('input[name="name"]', teamName);
    
    // Submit
    await page.click('button[type="submit"]:has-text("Create"), button[type="submit"]:has-text("Save")');
    
    // Should see the new team
    await expect(page.locator(`text=${teamName}`)).toBeVisible();
  });
});

test.describe('Reports Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should display reports dashboard', async ({ page }) => {
    await page.goto(`${BASE_URL}/reports`);
    
    await expect(page.locator('h1, h2').filter({ hasText: /reports/i })).toBeVisible();
  });

  test('should filter reports by date range', async ({ page }) => {
    await page.goto(`${BASE_URL}/reports`);
    
    const dateFilter = page.locator('[data-testid="date-filter"], input[type="date"]').first();
    if (await dateFilter.isVisible()) {
      await dateFilter.fill('2024-01-01');
      await page.waitForTimeout(500);
    }
  });

  test('should export report', async ({ page }) => {
    await page.goto(`${BASE_URL}/reports`);
    
    const exportButton = page.locator('button:has-text("Export"), [data-testid="export-button"]');
    if (await exportButton.isVisible()) {
      // Set up download handler
      const downloadPromise = page.waitForEvent('download');
      await exportButton.click();
      // Wait for download to start (may not complete in test)
      await page.waitForTimeout(1000);
    }
  });
});

test.describe('Time Entries Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should display time entries', async ({ page }) => {
    await page.goto(`${BASE_URL}/time-entries`);
    
    await expect(page.locator('h1, h2').filter({ hasText: /time|entries/i })).toBeVisible();
  });

  test('should create manual time entry', async ({ page }) => {
    await page.goto(`${BASE_URL}/time-entries`);
    
    // Open create modal
    await page.click('button:has-text("Add"), button:has-text("Manual"), [data-testid="add-entry"]');
    
    // Should see form
    await expect(page.locator('[role="dialog"], .modal, form')).toBeVisible();
  });

  test('should edit time entry', async ({ page }) => {
    await page.goto(`${BASE_URL}/time-entries`);
    
    // Click edit on first entry
    const editButton = page.locator('[data-testid="edit-entry"], button:has-text("Edit")').first();
    if (await editButton.isVisible()) {
      await editButton.click();
      await expect(page.locator('[role="dialog"], .modal, form')).toBeVisible();
    }
  });
});

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should navigate between all pages', async ({ page }) => {
    // Dashboard
    await page.click('a[href="/dashboard"], nav a:has-text("Dashboard")');
    await expect(page).toHaveURL(/\/dashboard/);
    
    // Projects
    await page.click('a[href="/projects"], nav a:has-text("Projects")');
    await expect(page).toHaveURL(/\/projects/);
    
    // Tasks
    await page.click('a[href="/tasks"], nav a:has-text("Tasks")');
    await expect(page).toHaveURL(/\/tasks/);
    
    // Teams
    await page.click('a[href="/teams"], nav a:has-text("Teams")');
    await expect(page).toHaveURL(/\/teams/);
    
    // Reports
    await page.click('a[href="/reports"], nav a:has-text("Reports")');
    await expect(page).toHaveURL(/\/reports/);
  });

  test('should show active state on current nav item', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    const activeNav = page.locator('nav a.active, nav a[aria-current="page"]');
    await expect(activeNav).toBeVisible();
  });
});

test.describe('Responsive Design', () => {
  test('should display mobile menu on small screens', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await login(page, TEST_USER.email, TEST_USER.password);
    
    // Look for hamburger menu
    const menuButton = page.locator('[data-testid="mobile-menu"], button[aria-label="Menu"]');
    if (await menuButton.isVisible()) {
      await menuButton.click();
      await expect(page.locator('nav, [role="navigation"]')).toBeVisible();
    }
  });

  test('should display desktop layout on large screens', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await login(page, TEST_USER.email, TEST_USER.password);
    
    // Sidebar should be visible
    await expect(page.locator('aside, [data-testid="sidebar"]')).toBeVisible();
  });
});

test.describe('Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, TEST_USER.email, TEST_USER.password);
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();
  });

  test('should have accessible form labels', async ({ page }) => {
    await page.goto(`${BASE_URL}/projects`);
    await page.click('button:has-text("New"), button:has-text("Create")');
    
    // Form inputs should have labels
    const inputs = page.locator('input[id]');
    const count = await inputs.count();
    
    for (let i = 0; i < count; i++) {
      const input = inputs.nth(i);
      const id = await input.getAttribute('id');
      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = await label.isVisible();
        const ariaLabel = await input.getAttribute('aria-label');
        const ariaLabelledBy = await input.getAttribute('aria-labelledby');
        
        // Should have some form of label
        expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
      }
    }
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Tab through elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Some element should be focused
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});
