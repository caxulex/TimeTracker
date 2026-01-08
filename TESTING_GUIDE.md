# TimeTracker Testing Guide

**Last Updated:** January 8, 2026  
**Application Version:** 2.0.0+

## Overview

This guide documents the comprehensive testing strategy for the TimeTracker application. Our testing approach covers:

- **Backend Tests**: Unit and integration tests for FastAPI endpoints
- **Frontend Unit Tests**: Component and store tests with Vitest
- **End-to-End Tests**: Critical user flow tests with Playwright

## Test Stack

### Backend
- **Framework**: pytest with pytest-asyncio
- **Database**: PostgreSQL with test fixtures
- **Mocking**: unittest.mock for external services
- **Coverage**: pytest-cov

### Frontend
- **Unit Testing**: Vitest + React Testing Library
- **E2E Testing**: Playwright
- **Mocking**: vi.mock for API/store mocking

---

## Running Tests

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v

# Run specific test class/function
pytest tests/test_auth.py::TestLogin -v
pytest tests/test_auth.py::TestLogin::test_login_success -v

# Run with specific markers
pytest -m "not slow"

# Run in parallel (if pytest-xdist installed)
pytest -n auto
```

### Frontend Unit Tests

```bash
cd frontend

# Run all tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage

# Run specific file
npm test -- src/stores/authStore.test.ts

# Run with UI
npm run test:ui
```

### E2E Tests

```bash
cd frontend

# Run all E2E tests
npm run test:e2e

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific spec file
npx playwright test e2e/critical-flows.spec.ts

# Run with debugging
npx playwright test --debug

# Open last HTML report
npx playwright show-report
```

---

## Test Structure

### Backend Test Organization

```
backend/tests/
├── conftest.py              # Shared fixtures
├── test_auth.py             # Authentication endpoints
├── test_users.py            # User management
├── test_companies.py        # Company management
├── test_teams.py            # Team management
├── test_projects.py         # Project CRUD
├── test_tasks.py            # Task CRUD
├── test_time_entries.py     # Time entry management
├── test_timer.py            # Timer operations
├── test_reports.py          # Reporting endpoints
├── test_websocket.py        # WebSocket functionality
├── test_multitenancy.py     # Multi-tenant isolation
├── test_email_service.py    # Email service (mocked)
└── test_password_reset.py   # Password reset flow
```

### Frontend Test Organization

```
frontend/src/
├── stores/
│   ├── authStore.test.ts       # Auth store tests
│   └── timerStore.test.ts      # Timer store tests
├── pages/
│   ├── LoginPage.test.tsx      # Login page tests
│   ├── DashboardPage.test.tsx  # Dashboard tests
│   └── TimePage.test.tsx       # Time entries tests
├── components/
│   └── time/
│       └── TimerWidget.test.tsx  # Timer widget tests
├── hooks/
│   └── useAuth.test.ts         # useAuth hook tests
└── api/
    └── client.test.ts          # API client tests

