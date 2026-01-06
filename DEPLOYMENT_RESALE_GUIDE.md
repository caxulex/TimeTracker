# TimeTracker Deployment Assessment for Resale
**Guide for Deploying TimeTracker to New Business Clients**

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Deployment Difficulty** | Medium |
| **Time per Deployment** | 1-2 hours (manual) / 15 min (automated) |
| **Server Cost** | $5-20/month per client |
| **Technical Skill Required** | Basic Linux/Docker knowledge |

---

## 1. Current Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    VPS (AWS/DO/etc)                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Docker Compose                      │   │
│  │  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │  Frontend   │  │  Backend    │              │   │
│  │  │  (nginx)    │  │  (FastAPI)  │              │   │
│  │  └─────────────┘  └─────────────┘              │   │
│  │  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │ PostgreSQL  │  │   Redis     │              │   │
│  │  └─────────────┘  └─────────────┘              │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Caddy (SSL/Proxy)                   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | React + Vite + nginx | User interface |
| Backend | FastAPI + Python 3.11 | API server |
| Database | PostgreSQL 15 | Data persistence |
| Cache | Redis 7 | Session & caching |
| Proxy | Caddy | SSL termination & routing |

---

## 2. Deployment Difficulty Breakdown

| Aspect | Difficulty | Time | Notes |
|--------|------------|------|-------|
| Server setup | Easy | 15 min | Any VPS with Docker works |
| Docker deployment | Easy | 10 min | Already containerized |
| SSL certificates | Easy | Auto | Caddy handles automatically |
| Database setup | Easy | 5 min | PostgreSQL in Docker |
| Configuration | Medium | 15 min | Environment variables |
| DNS setup | Easy | 5 min | Point domain to server IP |
| Initial data | Easy | 5 min | Seed script creates admin |
| **Total** | **Medium** | **~1 hour** | Per deployment |

---

## 3. Manual Deployment Steps

### Step 1: Server Setup (15 min)

**Option A: AWS Lightsail ($5-20/month)**
```bash
# Create Ubuntu 24.04 instance
# Minimum: 1GB RAM, 1 vCPU, 40GB SSD
```

**Option B: DigitalOcean Droplet ($6-24/month)**
```bash
# Create Ubuntu 24.04 droplet
# Minimum: 1GB RAM, 1 vCPU
```

**Option C: Any VPS with Docker support**

### Step 2: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### Step 3: Clone Repository

```bash
# Clone the repository
git clone https://github.com/caxulex/TimeTracker.git
cd TimeTracker
```

### Step 4: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Required Environment Variables:**

```env
# Database
DATABASE_URL=postgresql://postgres:YOUR_SECURE_PASSWORD@db:5432/timetracker
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# Redis
REDIS_URL=redis://redis:6379

# Security (MUST be unique per client!)
JWT_SECRET_KEY=GENERATE_UNIQUE_64_CHAR_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Domain
DOMAIN=client-domain.com
VITE_API_URL=https://client-domain.com

# Admin (for initial setup)
ADMIN_EMAIL=admin@client-domain.com
ADMIN_PASSWORD=SecurePassword123!
```

**Generate secure secrets:**
```bash
# Generate JWT secret
openssl rand -base64 64

# Generate database password
openssl rand -base64 32
```

### Step 5: DNS Configuration

Point client's domain to server IP:

| Record Type | Name | Value |
|-------------|------|-------|
| A | @ | SERVER_IP |
| A | www | SERVER_IP |

### Step 6: Deploy

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Step 7: Create Admin User

```bash
docker exec time-tracker-backend python -m scripts.create_superadmin
```

### Step 8: Verify Deployment

1. Visit `https://client-domain.com`
2. Login with admin credentials
3. Create teams, projects, and users
4. Test timer functionality

---

## 4. Automated Deployment Scripts

TimeTracker includes production-ready deployment scripts in the `scripts/` directory:

### Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `deploy-client.sh` | Full client deployment | `./scripts/deploy-client.sh <domain> <email>` |
| `deploy-sequential.sh` | Safe build (low RAM servers) | `./scripts/deploy-sequential.sh` |
| `generate-secrets.sh` | Generate secure credentials | `./scripts/generate-secrets.sh --env` |
| `backup-client.sh` | Create full backups | `./scripts/backup-client.sh` |
| `restore-backup.sh` | Disaster recovery | `./scripts/restore-backup.sh <file>` |
| `health-check.sh` | Monitor system health | `./scripts/health-check.sh` |

### Quick Deployment (Recommended)

```bash
# 1. Generate secrets
./scripts/generate-secrets.sh --env > backend/.env

# 2. Edit configuration
nano backend/.env  # Set domain, admin email, etc.

# 3. Deploy (use sequential build for <2GB RAM servers)
./scripts/deploy-sequential.sh
```

### Full Deployment Script

The `deploy-client.sh` script handles everything automatically:

```bash
# Usage
./scripts/deploy-client.sh <domain> <admin_email>

# Example
./scripts/deploy-client.sh timetracker.acme.com admin@acme.com
```

This script will:
1. ✅ Generate secure secrets (JWT, DB password)
2. ✅ Create environment configuration
3. ✅ Build and deploy containers
4. ✅ Set up SSL via Caddy
5. ✅ Create admin user
6. ✅ Print credentials to save

### Health Monitoring

```bash
# Full system check
./scripts/health-check.sh

# Quick API check only
./scripts/health-check.sh --quick

# JSON output for monitoring systems
./scripts/health-check.sh --json

# Continuous monitoring (every 30s)
./scripts/health-check.sh --watch
```

### Backup & Recovery

```bash
# Create backup
./scripts/backup-client.sh

# List available backups
./scripts/restore-backup.sh --list

# Verify backup integrity
./scripts/restore-backup.sh --verify <backup-file>

# Restore (full or database only)
./scripts/restore-backup.sh <backup-file>
./scripts/restore-backup.sh --db-only <backup-file>
```

---

## 5. Client Configuration Template

Use the template in `clients/template/.env.template` or generate with:

```env
# ============================================
# TimeTracker Client Configuration
# Client: [CLIENT_NAME]
# Domain: [CLIENT_DOMAIN]
# ============================================

# Database
DATABASE_URL=postgresql://postgres:[DB_PASSWORD]@db:5432/timetracker
POSTGRES_PASSWORD=[DB_PASSWORD]

# Redis
REDIS_URL=redis://redis:6379

# Security (UNIQUE PER CLIENT!)
JWT_SECRET_KEY=[UNIQUE_JWT_SECRET]
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Domain Configuration
DOMAIN=[CLIENT_DOMAIN]
VITE_API_URL=https://[CLIENT_DOMAIN]

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
AUTH_RATE_LIMIT_PER_MINUTE=5

# Optional: Email Configuration
# SMTP_HOST=smtp.example.com
# SMTP_PORT=587
# SMTP_USER=notifications@[CLIENT_DOMAIN]
# SMTP_PASSWORD=[SMTP_PASSWORD]
# SMTP_FROM=TimeTracker <notifications@[CLIENT_DOMAIN]>
```

---

## 6. Deployment Options Comparison

### Option A: Separate Deployment per Client (Current)

| Pros | Cons |
|------|------|
| ✅ Complete data isolation | ❌ Higher infrastructure cost |
| ✅ Independent updates | ❌ More maintenance overhead |
| ✅ Custom configurations | ❌ Slower to deploy at scale |
| ✅ Client owns their data | |

**Best for**: Enterprise clients, data-sensitive industries, clients needing customization

### Option B: Multi-Tenant (Single Deployment)

| Pros | Cons |
|------|------|
| ✅ Lower infrastructure cost | ❌ Shared database (logical isolation) |
| ✅ Single deployment to maintain | ❌ More complex to build |
| ✅ Faster client onboarding | ❌ Updates affect all clients |
| ✅ Better resource utilization | |

