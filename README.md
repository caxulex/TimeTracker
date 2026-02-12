# Time Tracker

A comprehensive, Time tracking application for teams and individuals. Built with modern technologies for performance, scalability, and user experience.

## ✨ Features

### Core Functionality
- **⏱️ Real-time Time Tracking** - Start/stop timers with one click
- **📊 Project Management** - Organize work by teams, projects, and tasks
- **👥 Team Collaboration** - Share projects, assign tasks, track team activity
- **📈 Reports & Analytics** - Weekly summaries, project breakdowns, exportable data
- **🔄 WebSocket Integration** - See who's working now in real-time

### User Experience
- **🎨 Modern UI** - Clean, responsive interface built with React and TailwindCSS
- **📱 Mobile Responsive** - Works on all devices
- **⚡ Fast & Reliable** - Optimized for performance

### Administrative Features
- **👤 Staff Management** - Comprehensive employee management with multi-step wizard
- **💰 Payroll Integration** - Pay rates, periods, and automated reporting
- **📋 Account Requests** - Self-service access request system for prospective staff
- **🔐 Role-Based Access** - Fine-grained permissions (Worker, Admin, Super Admin)
- **📊 Admin Dashboard** - Real-time monitoring and analytics

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **PostgreSQL** - Robust relational database
- **Redis** - Caching and session management
- **SQLAlchemy 2.0** - Async ORM with type hints
- **Pydantic 2** - Data validation and serialization

### Frontend
- **React 18** - Component-based UI library
- **TypeScript** - Type-safe JavaScript
- **Vite** - Lightning-fast build tool
- **TailwindCSS** - Utility-first CSS framework
- **Zustand** - Lightweight state management
- **React Query** - Server state management

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Production web server

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for development)
- Python 3.11+ (for development)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/time-tracker.git
   cd time-tracker
   ```

2. **Start the database and cache**
   ```bash
   docker-compose up -d postgres redis
   ```

3. **Backend Setup**
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload --port 8080
   ```

