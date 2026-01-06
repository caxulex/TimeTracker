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
   - Default Admin: admin@timetracker.com / admin123

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

**Test Coverage:**
- ✅ Authentication (register, login, tokens)
- ✅ Projects (CRUD, permissions)
- ✅ Time Entries (create, start/stop, update)
- ✅ Teams (CRUD, membership)
- ✅ Reports (dashboard, weekly, export)

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