**Best for**: SaaS model, many small clients, cost-sensitive deployments

**Would require**:
- Add `organization_id` to all models
- Organization management UI
- Subdomain routing
- ~2-3 weeks development

### Option C: Managed Platform (Railway, Render, etc.)

| Pros | Cons |
|------|------|
| ✅ One-click deployments | ❌ Higher per-client cost |
| ✅ Auto-scaling | ❌ Less control |
| ✅ Built-in monitoring | ❌ Platform lock-in |
| ✅ Automatic SSL | |

**Best for**: Quick MVP, clients who want managed infrastructure

---

## 7. Pricing Recommendations

### Infrastructure Costs per Client

| Tier | Specs | Monthly Cost | Best For |
|------|-------|--------------|----------|
| Starter | 1GB RAM, 1 vCPU | $5-6 | Small teams (<10 users) |
| Standard | 2GB RAM, 1 vCPU | $12-15 | Medium teams (10-50 users) |
| Professional | 4GB RAM, 2 vCPU | $24-30 | Large teams (50-200 users) |
| Enterprise | 8GB+ RAM, 4+ vCPU | $50+ | Enterprise (200+ users) |

### Suggested Client Pricing

| Tier | Your Cost | Suggested Price | Margin |
|------|-----------|-----------------|--------|
| Starter | $6/mo | $29/mo | $23 (79%) |
| Standard | $15/mo | $79/mo | $64 (81%) |
| Professional | $30/mo | $149/mo | $119 (80%) |
| Enterprise | $50/mo | $299/mo | $249 (83%) |

---

## 8. Post-Deployment Checklist

### For Each New Client:

- [ ] Server provisioned and accessible
- [ ] Docker and Docker Compose installed
- [ ] Repository cloned
- [ ] Environment variables configured
- [ ] Unique JWT secret generated
- [ ] DNS pointing to server
- [ ] SSL certificate active (Caddy auto-generates)
- [ ] All containers running
- [ ] Admin user created
- [ ] Client can login successfully
- [ ] Timer functionality working
- [ ] WebSocket real-time updates working
- [ ] Backup strategy configured
- [ ] Monitoring set up (optional)

### Documentation to Provide Client:

- [ ] Login credentials
- [ ] User guide / quick start
- [ ] Support contact information
- [ ] SLA terms (if applicable)

---

## 9. Maintenance & Updates

### Updating a Client's Deployment

```bash
cd /opt/timetracker-clientdomain.com

# Pull latest changes
git pull origin master

# Safe rebuild (prevents RAM crashes on small servers)
./scripts/deploy-sequential.sh

# Run any database migrations
docker exec timetracker-backend alembic upgrade head
```

### Backup Client Data

Use the provided backup script:

```bash
# Full backup (database + uploads + config)
./scripts/backup-client.sh

# Backup to specific directory
./scripts/backup-client.sh --output /backups/

# With --restore flag creates timestamped restore point
./scripts/backup-client.sh --restore
```

Backups are saved to `backups/` directory by default.

### Restore from Backup

```bash
# List available backups
./scripts/restore-backup.sh --list

# Verify backup before restore
./scripts/restore-backup.sh --verify backup_20260106.tar.gz

# Full restore
./scripts/restore-backup.sh backup_20260106.tar.gz

# Database only restore
./scripts/restore-backup.sh --db-only backup_20260106.sql.gz

# Dry run (preview what would happen)
./scripts/restore-backup.sh --dry-run backup_20260106.tar.gz
```

### Health Monitoring

```bash
# Quick health check
./scripts/health-check.sh --quick

# Full system check (containers, DB, Redis, disk, logs)
./scripts/health-check.sh

# JSON output for monitoring integration
./scripts/health-check.sh --json

# Continuous monitoring
./scripts/health-check.sh --watch 60  # Check every 60 seconds
```

---

