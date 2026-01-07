

> **Last Updated**: January 7, 2026
> **Latest Session Report**: [SESSION_REPORT_JAN_7_2026_TESTING.md](SESSION_REPORT_JAN_7_2026_TESTING.md)

---

## 🚀 Quick Start

### To Continue Development
```
Read CONTEXT.md, AIupgrade.md, PRODUCTION_FIXES_GUIDE.md, and the latest SESSION_REPORT file, then help me with [your task]
```

### Essential Reading Order
1. **CONTEXT.md** (this file) - Project overview
2. **AIupgrade.md** - AI feature specifications and phases
3. **PRODUCTION_FIXES_GUIDE.md** - ⚠️ MANDATORY before any changes
4. **Latest SESSION_REPORT** - What was done last session

### Production Status
| Item | Value |
|------|-------|
| **URL** | https://timetracker.shaemarcus.com |
| **Server** | AWS Lightsail |
| **Server IP** | `100.52.110.180` (use browser SSH from AWS Console) |
| **Path** | `/home/ubuntu/timetracker` (lowercase!) |
| **Docker File** | `docker-compose.prod.yml` (⚠️ NOT docker-compose.yml) |

### 🚀 How to Deploy (Browser SSH)
1. Go to **AWS Lightsail Console**: https://lightsail.aws.amazon.com/
2. Click on the **TimeTracker** instance
3. Click **"Connect using SSH"** (opens terminal in browser)
4. Run these commands:
   ```bash
   cd ~/timetracker
   git pull origin master
   ./scripts/deploy-sequential.sh
   ```
5. Wait ~5-7 minutes for sequential build
6. Verify: `curl http://localhost:8000/health`

> ⚠️ **NEVER** use `docker compose up -d --build` - it crashes the 1GB RAM server!

### ⚠️ Before Making ANY Changes
> **READ [PRODUCTION_FIXES_GUIDE.md](PRODUCTION_FIXES_GUIDE.md) FIRST!**
> 
> This guide contains critical lessons learned from breaking production on Dec 30, 2025:
> - Container naming conventions
> - Port mappings that CANNOT be changed
> - ALLOWED_HOSTS requirements
> - Auth state management rules
> - Health check configurations
> - Emergency recovery procedures
> 
> **Skipping this guide WILL break the application.**

### 🚨 CRITICAL: Server Resource Limits
> **⛔ THE SERVER IS EXTREMELY LIMITED - READ THIS CAREFULLY!**
> 
> **DANGEROUS commands that WILL CRASH the server:**
> - ❌ `docker compose build --no-cache` - NEVER USE
> - ❌ `docker compose up -d --build` - TOO HEAVY, CRASHES SERVER
> - ❌ Building both containers simultaneously
> 
> ### ✅ RECOMMENDED: Sequential Build Deployment
> **Use the sequential build script that builds ONE container at a time:**
> ```bash
> cd ~/timetracker
> git pull origin master
> chmod +x scripts/deploy-sequential.sh
> ./scripts/deploy-sequential.sh
> ```
> 
> **What the script does (in order):**
> 1. `docker system prune -f` - Frees memory
> 2. Builds **backend** first (~130s)
> 3. `docker builder prune -f` - Clears cache, frees RAM
> 4. Builds **frontend** (~70s) - gets all the freed memory
> 5. Restarts all containers
> 6. Final cleanup
> 
> **This was tested on Jan 5, 2026 and completed successfully without crashing!**
> 
> ### Alternative: No-code-change deployment
> If no code changes require rebuild:
> ```bash
> cd ~/timetracker
> git pull origin master
> docker compose -f docker-compose.prod.yml up -d
> ```
> 
> ### Manual Sequential Build (if script fails)
> ```bash
> cd ~/timetracker
> git pull origin master
> docker system prune -f
> docker compose -f docker-compose.prod.yml build backend
> docker builder prune -f
> docker compose -f docker-compose.prod.yml build frontend
> docker compose -f docker-compose.prod.yml down
> docker compose -f docker-compose.prod.yml up -d
> ```
> 
> **If server becomes unresponsive:**
> 1. Wait 10-15 minutes for recovery, OR
> 2. Reboot from AWS Lightsail Console
> 3. After reboot: `docker compose -f docker-compose.prod.yml up -d`
> 
> **🔴 AI ASSISTANTS: NEVER suggest `--build` flag without explicit user approval!**

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
# Option 1: Browser SSH (Recommended - no local key needed)
# 1. Go to AWS Lightsail Console: https://lightsail.aws.amazon.com/
# 2. Click TimeTracker instance → "Connect using SSH"
# 3. Run the commands below in the browser terminal

