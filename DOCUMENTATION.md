# Time Tracker - Complete Documentation

## Table of Contents
1. [Quick Start Guide](#quick-start-guide)
2. [User Guide](#user-guide)
3. [Admin Guide](#admin-guide)
4. [API Documentation](#api-documentation)
5. [Developer Guide](#developer-guide)
6. [Architecture Overview](#architecture-overview)
7. [Deployment Guide](#deployment-guide)

---

## Quick Start Guide

### Prerequisites
- Node.js 18+ (frontend)
- Python 3.11+ (backend)
- PostgreSQL 15+
- Redis 7+
- Docker (optional, recommended)

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/timetracker.git
cd timetracker

# Start all services
docker-compose up -d

# The application will be available at:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8080
# - API Docs: http://localhost:8080/docs
```

### Manual Setup

#### Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8080
```

#### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration

# Start the development server
npm run dev
```

### Default Credentials
- Admin: `admin@timetracker.com` / (set during initial setup)
- Worker: `worker@timetracker.com` / (set during initial setup)

---

## User Guide

### Dashboard
The dashboard provides an overview of your time tracking activity:
- **Today's Time**: Total hours tracked today
- **This Week**: Weekly total
- **This Month**: Monthly total
- **Active Projects**: Number of projects you're working on

### Tracking Time

#### Using the Timer
1. Select a project from the dropdown
2. Optionally select a task
3. Add a description (optional)
4. Click "Start Timer"
5. Click "Stop" when finished

#### Manual Time Entry
1. Navigate to Time Entries
2. Click "Add Entry"
3. Select project, task, date, and times
4. Save the entry

### Projects
- View all projects you have access to
- Click on a project to see details
- Track time on specific projects

### Tasks
- View tasks organized by status (To Do, In Progress, Done)
- Create new tasks
- Update task status by dragging or using the dropdown
- Track time on specific tasks

### Reports
- View time summaries by project
- Export data as CSV
- Filter by date range

---

## Admin Guide

### User Management
Access: Settings > Users (Admin only)

#### Capabilities:
- View all users
- Change user roles (Admin/Regular User)
- Deactivate/Activate accounts
- Edit user details

#### User Roles:
| Role | Description |
|------|-------------|
| Super Admin | Full access to all features, can manage users |
| Regular User | Can track time, view own reports, manage tasks |

### Team Management
- Create teams
- Add/remove team members
- Assign team roles (Owner, Admin, Member)

### Project Management
- Create projects and assign to teams
- Archive inactive projects
- View project statistics

### Dashboard Overview
Admin dashboard shows:
- Team-wide time totals
- Active users today
- Running timers
- Time by user breakdown

### Reports
- Generate team reports
- Export time data for payroll
- View time by project/user

---

## API Documentation

Full API documentation is available at `/docs` when the server is running.

### Authentication

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

#### Using the Token
Include the token in the Authorization header:
```http
Authorization: Bearer eyJ...
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/login | User login |
| POST | /api/auth/register | User registration |
| GET | /api/auth/me | Get current user |
| GET | /api/projects | List projects |
| POST | /api/projects | Create project |
| GET | /api/tasks | List tasks |
| POST | /api/tasks | Create task |
| GET | /api/time | List time entries |
| POST | /api/time/start | Start timer |
| POST | /api/time/stop | Stop timer |
| GET | /api/reports/dashboard | Get dashboard stats |

---

## Developer Guide

### Project Structure

```
timetracker/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy models
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── middleware/     # Custom middleware
│   │   ├── utils/          # Utilities
│   │   ├── main.py         # FastAPI app
│   │   ├── config.py       # Configuration
│   │   └── database.py     # Database setup
│   ├── alembic/            # Database migrations
│   ├── tests/              # Test files
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── stores/         # Zustand stores
│   │   ├── hooks/          # Custom hooks
│   │   ├── types/          # TypeScript types
│   │   └── utils/          # Utilities
│   ├── package.json
│   └── vite.config.ts
├── docker/                  # Docker configs
└── docker-compose.yml
```

### Running Tests

#### Backend Tests
```bash
cd backend
pytest --cov=app --cov-report=html
```

#### Frontend Tests
```bash
cd frontend
npm test
```

### Code Style

#### Backend (Python)
- Use Black for formatting
- Use Ruff for linting
- Follow PEP 8 guidelines

```bash
black .
ruff check .
```

#### Frontend (TypeScript)
- Use ESLint
- Use Prettier

```bash
npm run lint
npm run format
```

### Creating a Migration

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Adding a New API Endpoint

1. Create/update the model in `app/models/`
2. Create/update the schema in `app/schemas/`
3. Create the router in `app/routers/`
4. Register the router in `app/main.py`
5. Add tests in `tests/`

### Adding a New Frontend Page

1. Create the page component in `src/pages/`
2. Add the route in `src/App.tsx`
3. Update navigation if needed
4. Add API calls to `src/api/client.ts`

---

## Architecture Overview

### Technology Stack

#### Backend
- **FastAPI**: High-performance Python web framework
- **SQLAlchemy 2.0**: Async ORM
- **PostgreSQL**: Primary database
- **Redis**: Caching and rate limiting
- **Alembic**: Database migrations
- **JWT**: Authentication tokens

#### Frontend
- **React 18**: UI library
- **TypeScript**: Type safety
- **Vite**: Build tool
- **TailwindCSS**: Styling
- **Zustand**: State management
- **React Query**: Data fetching
- **Recharts**: Charts and graphs

### Security Features
- JWT-based authentication with refresh tokens
- Password hashing with bcrypt
- Rate limiting
- CORS protection
- SQL injection prevention
- XSS protection
- CSRF protection
- Input validation

### Database Schema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Users     │────<│ TeamMembers  │>────│    Teams     │
└──────────────┘     └──────────────┘     └──────────────┘
       │                                         │
       │                                         │
       ▼                                         ▼
┌──────────────┐                          ┌──────────────┐
│ TimeEntries  │────────────────────────>│   Projects   │
└──────────────┘                          └──────────────┘
       │                                         │
       │                                         │
       ▼                                         ▼
┌──────────────┐                          ┌──────────────┐
│ (optional)   │                          │    Tasks     │
└──────────────┘                          └──────────────┘
```

---

## Deployment Guide

### Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Disable `DEBUG` mode
- [ ] Configure proper `ALLOWED_ORIGINS`
- [ ] Set up SSL/TLS certificates
- [ ] Configure database backups
- [ ] Set up monitoring (Sentry, etc.)
- [ ] Configure rate limits
- [ ] Review security headers

### Docker Deployment

```bash
# Build and deploy with production settings
docker-compose -f docker-compose.prod.yml up -d --build
```

### Environment Variables

#### Required
| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key (min 32 chars) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `ALLOWED_ORIGINS` | CORS allowed origins |

#### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | false | Enable debug mode |
| `LOG_LEVEL` | INFO | Logging level |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | 60 | Rate limit |

### Health Checks

- Backend: `GET /health`
- Database: Check via application health endpoint
- Redis: Check via application health endpoint

### Scaling

#### Horizontal Scaling
- Use multiple backend instances behind a load balancer
- Use Redis for session storage
- Configure database connection pooling

#### Recommended Setup
```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │  Backend 1   │  │  Backend 2   │  │  Backend 3   │
 └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │  PostgreSQL  │  │    Redis     │  │   Frontend   │
 │  (Primary)   │  │   Cluster    │  │     CDN      │
 └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Support

For issues and feature requests, please use the GitHub Issues page.

For security vulnerabilities, please email security@timetracker.com.

---

*Documentation last updated: December 2025*
