# Time Tracker API Documentation

## Overview

The Time Tracker API provides a RESTful interface for managing time tracking, projects, teams, and generating reports.

**Base URL:** `http://localhost:8080/api`  
**Documentation:** `http://localhost:8080/docs` (Swagger UI)  
**Alternative Docs:** `http://localhost:8080/redoc` (ReDoc)

## Authentication

All API endpoints (except `/auth/login` and `/auth/register`) require authentication.

### JWT Token Authentication

```bash
# Login to get tokens
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Using the Token

Include the access token in the Authorization header:

```bash
Authorization: Bearer eyJ...
```

### Refreshing Tokens

```bash
POST /api/auth/refresh
Authorization: Bearer {refresh_token}

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

## Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login and get tokens |
| POST | `/auth/logout` | Logout and invalidate tokens |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/auth/me` | Get current user info |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List all users (admin only) |
| GET | `/users/{id}` | Get user by ID |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user (admin only) |
| PUT | `/users/{id}/role` | Update user role (admin only) |

### Teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/teams` | List teams for current user |
| POST | `/teams` | Create a new team |
| GET | `/teams/{id}` | Get team details |
| PUT | `/teams/{id}` | Update team |
| DELETE | `/teams/{id}` | Delete team |
| GET | `/teams/{id}/members` | List team members |
| POST | `/teams/{id}/members` | Add team member |
| DELETE | `/teams/{id}/members/{user_id}` | Remove team member |
| PUT | `/teams/{id}/members/{user_id}` | Update member role |

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects` | List projects for current user |
| POST | `/projects` | Create a new project |
| GET | `/projects/{id}` | Get project details |
| PUT | `/projects/{id}` | Update project |
| DELETE | `/projects/{id}` | Delete project |
| GET | `/projects/{id}/time-entries` | Get project time entries |
| GET | `/projects/{id}/stats` | Get project statistics |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks` | List tasks |
| POST | `/tasks` | Create a new task |
| GET | `/tasks/{id}` | Get task details |
| PUT | `/tasks/{id}` | Update task |
| DELETE | `/tasks/{id}` | Delete task |
| PUT | `/tasks/{id}/status` | Update task status |
| PUT | `/tasks/{id}/assign` | Assign task to user |

### Time Entries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/time` | List time entries |
| POST | `/time` | Create manual time entry |
| GET | `/time/{id}` | Get time entry details |
| PUT | `/time/{id}` | Update time entry |
| DELETE | `/time/{id}` | Delete time entry |
| GET | `/time/timer` | Get current timer status |
| POST | `/time/start` | Start timer |
| POST | `/time/stop` | Stop timer |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reports/dashboard` | Get dashboard statistics |
| GET | `/reports/time` | Get time report with filters |
| GET | `/reports/weekly` | Get weekly breakdown |
| GET | `/reports/monthly` | Get monthly summary |
| GET | `/reports/projects/{id}` | Get project report |
| GET | `/reports/export` | Export report (CSV/PDF) |

### Payroll

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pay-rates` | List pay rates |
| POST | `/pay-rates` | Create pay rate |
| PUT | `/pay-rates/{id}` | Update pay rate |
| GET | `/payroll/periods` | List payroll periods |
| POST | `/payroll/periods` | Create payroll period |
| GET | `/payroll/periods/{id}` | Get period details |
| POST | `/payroll/periods/{id}/calculate` | Calculate payroll |
| GET | `/payroll-reports/summary` | Get payroll summary |

---

## Request/Response Examples

### Create Project

```bash
POST /api/projects
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Website Redesign",
  "description": "Redesign company website",
  "team_id": "uuid-of-team",
  "color": "#3B82F6",
  "is_billable": true,
  "hourly_rate": 75.00
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "name": "Website Redesign",
  "description": "Redesign company website",
  "team_id": "uuid-of-team",
  "color": "#3B82F6",
  "is_billable": true,
  "hourly_rate": 75.00,
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Start Timer

```bash
POST /api/time/start
Authorization: Bearer {token}
Content-Type: application/json

{
  "project_id": "uuid-of-project",
  "task_id": "uuid-of-task",
  "description": "Working on feature X"
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "project_id": "uuid-of-project",
  "task_id": "uuid-of-task",
  "description": "Working on feature X",
  "start_time": "2024-01-15T10:30:00Z",
  "end_time": null,
  "duration_seconds": null,
  "is_running": true
}
```

### Get Dashboard Stats

```bash
GET /api/reports/dashboard
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "today_hours": 4.5,
  "week_hours": 32.75,
  "month_hours": 142.5,
  "active_projects": 5,
  "total_entries": 1250,
  "running_timer": {
    "id": "uuid",
    "project_name": "Website Redesign",
    "elapsed_seconds": 3600
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request data",
  "errors": [
    {"field": "email", "message": "Invalid email format"}
  ]
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Not enough permissions"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

API requests are rate limited to prevent abuse:

- **Standard endpoints:** 100 requests per minute
- **Auth endpoints:** 10 requests per minute
- **Export endpoints:** 10 requests per hour

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705315200
```

---

## Pagination

List endpoints support pagination with the following query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |
| `sort` | string | created_at | Field to sort by |
| `order` | string | desc | Sort order (asc/desc) |

**Example:**
```bash
GET /api/time?page=2&per_page=50&sort=start_time&order=desc
```

**Response includes pagination info:**
```json
{
  "items": [...],
  "total": 250,
  "page": 2,
  "per_page": 50,
  "pages": 5
}
```

---

## Filtering

Many endpoints support filtering via query parameters:

### Time Entries
- `project_id` - Filter by project
- `task_id` - Filter by task
- `start_date` - Filter entries after this date
- `end_date` - Filter entries before this date
- `is_running` - Filter by running status

### Tasks
- `project_id` - Filter by project
- `status` - Filter by status (todo, in_progress, done)
- `assignee_id` - Filter by assignee

**Example:**
```bash
GET /api/time?project_id=uuid&start_date=2024-01-01&end_date=2024-01-31
```

---

## WebSocket API

Real-time updates are available via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws?token={access_token}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

### Message Types

| Type | Description |
|------|-------------|
| `timer_started` | Timer was started |
| `timer_stopped` | Timer was stopped |
| `entry_created` | Time entry created |
| `entry_updated` | Time entry updated |
| `entry_deleted` | Time entry deleted |
| `project_updated` | Project was updated |

---

## SDK Examples

### Python
```python
import requests

BASE_URL = "http://localhost:8080/api"
TOKEN = "your_access_token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Get projects
response = requests.get(f"{BASE_URL}/projects", headers=headers)
projects = response.json()

# Start timer
response = requests.post(
    f"{BASE_URL}/time/start",
    headers=headers,
    json={"project_id": "uuid"}
)
```

### JavaScript
```javascript
const API_URL = 'http://localhost:8080/api';
const token = 'your_access_token';

// Get projects
const response = await fetch(`${API_URL}/projects`, {
  headers: { Authorization: `Bearer ${token}` }
});
const projects = await response.json();

// Start timer
const timerResponse = await fetch(`${API_URL}/time/start`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ project_id: 'uuid' })
});
```