## 10. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Containers not starting | Check logs: `docker compose logs` |
| SSL not working | Verify DNS propagation, check Caddy logs |
| Database connection failed | Verify DATABASE_URL, check postgres container |
| 502 Bad Gateway | Backend container may be down, restart it |
| WebSocket not connecting | Check nginx/Caddy WebSocket proxy config |

### Useful Commands

```bash
# View all container logs
docker compose logs -f

# Restart specific service
docker compose restart backend

# Enter container shell
docker exec -it time-tracker-backend bash

# Check database connection
docker exec -it time-tracker-postgres psql -U postgres -d timetracker

# Check Redis
docker exec -it time-tracker-redis redis-cli ping
```

---

## 11. Security Checklist

For each deployment, ensure:

- [ ] Unique JWT_SECRET_KEY (never reuse!)
- [ ] Strong database password
- [ ] SSL/HTTPS enabled
- [ ] Firewall configured (only ports 80, 443, 22)
- [ ] Regular security updates
- [ ] Database backups encrypted
- [ ] Admin password changed from default

---

## 12. Global Update Repository Strategy

When selling to multiple clients, you need a centralized way to push updates while keeping custom builds isolated.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     YOUR CENTRAL REPOSITORY                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  GitHub Repo    →    GHCR Images    →    Version Tags       │    │
│  │  (Source Code)       (Built Images)      (Release Control)   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ Pull Updates
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
   │  Client A   │        │  Client B   │        │  Client C   │
   │  Standard   │        │  Standard   │        │  CUSTOM     │
   │  :latest    │        │  :latest    │        │  :v2.1.0    │
   │  (Auto)     │        │  (Auto)     │        │  (Frozen)   │
   └─────────────┘        └─────────────┘        └─────────────┘
        │                       │                       │
   Auto-updates            Auto-updates           Manual updates
   via Watchtower          via Watchtower         (approval req)
```

### Image Tagging Strategy

| Tag | Purpose | Who Uses It |
|-----|---------|-------------|
| `:latest` | Current stable release | Standard clients (auto-update) |
| `:v2.1.0` | Specific version | Custom/Enterprise clients (frozen) |
| `:develop` | Pre-release testing | Internal QA only |
| `:client-acme` | Client-specific build | Heavily customized clients |

### Client Tier Update Policies

| Tier | Image Tag | Update Method | Customization |
|------|-----------|---------------|---------------|
| **Standard** | `:latest` | Automatic (Watchtower) | None - core product only |
| **Professional** | `:latest` | Scheduled (weekly) | Config-level only |
| **Enterprise** | `:v2.x.x` | Manual approval | Full custom features |
| **Custom Build** | `:client-name` | Manual only | Separate branch |

---

## 13. Version Control & Release Management

### Branch Strategy

```
main (stable)
  │
  ├── develop (integration)
  │     │
  │     ├── feature/new-reports
  │     ├── feature/api-v2
  │     └── fix/timer-bug
  │
  ├── release/v2.1.0 (release candidate)
  │
  └── client/acme-custom (client-specific)
```

### Release Workflow

```bash
# 1. Create release branch from develop
git checkout develop
git checkout -b release/v2.1.0

# 2. Final testing and bug fixes on release branch
# ... testing ...

# 3. Merge to main and tag
git checkout main
git merge release/v2.1.0
git tag -a v2.1.0 -m "Release v2.1.0 - New reporting features"
git push origin main --tags

# 4. Build and push Docker images
docker build -t ghcr.io/yourcompany/timetracker-backend:v2.1.0 ./backend
docker build -t ghcr.io/yourcompany/timetracker-backend:latest ./backend
docker push ghcr.io/yourcompany/timetracker-backend:v2.1.0
docker push ghcr.io/yourcompany/timetracker-backend:latest

