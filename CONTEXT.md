# TimeTracker Project Context

> **Last Updated**: December 31, 2025
> **Latest Session Report**: [SESSION_REPORT_DEC_31_2025.md](SESSION_REPORT_DEC_31_2025.md)

---

## 🚀 Quick Start

### To Continue Development
```
Read this file and the latest SESSION_REPORT file, then help me with [your task]
```

### Production Status
| Item | Value |
|------|-------|
| **URL** | https://timetracker.shaemarcus.com |
| **Server** | AWS Lightsail |
| **Path** | `/home/ubuntu/timetracker` (lowercase!) |
| **Docker File** | `docker-compose.prod.yml` (⚠️ NOT docker-compose.yml) |

---

## 📁 Project Architecture

### Tech Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 15
- **Cache**: Redis 7
- **Frontend**: React (Vite) with Tailwind CSS
- **Auth**: JWT with refresh tokens
- **AI**: Gemini (primary), OpenAI (fallback)

### Key Directories
```
backend/
├── app/           # FastAPI app config, main.py
├── routers/       # API endpoints (17+ router files)
├── services/      # Business logic & AI services
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic validation
├── utils/         # Auth, encryption, helpers
└── alembic/       # DB migrations

frontend/
├── src/
│   ├── components/  # React components
│   ├── pages/       # Page components
│   ├── services/    # API clients
│   └── hooks/       # Custom React hooks
```

### Database
- **PostgreSQL 15** with 20+ tables
- Time entries, users, teams, projects, breaks
- AI-specific: `api_keys`, `global_ai_settings`, `user_ai_preferences`

---

## 🔧 Common Commands

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Production Deployment
```bash
# SSH to server
ssh ubuntu@<lightsail-ip>
cd /home/ubuntu/timetracker

# Pull changes
git pull origin master

# Rebuild & deploy
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check health
curl http://localhost:8000/health

# View logs
docker logs timetracker-backend --tail=100
docker logs timetracker-frontend --tail=100
```

---

## ✅ Implemented Features

### Core Features
- User authentication (JWT + refresh)
- Time tracking (entries, breaks, projects)
- Team management
- Admin dashboard
- Role-based access (user, team_lead, admin, super_admin)
- Audit logging
- Export (CSV/Excel)

### AI Features (Phases 0.2 - 5.2)
| Phase | Feature | Status |
|-------|---------|--------|
| 0.2 | AI Feature Toggle System | ✅ |
| 1.1 | Smart Time Entry Description | ✅ |
| 1.2 | Task Categorization | ✅ |
| 2.1 | Time Entry Validation | ✅ |
| 2.2 | Break Optimization | ✅ |
| 3.1 | Daily Summary Generation | ✅ |
| 3.2 | Weekly Pattern Analysis | ✅ |
| 4.1 | Real-time Productivity Alerts | ✅ |
| 4.2 | Daily/Weekly AI Reports | ✅ |
| 5.1 | Semantic Search | ✅ |
| 5.2 | Team Analytics | ✅ |

### AI Endpoints (30 total)
- `/api/ai/settings/*` - Admin AI configuration
- `/api/ai/preferences/*` - User AI preferences
- `/api/ai/assist/*` - Smart descriptions, categorization
- `/api/ai/validate/*` - Entry validation
- `/api/ai/analyze/*` - Pattern analysis
- `/api/ai/generate/*` - Summary generation
- `/api/ai/alerts/*` - Real-time alerts
- `/api/ai/reports/*` - AI-powered reports
- `/api/ai/search/*` - Semantic search
- `/api/ai/team-analytics/*` - Team insights

---

## ⚠️ Important Notes

### Production Deploy Rules
1. **ALWAYS** use `docker-compose.prod.yml` (NOT `docker-compose.yml`)
2. Container names are `timetracker-*` (lowercase)
3. Server path is `/home/ubuntu/timetracker` (lowercase)

### Environment Variables (Production)
Required in `.env`:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - JWT signing key
- `FRONTEND_URL` - CORS origin

Optional:
- `API_KEY_ENCRYPTION_KEY` - For API key encryption (auto-generated if missing)
- `GEMINI_API_KEY` - Fallback if no DB key
- `OPENAI_API_KEY` - Fallback if no DB key

### ML Dependencies (Optional)
```bash
pip install numpy scikit-learn xgboost
```
System degrades gracefully without these.

---

## 📋 Session Reports Index

| Date | Report | Focus |
|------|--------|-------|
| Dec 31, 2025 | [SESSION_REPORT_DEC_31_2025.md](SESSION_REPORT_DEC_31_2025.md) | AI Phases 0.2-5.2, Full deployment |
| Dec 30, 2025 | [SESSION_REPORT_DEC_30_2025.md](SESSION_REPORT_DEC_30_2025.md) | Previous work |
| Dec 29, 2025 | [SESSION_REPORT_DEC_29_2025.md](SESSION_REPORT_DEC_29_2025.md) | Previous work |

---

## 🐛 Known Issues / TODO

- [ ] `API_KEY_ENCRYPTION_KEY` should be set in production for persistent encryption
- [ ] ML packages not installed (optional)
- [ ] Test AI features via Admin UI after adding API keys

---

## 📚 Key Documentation Files

1. **[CONTEXT.md](CONTEXT.md)** - This file - project overview
2. **[PRODUCTION_FIXES_GUIDE.md](PRODUCTION_FIXES_GUIDE.md)** - Deployment guide
3. **[AIupgrade.md](AIupgrade.md)** - AI feature specifications
4. **[README.md](README.md)** - Project readme
5. **Latest SESSION_REPORT** - Detailed session history

---

*Keep this file updated at the end of each session for continuity.*
