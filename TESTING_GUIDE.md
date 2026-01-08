# TimeTracker Testing Guide

**Last Updated:** January 8, 2026  
**Application Version:** 2.0.0+  
**Test Status:** 291+ tests passing (154 backend, 137 frontend)

## Overview

This guide documents the comprehensive testing strategy for the TimeTracker application. Our testing approach covers:

- **Backend Tests**: Unit and integration tests for FastAPI endpoints (154 tests)
- **Frontend Unit Tests**: Component and store tests with Vitest (137 tests)
- **End-to-End Tests**: Critical user flow tests with Playwright
- **AI Features Tests**: Tests for all AI-powered features (Phases 0.2-5.2)
- **White-Label/Branding Tests**: Multi-tenant branding tests

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

5. **AI Features** ✅
   - Smart descriptions
   - Task categorization
   - Productivity alerts
   - AI reports generation

---

## Testing AI Features

### AI Feature Test Categories

| Phase | Feature | Test File | Status |
|-------|---------|-----------|--------|
| 0.2 | AI Infrastructure | `test_ai_features.py` | ✅ |
| 1.1 | Smart Descriptions | `test_ai_features.py` | ✅ |
| 1.2 | Task Categorization | `test_ai_features.py` | ✅ |
| 2.1 | Time Entry Validation | `test_ai_features.py` | ✅ |
| 2.2 | Break Optimization | `test_ai_features.py` | ✅ |
| 3.1 | Daily Summaries | `test_ai_features.py` | ✅ |
| 3.2 | Weekly Analysis | `test_ai_features.py` | ✅ |
| 4.1 | Productivity Alerts | `test_ai_features.py` | ✅ |
| 4.2 | AI Reports | `test_ai_features.py` | ✅ |
| 5.1 | Semantic Search | `test_ai_features.py` | ✅ |
| 5.2 | Team Analytics | `test_ai_features.py` | ✅ |

### Running AI Tests

```bash
cd backend

# Run all AI tests
pytest tests/test_ai_features.py -v

# Run specific AI feature test
pytest tests/test_ai_features.py::TestSmartDescriptions -v
pytest tests/test_ai_features.py::TestTaskCategorization -v
pytest tests/test_ai_features.py::TestProductivityAlerts -v

# Run with AI provider mocked
pytest tests/test_ai_features.py -v --mock-ai
```