# Option 2: Local SSH (requires .pem key)
ssh -i ~/Downloads/LightsailDefaultKey-us-east-1.pem ubuntu@100.52.110.180

# Deploy commands (run on server) - USE SEQUENTIAL BUILD!
cd ~/timetracker
git pull origin master
./scripts/deploy-sequential.sh

# Or manual sequential (if script fails):
# docker compose -f docker-compose.prod.yml build backend
# docker compose -f docker-compose.prod.yml build frontend
# docker compose -f docker-compose.prod.yml down
# docker compose -f docker-compose.prod.yml up -d

# Run migrations (if needed)
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
| Jan 7, 2026 | [SESSION_REPORT_JAN_7_2026_TESTING.md](SESSION_REPORT_JAN_7_2026_TESTING.md) | Phase 7: Testing Complete |
| Jan 6, 2026 | [SESSION_REPORT_JAN_6_2026.md](SESSION_REPORT_JAN_6_2026.md) | Resellability: Branding, Email, Docs |
| Jan 5, 2026 | [SESSION_REPORT_JAN_5_2026.md](SESSION_REPORT_JAN_5_2026.md) | Resellability Phase 1 |
| Dec 31, 2025 | [SESSION_REPORT_DEC_31_2025.md](SESSION_REPORT_DEC_31_2025.md) | AI Phases 0.2-5.2, Full deployment |
| Dec 30, 2025 | [SESSION_REPORT_DEC_30_2025.md](SESSION_REPORT_DEC_30_2025.md) | Previous work |

---

## 🐛 Known Issues / TODO

- [ ] `API_KEY_ENCRYPTION_KEY` should be set in production for persistent encryption
- [ ] ML packages not installed (optional)
- [ ] Test AI features via Admin UI after adding API keys

---

## 📚 Key Documentation Files

1. **[CONTEXT.md](CONTEXT.md)** - This file - project overview
2. **[AIupgrade.md](AIupgrade.md)** - AI feature specifications (Phases 0.2-5.2)
3. **[PRODUCTION_FIXES_GUIDE.md](PRODUCTION_FIXES_GUIDE.md)** - ⚠️ MANDATORY deployment guide
4. **[README.md](README.md)** - Project readme
5. **[docs/](docs/)** - Full documentation suite:
   - [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment
   - [INSTALLATION.md](docs/INSTALLATION.md) - Setup guide
   - [BRANDING_CUSTOMIZATION.md](docs/BRANDING_CUSTOMIZATION.md) - White-label
   - [EMAIL_CONFIGURATION.md](docs/EMAIL_CONFIGURATION.md) - SMTP setup
6. **Latest SESSION_REPORT** - Detailed session history

### 🤖 AI Assistant Instructions
> **When starting a new session, ALWAYS read these files first:**
> 1. `CONTEXT.md` - Understand the project
> 2. `AIupgrade.md` - Know the AI features and phases
> 3. `PRODUCTION_FIXES_GUIDE.md` - Avoid breaking production
> 4. The most recent `SESSION_REPORT_*.md` - Continue where we left off

---

*Keep this file updated at the end of each session for continuity.*
