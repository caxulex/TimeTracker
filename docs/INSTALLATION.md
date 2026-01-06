# TimeTracker Installation Guide

Complete guide for installing TimeTracker for development or production.

---

## Table of Contents

1. [Development Setup](#development-setup)
2. [Production Setup](#production-setup)
3. [Docker Setup](#docker-setup)
4. [Environment Configuration](#environment-configuration)
5. [Database Setup](#database-setup)
6. [First Run](#first-run)

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### Backend Setup

```bash
# Clone repository
git clone https://github.com/your-repo/timetracker.git
cd timetracker/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit environment variables
nano .env

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8080
```

### Frontend Setup

```bash
# In a new terminal
cd timetracker/frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Start development server
npm run dev
```

### Access Application

- Frontend: http://localhost:5173
- Backend API: http://localhost:8080
- API Docs: http://localhost:8080/docs

---

## Production Setup

For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).

Quick start:

```bash
# Generate secrets
./scripts/generate-secrets.sh --env > .env.production

# Deploy with Docker
./scripts/deploy-sequential.sh
```

---

## Docker Setup

### Development with Docker

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Production with Docker

```bash
# Build and start production stack
docker compose -f docker-compose.prod.yml up -d --build

# For low-RAM servers, use sequential build
./scripts/deploy-sequential.sh
```

### Container Overview

| Container | Port | Purpose |
|-----------|------|---------|
| frontend | 80 | React application |
| backend | 8080 | FastAPI server |
| postgres | 5432 | Database |
| redis | 6379 | Cache/sessions |

---

## Environment Configuration

### Backend Environment Variables

Create `backend/.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://timetracker:password@localhost:5432/time_tracker
DB_PASSWORD=your_secure_password

# Security
SECRET_KEY=your_64_character_secret_key_here
API_KEY_ENCRYPTION_KEY=your_32_character_key_here

# Redis
REDIS_URL=redis://localhost:6379

# Environment
ENVIRONMENT=development
DEBUG=true

# CORS
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
ALLOWED_HOSTS=["localhost","127.0.0.1"]

# Admin Account
FIRST_SUPER_ADMIN_EMAIL=admin@example.com
FIRST_SUPER_ADMIN_PASSWORD=AdminPassword123!
```

### Frontend Environment Variables

Create `frontend/.env.local`:

```env
# API URL
VITE_API_URL=http://localhost:8080/api

# Branding
VITE_APP_NAME=Time Tracker
VITE_COMPANY_NAME=Your Company
VITE_LOGO_URL=/logo.svg
VITE_PRIMARY_COLOR=#2563eb
VITE_SUPPORT_EMAIL=support@example.com
```

### Generate Secrets

```bash
# Generate all secrets at once
./scripts/generate-secrets.sh --env

# Or generate individually
python -c "import secrets; print(secrets.token_urlsafe(64))"  # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"  # API_KEY_ENCRYPTION_KEY
openssl rand -base64 32  # DB_PASSWORD
```

---

## Database Setup

### Create Database (PostgreSQL)

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create user and database
CREATE USER timetracker WITH PASSWORD 'your_password';
CREATE DATABASE time_tracker OWNER timetracker;
GRANT ALL PRIVILEGES ON DATABASE time_tracker TO timetracker;
\q
```

### Run Migrations

```bash
# Using alembic directly
cd backend
alembic upgrade head

# Using Docker
docker compose exec backend alembic upgrade head
```

### Create Initial Admin

The first admin is created automatically on startup using environment variables:

```env
FIRST_SUPER_ADMIN_EMAIL=admin@example.com
FIRST_SUPER_ADMIN_PASSWORD=YourSecurePassword!
```

Or create manually:

```bash
docker compose exec backend python -m scripts.create_superadmin
```

---

## First Run

### 1. Start Services

```bash
# Development
docker compose up -d

# Production
docker compose -f docker-compose.prod.yml up -d
```

### 2. Verify Health

```bash
# Check containers
docker compose ps

# Check backend health
curl http://localhost:8080/health

# Check frontend
curl http://localhost/
```

### 3. Login

1. Open http://localhost:5173 (dev) or https://yourdomain.com (prod)
2. Login with admin credentials
3. **Change your password immediately!**

### 4. Initial Configuration

1. Go to **Admin** → **Settings**
2. Configure:
   - Company information
   - Default work hours
   - Pay period settings
3. Create teams and projects
4. Invite users

---

## Common Issues

### Port Already in Use

```bash
# Find process using port
lsof -i :8080
# Kill process
kill -9 <PID>
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection string
psql postgresql://timetracker:password@localhost:5432/time_tracker
```

### Redis Connection Failed

```bash
# Check Redis is running
redis-cli ping
# Expected: PONG
```

### Frontend Can't Connect to Backend

1. Check VITE_API_URL in frontend/.env.local
2. Verify backend is running on correct port
3. Check CORS settings in backend

---

## Next Steps

After installation:

1. **Configure branding** - See [BRANDING_CUSTOMIZATION.md](BRANDING_CUSTOMIZATION.md)
2. **Set up email** - See [EMAIL_CONFIGURATION.md](EMAIL_CONFIGURATION.md)
3. **Learn admin tasks** - See [ADMIN_GUIDE.md](ADMIN_GUIDE.md)
4. **Train users** - See [USER_QUICK_START.md](USER_QUICK_START.md)

---

**Last Updated:** January 6, 2026