### AI API Endpoints to Test

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai/settings/features` | GET | List all AI features |
| `/api/ai/preferences` | GET/PUT | User AI preferences |
| `/api/ai/assist/description` | POST | Generate smart description |
| `/api/ai/assist/categorize` | POST | Auto-categorize entry |
| `/api/ai/validate/entry` | POST | Validate time entry |
| `/api/ai/analyze/patterns` | GET | Weekly work patterns |
| `/api/ai/generate/summary` | POST | Daily/weekly summary |
| `/api/ai/alerts/productivity` | GET | Productivity alerts |
| `/api/ai/reports/generate` | POST | AI-powered report |
| `/api/ai/search` | POST | Semantic search |
| `/api/ai/team-analytics` | GET | Team analytics |

### AI Test Examples

```python
@pytest.mark.asyncio
class TestSmartDescriptions:
    """Test AI smart description generation."""

    async def test_generate_description_success(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test generating a description for time entry."""
        response = await client.post(
            "/api/ai/assist/description",
            headers=auth_headers,
            json={
                "project_id": 1,
                "context": "Working on user authentication module"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "description" in data
        assert len(data["description"]) > 0

    async def test_generate_description_requires_auth(
        self, client: AsyncClient
    ):
        """Test endpoint requires authentication."""
        response = await client.post(
            "/api/ai/assist/description",
            json={"project_id": 1}
        )
        assert response.status_code in [401, 403]


@pytest.mark.asyncio
class TestProductivityAlerts:
    """Test AI productivity alerts."""

    async def test_get_alerts_returns_list(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting productivity alerts."""
        response = await client.get(
            "/api/ai/alerts/productivity",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data or isinstance(data, list)
```

### Manual AI Testing Checklist

```markdown
## AI Feature Manual Testing

### Prerequisites
- [ ] AI API key configured (GOOGLE_AI_KEY or OPENAI_API_KEY)
- [ ] AI features enabled in admin settings
- [ ] User AI preferences enabled

### Smart Descriptions (Phase 1.1)
- [ ] Create time entry without description
- [ ] Click "AI Suggest" button
- [ ] Verify description generated
- [ ] Description relevant to project context

### Task Categorization (Phase 1.2)
- [ ] Enter time entry with description
- [ ] Click "Auto-categorize"
- [ ] Verify category suggestion
- [ ] Verify tag suggestions

### Time Entry Validation (Phase 2.1)
- [ ] Enter unusual duration (16+ hours)
- [ ] Verify validation warning
- [ ] Check correction suggestion

### Daily Summary (Phase 3.1)
- [ ] Navigate to Reports > AI Summary
- [ ] Generate daily summary
- [ ] Verify time breakdown
- [ ] Verify productivity insights

### Productivity Alerts (Phase 4.1)
- [ ] Work without breaks
- [ ] Verify break reminder
- [ ] Check productivity tip

### AI Reports (Phase 4.2)
- [ ] Generate AI report
- [ ] Verify narrative summary
- [ ] Check recommendations
```

---

## Testing White-Label/Branding

### Environment Variables

```env
# White-label configuration
VITE_APP_NAME="Custom Portal"
VITE_APP_LOGO_URL="/custom-logo.png"
VITE_APP_FAVICON_URL="/custom-favicon.ico"
VITE_PRIMARY_COLOR="#FF5722"
VITE_SECONDARY_COLOR="#795548"
VITE_WHITE_LABELED="true"
VITE_SHOW_POWERED_BY="false"
VITE_SUPPORT_EMAIL="support@client.com"
```

### Branding Test Examples

```typescript
describe('BrandingContext', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  it('applies custom app name', () => {
    vi.stubEnv('VITE_APP_NAME', 'Custom App');
    render(<Header />, { wrapper: TestWrapper });
    expect(screen.getByText('Custom App')).toBeInTheDocument();
  });

  it('hides registration in white-label mode', () => {
    vi.stubEnv('VITE_WHITE_LABELED', 'true');
    render(<LoginPage />, { wrapper: TestWrapper });
    expect(screen.queryByText(/register/i)).not.toBeInTheDocument();
  });

  it('shows account request form when white-labeled', () => {
    vi.stubEnv('VITE_WHITE_LABELED', 'true');
    render(<LoginPage />, { wrapper: TestWrapper });
    expect(screen.getByText(/request account/i)).toBeInTheDocument();
  });
});
```

### White-Label Manual Testing Checklist

```markdown
## White-Label Testing

### Branding Elements
- [ ] App name in header
- [ ] Custom logo loads
- [ ] Favicon updated
- [ ] Primary color on buttons
- [ ] Secondary color on accents

### White-Label Mode (VITE_WHITE_LABELED=true)
- [ ] Registration hidden
- [ ] "Powered by" hidden
- [ ] Account request form visible
- [ ] Support links customized

### Company-Specific Branding
- [ ] Company logo on login
- [ ] Company colors applied
- [ ] Custom subdomain works

### Email Templates
- [ ] Welcome email branded
- [ ] Password reset branded
- [ ] Invitation email branded
```

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

### Common Issues & Solutions

#### 1. "Event loop is closed" Error

**Symptom:** Redis operations fail in async tests with `RuntimeError: Event loop is closed`

**Cause:** Test uses real Redis service that tries to access closed event loop

**Solution:** Mock Redis-dependent services:
```python
with patch('app.services.invitation_service.InvitationService.create_reset_token', 
           new_callable=AsyncMock) as mock_create:
    with patch('app.services.invitation_service.InvitationService.get_reset_token',
               new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        # ... test code
```

#### 2. Duplicate Key Constraint Error

**Symptom:** `asyncpg.UniqueViolationError: duplicate key value violates unique constraint`

**Cause:** Test fixtures use static slugs/emails that conflict between test runs

**Solution:** Use dynamic unique identifiers:
```python
import uuid

unique_id = uuid.uuid4().hex[:8]
company = Company(
    name="Test Company",
    slug=f"test-company-{unique_id}",
    email=f"test-{unique_id}@example.com",
    status="active",  # Note: use 'status' not 'is_active'
)
```

#### 3. API Response Format Mismatch

**Symptom:** Test expects list but receives `{"items": [...], "count": 0}`

**Cause:** API returns wrapped/paginated responses

**Solution:** Handle both formats:
```python
data = response.json()
items = data.get("items", data) if isinstance(data, dict) else data
# Or for timer responses:
timers = data.get("timers", data) if isinstance(data, dict) else data
```

#### 4. 307 Redirect on POST/PUT

**Symptom:** `AssertionError: assert 307 == 200`

**Cause:** FastAPI redirects trailing slashes

**Solution:** Remove trailing slashes from URLs:
```python
# Wrong
await client.post("/api/teams/", ...)

# Correct
await client.post("/api/teams", ...)
```

#### 5. pytest-asyncio Compatibility

**Symptom:** `TypeError: __init__() got an unexpected keyword argument 'asyncio_default_fixture_loop_scope'`

**Cause:** CI uses pytest-asyncio 0.21.1 which doesn't support this option

**Solution:** Remove from pyproject.toml:
```toml
# Remove this line:
# asyncio_default_fixture_loop_scope = "function"

# Use this instead:
asyncio_mode = "auto"
```

#### 6. Company Model Field Error

**Symptom:** `TypeError: unexpected keyword argument 'is_active'`

**Cause:** Company model uses `status` enum, not `is_active` boolean

**Solution:** Use correct field:
```python
# Wrong
company = Company(is_active=True, ...)

# Correct
company = Company(status="active", ...)  # or CompanyStatus.ACTIVE
```

#### 7. localStorage Not Persisting (Frontend)

**Symptom:** Tests fail because localStorage mock doesn't persist values

**Solution:** Create proper mock with internal store:
```typescript
const createMockStorage = () => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((i: number) => Object.keys(store)[i] || null),
  };
};