# 5. Standard clients auto-update via Watchtower
# 6. Enterprise clients notified of new version available
```

### Semantic Versioning

| Version Change | When | Example |
|----------------|------|---------|
| **Major** (X.0.0) | Breaking changes, major features | v2.0.0 → v3.0.0 |
| **Minor** (0.X.0) | New features, backward compatible | v2.1.0 → v2.2.0 |
| **Patch** (0.0.X) | Bug fixes, security patches | v2.1.0 → v2.1.1 |

---

## 14. Automatic Updates with Watchtower

### Setup Watchtower for Standard Clients

Add to client's `docker-compose.prod.yml`:

```yaml
services:
  # ... existing services ...

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      # Check for updates daily at 3 AM
      - WATCHTOWER_SCHEDULE=0 0 3 * * *
      # Only update specific containers
      - WATCHTOWER_LABEL_ENABLE=true
      # Cleanup old images
      - WATCHTOWER_CLEANUP=true
      # Notification (optional)
      - WATCHTOWER_NOTIFICATIONS=email
      - WATCHTOWER_NOTIFICATION_EMAIL_FROM=updates@yourcompany.com
      - WATCHTOWER_NOTIFICATION_EMAIL_TO=admin@client.com
    labels:
      - "com.centurylinklabs.watchtower.enable=false"
```

### Label Containers for Auto-Update

```yaml
services:
  backend:
    image: ghcr.io/yourcompany/timetracker-backend:latest
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
    # ...

  frontend:
    image: ghcr.io/yourcompany/timetracker-frontend:latest
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
    # ...

  # Database should NOT auto-update
  db:
    image: postgres:15
    labels:
      - "com.centurylinklabs.watchtower.enable=false"
    # ...
```

### Update Notification Script

Save as `notify-update.sh` on your build server:

```bash
#!/bin/bash
# Run after pushing new images

VERSION=$1
CHANGELOG=$2

# List of client webhooks/emails
CLIENTS=(
  "https://hooks.slack.com/services/CLIENT_A_WEBHOOK"
  "https://hooks.slack.com/services/CLIENT_B_WEBHOOK"
)

for WEBHOOK in "${CLIENTS[@]}"; do
  curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"🚀 TimeTracker $VERSION released!\n$CHANGELOG\nAuto-update will occur at 3 AM.\"}" \
    "$WEBHOOK"
done
```

---

## 15. Client Instance Registry

Track all deployments in a central registry:

### Client Registry Template (clients.json)

```json
{
  "clients": [
    {
      "id": "client-001",
      "name": "Acme Corp",
      "domain": "timetracker.acme.com",
      "tier": "standard",
      "version": "latest",
      "auto_update": true,
      "deployed_at": "2025-01-15",
      "server_ip": "192.168.1.100",
      "server_provider": "aws-lightsail",
      "monthly_cost": 12,
      "monthly_price": 79,
      "contact_email": "admin@acme.com",
      "features": {
        "payroll": true,
        "reports_export": true,
        "api_access": false,
        "custom_branding": false
      },
      "notes": "Standard deployment, no customizations"
    },
    {
      "id": "client-002",
      "name": "TechStart Inc",
      "domain": "time.techstart.io",
      "tier": "enterprise",
      "version": "v2.1.0",
      "auto_update": false,
      "deployed_at": "2025-02-01",
      "server_ip": "192.168.1.101",
      "server_provider": "digitalocean",
      "monthly_cost": 50,
      "monthly_price": 299,
      "contact_email": "it@techstart.io",
      "features": {
        "payroll": true,
        "reports_export": true,
        "api_access": true,
        "custom_branding": true,
        "sso_integration": true
      },
      "custom_branch": "client/techstart",
      "notes": "Custom SSO integration with Okta"
    }
  ]
}
```

### Client Management Dashboard (Future)

Consider building a simple admin dashboard to:
- View all client deployments
- Monitor health/status of each instance
- Trigger manual updates
- View revenue/costs per client
- Manage feature flags

---

## 16. Feature Flags for Per-Client Configuration

### Environment-Based Feature Flags

Add to client's `.env`:

```env
# Feature Flags
FEATURE_PAYROLL_ENABLED=true
FEATURE_REPORTS_EXPORT=true
FEATURE_API_ACCESS=false
FEATURE_CUSTOM_BRANDING=false
FEATURE_SSO_ENABLED=false
FEATURE_ADVANCED_ANALYTICS=false
```

### Backend Feature Flag Check

```python
# backend/app/config.py
class Settings:
    # ... existing settings ...
    
    # Feature Flags
    FEATURE_PAYROLL_ENABLED: bool = True
    FEATURE_REPORTS_EXPORT: bool = True
    FEATURE_API_ACCESS: bool = False
    FEATURE_CUSTOM_BRANDING: bool = False
    FEATURE_SSO_ENABLED: bool = False

