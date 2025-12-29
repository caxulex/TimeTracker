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

## 4. Automated Deployment Script

Save as `deploy-client.sh`:

```bash
#!/bin/bash

# ============================================
# TimeTracker Client Deployment Script
# Usage: ./deploy-client.sh <domain> <admin_email>
# ============================================

set -e

DOMAIN=$1
ADMIN_EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$ADMIN_EMAIL" ]; then
    echo "Usage: ./deploy-client.sh <domain> <admin_email>"
    echo "Example: ./deploy-client.sh timetracker.acme.com admin@acme.com"
    exit 1
fi

# Generate secure credentials
ADMIN_PASSWORD=$(openssl rand -base64 12)
JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')

echo "🚀 Deploying TimeTracker for $DOMAIN..."
echo ""

# Create deployment directory
DEPLOY_DIR="/opt/timetracker-$DOMAIN"
sudo mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# Clone repository
echo "📦 Cloning repository..."
git clone https://github.com/caxulex/TimeTracker.git .

# Create environment file
echo "⚙️ Creating configuration..."
cat > .env << EOF
# Database
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/timetracker
POSTGRES_PASSWORD=${DB_PASSWORD}

# Redis
REDIS_URL=redis://redis:6379

# Security
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Domain
DOMAIN=${DOMAIN}
VITE_API_URL=https://${DOMAIN}

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
AUTH_RATE_LIMIT_PER_MINUTE=5
EOF

# Deploy
echo "🐳 Starting Docker containers..."
docker compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Create admin user
echo "👤 Creating admin user..."
docker exec time-tracker-backend python -c "
import asyncio
from app.database import async_engine, AsyncSessionLocal
from app.models import User
from app.services.auth_service import auth_service
from sqlalchemy import select

async def create_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == '${ADMIN_EMAIL}'))
        if result.scalar_one_or_none():
            print('Admin user already exists')
            return
        
        hashed = auth_service.hash_password('${ADMIN_PASSWORD}')
        admin = User(
            email='${ADMIN_EMAIL}',
            hashed_password=hashed,
            name='Administrator',
            role='super_admin',
            is_active=True
        )
        db.add(admin)
        await db.commit()
        print('Admin user created successfully')

asyncio.run(create_admin())
"

# Print summary
echo ""
echo "============================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "🌐 URL: https://${DOMAIN}"
echo ""
echo "👤 Admin Credentials:"
echo "   Email: ${ADMIN_EMAIL}"
echo "   Password: ${ADMIN_PASSWORD}"
echo ""
echo "⚠️  IMPORTANT: Save these credentials securely!"
echo "   Change the password after first login."
echo ""
echo "📁 Deployment directory: ${DEPLOY_DIR}"
echo "============================================"
```

**Make executable:**
```bash
chmod +x deploy-client.sh
```

**Usage:**
```bash
./deploy-client.sh timetracker.acme.com admin@acme.com
```

---

## 5. Client Configuration Template

Save as `client-config-template.env`:

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

# Rebuild and restart containers
docker compose -f docker-compose.prod.yml up -d --build

# Run any database migrations
docker exec time-tracker-backend alembic upgrade head
```

### Backup Client Data

```bash
# Backup database
docker exec time-tracker-postgres pg_dump -U postgres timetracker > backup_$(date +%Y%m%d).sql

# Backup entire deployment
tar -czvf timetracker-backup-$(date +%Y%m%d).tar.gz /opt/timetracker-clientdomain.com
```

### Restore from Backup

```bash
# Restore database
cat backup_20251229.sql | docker exec -i time-tracker-postgres psql -U postgres timetracker
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

**Document Version**: 1.0  
**Last Updated**: December 29, 2025  
**Author**: TimeTracker Team