Object.defineProperty(window, 'localStorage', {
  value: createMockStorage(),
});
```

#### 8. Zustand State Leaking Between Tests

**Symptom:** Tests fail randomly due to state from previous test

**Solution:** Reset store state in beforeEach:
```typescript
beforeEach(() => {
  useAuthStore.setState({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });
  vi.clearAllMocks();
});
```

#### 9. Permission Denied (403) vs Not Found (404)

**Symptom:** Test expects 404 but gets 403, or vice versa

**Cause:** Authorization checks may return different codes based on timing

**Solution:** Accept both status codes:
```python
# For access denied scenarios
assert response.status_code in [403, 404]
```

#### 10. WebSocket Authentication Error

**Symptom:** WebSocket tests fail with 422 validation error

**Cause:** HTTP endpoint using `get_current_user_ws` instead of `get_current_user`

**Solution:** Use correct dependency:
```python
# For HTTP endpoints (not WebSocket)
@router.get("/active-timers")
async def get_active_timers(
    current_user: User = Depends(get_current_user),  # Not get_current_user_ws
):
    ...
```

### Debug Commands

```bash
# Backend - verbose output with long traceback
pytest -v --tb=long

# Backend - stop at first failure
pytest -x

# Backend - show print statements
pytest -s

# Frontend - debug specific test
npm test -- --reporter=verbose src/stores/authStore.test.ts

# E2E - step through test
npx playwright test --debug e2e/timer.spec.ts

# E2E - run with tracing
npx playwright test --trace on
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