4. **Frontend Setup** (new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Access the application**
   - Frontend: http://localhost:5173
   - API Docs: http://localhost:8080/docs
   - Default Admin: admin@your-domain.com / (set via FIRST_SUPER_ADMIN_PASSWORD env var)

### Production Deployment

1. **Configure environment**
   ```bash
   cp .env.production.example .env
   # Edit .env with your production values
   ```

2. **Build and run**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

3. **Access at** http://localhost (or your domain)

## 📁 Project Structure

```
time-tracker/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── routers/        # API endpoints
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   └── main.py         # Application entry
│   ├── tests/              # Pytest test suite
│   ├── alembic/            # Database migrations
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom hooks
│   │   ├── stores/         # Zustand stores
│   │   └── services/       # API services
│   └── package.json
├── docker-compose.yml      # Development containers
├── docker-compose.prod.yml # Production containers
└── README.md
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend Unit Tests
```bash
cd frontend
npx vitest run
```

### Frontend Type Check
```bash
cd frontend
npx tsc --noEmit
```

### Load Tests
```bash
# Create test users first
cd backend && python setup_load_test_users.py

# Run Phase 9B load test (115 concurrent users)
cd .. && locust -f locustfile_phase9b.py --host=http://127.0.0.1:8000
# Open http://localhost:8089, set 115 users, spawn rate 10/s, run 5 min
```

**Test Coverage:**
- ✅ Authentication (register, login, tokens, password reset)
- ✅ Projects (CRUD, permissions, budgets)
- ✅ Time Entries (create, start/stop, update, delete)
- ✅ Teams (CRUD, membership)
- ✅ Reports (dashboard, weekly, project, admin, export)
- ✅ Payroll (pay rates, periods, processing)
- ✅ Multi-tenancy (company isolation, branding)
- ✅ AI Features (NLP, estimation, toggles)
- ✅ Security (audit logs, rate limiting, encryption)
- ✅ i18n (translation completeness, component rendering)
- ✅ WebSocket (real-time updates, reconnection)

## 🌐 Internationalization (i18n)

The app uses `react-i18next` for internationalization. English is the default language.

### Adding a New Language

1. Copy the English translation file:
   ```bash
   mkdir -p frontend/src/i18n/locales/es
   cp frontend/src/i18n/locales/en/translation.json frontend/src/i18n/locales/es/translation.json
   ```

2. Translate all string values (keep keys unchanged).

3. Register in `frontend/src/i18n/config.ts`:
   ```typescript
   import es from './locales/es/translation.json';
   // add to resources: es: { translation: es }
   ```

See [docs/I18N_GUIDE.md](docs/I18N_GUIDE.md) for the full guide.

## 🔧 Environment Variables

### Backend (`backend/.env`)

| Variable                     | Required | Description                              |
|------------------------------|----------|------------------------------------------|
| `SECRET_KEY`                 | ✅       | JWT signing key (64+ chars)              |
| `DATABASE_URL`               | ✅       | PostgreSQL connection string             |
| `REDIS_URL`                  | ✅       | Redis connection string                  |
| `ALLOWED_ORIGINS`            | ✅       | CORS origins (JSON array)                |
| `FIRST_SUPER_ADMIN_EMAIL`    | ✅       | Initial admin email                      |
| `FIRST_SUPER_ADMIN_PASSWORD` | ✅       | Initial admin password                   |
| `SENTRY_DSN`                 | Optional | Sentry error tracking DSN                |
| `API_KEY_ENCRYPTION_KEY`     | Optional | Fernet key for AI API key encryption     |
| `OPENAI_API_KEY`             | Optional | OpenAI API key for AI features           |
| `ANTHROPIC_API_KEY`          | Optional | Anthropic API key for AI features        |
| `SMTP_HOST`                  | Optional | SMTP server for emails                   |
| `SMTP_PORT`                  | Optional | SMTP port (default: 587)                 |
| `SMTP_USER`                  | Optional | SMTP username                            |
| `SMTP_PASSWORD`              | Optional | SMTP password                            |

### Frontend (`frontend/.env.local`)

| Variable                  | Required | Description                   |
|---------------------------|----------|-------------------------------|
| `VITE_API_URL`            | ✅       | Backend API URL               |
| `VITE_SENTRY_DSN`         | Optional | Sentry DSN for frontend       |
| `VITE_SENTRY_ENVIRONMENT` | Optional | Sentry environment tag        |

## 📚 API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register | Register new user |
| POST | /api/auth/login | Login and get tokens |
| GET | /api/projects | List user's projects |
| POST | /api/time/start | Start timer |
| POST | /api/time/stop | Stop running timer |
| GET | /api/reports/dashboard | Get dashboard stats |
| POST | /api/account-requests | Submit account request (public) |
| GET | /api/account-requests | List account requests (admin) |

For complete API documentation, see:
- **Phase 13 - Account Requests**: [PHASE13_ACCOUNT_REQUESTS.md](PHASE13_ACCOUNT_REQUESTS.md)
- **Phase 2 - Staff Management**: [Update3.md](Update3.md)

## 🔒 Security

- JWT-based authentication with access/refresh tokens
- Password hashing with bcrypt
- CORS protection
- SQL injection prevention via SQLAlchemy ORM
- Input validation with Pydantic
- Rate limiting on sensitive endpoints (3 requests/hour for account requests)
- XSS prevention via input sanitization
- Audit logging for all account operations

## 📖 Documentation

Complete documentation is available in the `docs/` folder:

### Getting Started
- **[docs/INSTALLATION.md](docs/INSTALLATION.md)** - First-time setup guide
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide
- **[docs/USER_QUICK_START.md](docs/USER_QUICK_START.md)** - End-user getting started

### Configuration
- **[docs/BRANDING_CUSTOMIZATION.md](docs/BRANDING_CUSTOMIZATION.md)** - White-label customization
- **[docs/EMAIL_CONFIGURATION.md](docs/EMAIL_CONFIGURATION.md)** - SMTP and email setup

### Administration
- **[docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)** - System administration tasks
- **[docs/API.md](docs/API.md)** - API reference documentation

### For Resellers
- **[RESELL_APP.md](RESELL_APP.md)** - Resellability assessment (95% ready)
- **[DEPLOYMENT_RESALE_GUIDE.md](DEPLOYMENT_RESALE_GUIDE.md)** - Detailed deployment guide

### Other Documents
- **[CONTEXT.md](CONTEXT.md)** - Critical deployment rules and context
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with ❤️ for productive teams everywhere

# Test auto-deploy