frontend/e2e/
├── app.spec.ts              # Basic app tests
├── critical-flows.spec.ts   # Critical user journeys
├── registration.spec.ts     # Registration flow
├── password-reset.spec.ts   # Password reset flow
├── multi-tenant.spec.ts     # Multi-tenancy tests
├── projects.spec.ts         # Project management
└── timer.spec.ts            # Timer operations
```

---

## Test Categories

### Unit Tests

Test individual functions, components, and modules in isolation.

**Backend Example:**
```python
@pytest.mark.asyncio
async def test_create_time_entry(client, auth_headers):
    """Test creating a time entry."""
    response = await client.post(
        "/api/time-entries",
        json={
            "project_id": 1,
            "description": "Test entry",
            "start_time": "2026-01-08T09:00:00Z",
            "end_time": "2026-01-08T10:00:00Z",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Test entry"
```

**Frontend Example:**
```typescript
describe('authStore', () => {
  it('should login successfully', async () => {
    await act(async () => {
      await useAuthStore.getState().login({
        email: 'test@example.com',
        password: 'password',
      });
    });
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });
});
```

### Integration Tests

Test multiple components working together.

**Multi-tenancy Test:**
```python
@pytest.mark.asyncio
async def test_company_data_isolation(client, company1_headers, company2_headers):
    """Users from different companies cannot see each other's data."""
    # Create project as company1
    response = await client.post(
        "/api/projects",
        json={"name": "Company1 Project"},
        headers=company1_headers,
    )
    project_id = response.json()["id"]
    
    # Company2 user should not see it
    response = await client.get(
        f"/api/projects/{project_id}",
        headers=company2_headers,
    )
    assert response.status_code == 404
```

### E2E Tests

Test complete user workflows end-to-end.

**Timer Flow:**
```typescript
test('should start and stop timer', async ({ page }) => {
  await login(page, TEST_USER.email, TEST_USER.password);
  await page.goto('/time');
  
  // Start timer
  await page.click('[data-testid="start-timer"]');
  await expect(page.locator('[data-testid="stop-timer"]')).toBeVisible();
  
  // Wait for some time
  await page.waitForTimeout(3000);
  
  // Stop timer
  await page.click('[data-testid="stop-timer"]');
  await expect(page.locator('[data-testid="start-timer"]')).toBeVisible();
});
```

---

## Test Fixtures

### Backend Fixtures (conftest.py)

```python
@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password"),
        company_id=1,
    )
    db_session.add(user)
    await db_session.commit()
    return user

@pytest.fixture
async def auth_headers(test_user):
    """Get authentication headers for test user."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}
```

### Frontend Test Wrappers

```typescript
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NotificationProvider>
          <BrandingProvider>
            {children}
          </BrandingProvider>
        </NotificationProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};
```

---

## Mocking Strategies

### Backend - Email Service

```python
@pytest.fixture
def mock_smtp(mocker):
    """Mock SMTP connection for email tests."""
    mock = mocker.patch('smtplib.SMTP')
    mock.return_value.__enter__ = Mock()
    mock.return_value.__exit__ = Mock()
    return mock

async def test_send_email(mock_smtp):
    await email_service.send_email(
        to="user@example.com",
        subject="Test",
        body="Test body",
    )
    mock_smtp.return_value.send_message.assert_called_once()
```

### Frontend - API Calls

```typescript
vi.mock('../api/client', () => ({
  timeEntriesApi: {
    getAll: vi.fn(() => Promise.resolve({
      items: [/* mock data */],
      total: 1,
    })),
    create: vi.fn(() => Promise.resolve({ id: 1 })),
  },
}));
```

---

## Test Coverage Goals

| Area | Current | Target |
|------|---------|--------|
| Backend API | ~90% | 95% |
| Frontend Stores | ~80% | 90% |
| Frontend Components | ~50% | 70% |
| E2E Critical Paths | ~70% | 90% |

### Critical Paths to Test

1. **Authentication** ✅
   - Login, logout, session management
   - Token refresh
   - Password reset flow

2. **Timer Operations** ✅
   - Start/stop timer
   - Timer persistence across reloads
   - Time entry creation

3. **Multi-tenancy** ✅
   - Data isolation between companies
   - White-label branding
   - Cross-company access prevention

4. **Admin Functions** ✅
   - User management
   - Project management
   - Reports generation

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm test -- --coverage
      - run: npx playwright install --with-deps
      - run: npm run test:e2e
```

---

## Troubleshooting

### Common Issues

1. **Database connection errors in tests**
   - Ensure test database exists
   - Check `DATABASE_URL_TEST` environment variable

2. **Async test timeouts**
   - Use `@pytest.mark.asyncio` decorator
   - Increase timeout: `@pytest.mark.timeout(30)`

3. **Frontend test flakiness**
   - Use `waitFor` for async operations
   - Mock all external API calls
   - Reset store state in `beforeEach`

4. **E2E test failures**
   - Ensure dev server is running
   - Check BASE_URL configuration
   - Use `--debug` flag to step through

### Debug Commands

```bash
# Backend - verbose output
pytest -v --tb=long

# Frontend - debug specific test
npm test -- --reporter=verbose src/stores/authStore.test.ts

# E2E - step through test
npx playwright test --debug e2e/timer.spec.ts
```

---

## Writing New Tests

### Checklist

- [ ] Test happy path
- [ ] Test edge cases
- [ ] Test error conditions
- [ ] Test with different user roles
- [ ] Test multi-tenant isolation (if applicable)
- [ ] Mock external services
- [ ] Clean up test data

### Naming Convention

```
test_<action>_<condition>_<expected_result>

Examples:
- test_login_with_valid_credentials_returns_token
- test_create_project_without_name_returns_400
- test_timer_stop_creates_time_entry
```

---

## Contact

For testing-related questions:
- Check existing tests for patterns
- Review this guide
- Consult team lead for complex scenarios