# backend/app/dependencies.py
from app.config import settings

def require_feature(feature_name: str):
    """Dependency to check if feature is enabled"""
    def check_feature():
        feature_enabled = getattr(settings, f"FEATURE_{feature_name.upper()}_ENABLED", False)
        if not feature_enabled:
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature_name}' is not enabled for this instance"
            )
        return True
    return Depends(check_feature)

# Usage in router
@router.get("/api/payroll/report")
async def get_payroll_report(
    _: bool = require_feature("payroll"),
    db: AsyncSession = Depends(get_db)
):
    # ... endpoint logic ...
```

### Frontend Feature Flag Check

```typescript
// frontend/src/config/features.ts
export const features = {
  payroll: import.meta.env.VITE_FEATURE_PAYROLL === 'true',
  reportsExport: import.meta.env.VITE_FEATURE_REPORTS_EXPORT === 'true',
  apiAccess: import.meta.env.VITE_FEATURE_API_ACCESS === 'true',
  customBranding: import.meta.env.VITE_FEATURE_CUSTOM_BRANDING === 'true',
};

// Usage in component
{features.payroll && <PayrollSection />}
```

---

## 17. Handling Custom Client Builds

### When to Create a Custom Branch

| Scenario | Solution |
|----------|----------|
| Config changes only | Environment variables |
| Logo/branding changes | Feature flag + assets |
| Minor UI tweaks | Feature flag |
| New feature for one client | Custom branch |
| Major workflow changes | Custom branch |
| Third-party integration | Custom branch |

### Custom Branch Workflow

```bash
# Create client-specific branch from latest release
git checkout v2.1.0
git checkout -b client/acme-custom

# Make client-specific changes
# ... develop custom features ...

# Commit and push
git add .
git commit -m "[ACME] Add custom PTO tracking feature"
git push origin client/acme-custom

# Build client-specific image
docker build -t ghcr.io/yourcompany/timetracker-backend:client-acme ./backend
docker push ghcr.io/yourcompany/timetracker-backend:client-acme

# Deploy to client
# In client's docker-compose.yml, use:
# image: ghcr.io/yourcompany/timetracker-backend:client-acme
```

### Merging Core Updates to Custom Branches

```bash
# When new version released, merge to custom branch
git checkout client/acme-custom
git merge v2.2.0

# Resolve any conflicts
# Test thoroughly
# Rebuild and deploy client-specific image
```

---

## 18. Rollback Strategy

### Quick Rollback for Standard Clients

```bash
# SSH into client server
ssh client-server

# Roll back to previous version
cd /opt/timetracker-client.com

# Update docker-compose to use specific version
# Change: image: ghcr.io/yourcompany/timetracker-backend:latest
# To:     image: ghcr.io/yourcompany/timetracker-backend:v2.0.9

docker compose pull
docker compose up -d
```

### Automated Rollback Script

```bash
#!/bin/bash
# rollback.sh <version>

VERSION=${1:-"v2.0.9"}

echo "🔄 Rolling back to $VERSION..."

# Stop watchtower temporarily
docker stop watchtower

# Update images
docker compose pull backend frontend
docker compose up -d backend frontend

echo "✅ Rolled back to $VERSION"
echo "⚠️  Remember to restart watchtower when ready for updates"
```

---

**Document Version**: 1.1  
**Last Updated**: December 29, 2025  
**Author**: TimeTracker Team
