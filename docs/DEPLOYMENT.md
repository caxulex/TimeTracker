# TimeTracker Deployment Guide

Quick reference guide for deploying TimeTracker to production.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Deploy (Automated)](#quick-deploy-automated)
3. [Manual Deploy](#manual-deploy)
4. [Configuration](#configuration)
5. [SSL Setup](#ssl-setup)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 1 GB | 2 GB |
| CPU | 1 vCPU | 2 vCPU |
| Storage | 20 GB SSD | 40 GB SSD |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 |

### Software Requirements

- Docker 24.0+
- Docker Compose 2.0+
- Git

### Network Requirements

- Domain name pointing to server IP
- Ports 80 and 443 open
- SSH access (port 22)

---

## Quick Deploy (Automated)

Use the deployment scripts for fastest setup:

```bash
# 1. Clone repository
git clone https://github.com/your-repo/timetracker.git
cd timetracker

# 2. Generate secrets
./scripts/generate-secrets.sh --env > .env.production

# 3. Deploy
./scripts/deploy-client.sh CLIENT_NAME yourdomain.com
```

The script handles:
- Docker installation
- SSL certificate generation
- Database setup
- Initial admin creation

---

## Manual Deploy

### Step 1: Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify
docker --version
docker compose version
```

### Step 2: Clone and Configure

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/your-repo/timetracker.git
cd timetracker

# Copy environment template
cp clients/template/.env.template .env.production

# Generate secrets
./scripts/generate-secrets.sh --env >> .env.production

# Edit configuration
nano .env.production
```

### Step 3: Build and Deploy

⚠️ **IMPORTANT:** On servers with limited RAM (≤2GB), use sequential builds!

```bash
# For low-RAM servers (RECOMMENDED)
chmod +x scripts/deploy-sequential.sh
./scripts/deploy-sequential.sh

# For high-RAM servers (4GB+)
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 4: Run Migrations

```bash
docker compose exec backend alembic upgrade head
```

### Step 5: Create Admin User

```bash
docker compose exec backend python -m scripts.create_superadmin
```

---

## Configuration

### Required Environment Variables

```env
# Security (GENERATE UNIQUE VALUES!)
SECRET_KEY=your_64_char_secret_key
DB_PASSWORD=your_32_char_db_password
API_KEY_ENCRYPTION_KEY=your_32_char_encryption_key

# Database
DATABASE_URL=postgresql+asyncpg://timetracker:${DB_PASSWORD}@postgres:5432/time_tracker

# Domain
ALLOWED_ORIGINS=["https://yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com","localhost"]

# Admin Account
FIRST_SUPER_ADMIN_EMAIL=admin@yourdomain.com
FIRST_SUPER_ADMIN_PASSWORD=ChangeThisImmediately!
```

### Branding Variables

```env
VITE_APP_NAME=Your App Name
VITE_COMPANY_NAME=Your Company
VITE_LOGO_URL=/logo.svg
VITE_PRIMARY_COLOR=#2563eb
VITE_SUPPORT_EMAIL=support@yourdomain.com
```

### Email Configuration (Optional)

```env
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=your_smtp_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Your App Name
```

See `docs/EMAIL_CONFIGURATION.md` for detailed SMTP setup.

---

## SSL Setup

### Option A: Caddy (Automatic)

Caddy automatically obtains and renews SSL certificates:

```bash
# Caddyfile
yourdomain.com {
    reverse_proxy frontend:80
    handle_path /api/* {
        reverse_proxy backend:8080
    }
}
```

### Option B: Let's Encrypt (Manual)

```bash
# Install certbot
sudo apt install certbot

# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com

# Auto-renewal (add to crontab)
0 0 1 * * certbot renew --quiet
```

---

## Verification

### Check Container Status

```bash
docker compose ps
# All 4 containers should be "Up"
```

### Health Checks

```bash
# Backend health
curl http://localhost:8080/health
# Expected: {"status": "healthy"}

# Frontend
curl http://localhost/
# Expected: HTML response
```

### Test Login

1. Navigate to `https://yourdomain.com`
2. Login with admin credentials
3. Verify dashboard loads
4. Test timer start/stop

---

## Troubleshooting

### Container Won't Start

```bash
# View logs
docker compose logs backend
docker compose logs frontend

# Restart services
docker compose restart
```

### Database Connection Failed

```bash
# Check PostgreSQL
docker compose exec postgres psql -U timetracker -d time_tracker -c "SELECT 1"

# Verify DATABASE_URL matches credentials
```

### Build Crashes (Out of Memory)

```bash
# Use sequential build script
./scripts/deploy-sequential.sh

# Or increase swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### SSL Certificate Issues

```bash
# Check Caddy logs
docker compose logs caddy

# Verify DNS points to correct IP
dig yourdomain.com
```

### Permission Denied

```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Fix file permissions
sudo chown -R $USER:$USER /opt/timetracker
```

---

## Backup & Recovery

### Create Backup

```bash
./scripts/backup-client.sh CLIENT_NAME
```

### Manual Backup

```bash
# Database
docker compose exec postgres pg_dump -U timetracker time_tracker > backup.sql

# Files
tar -czf uploads.tar.gz uploads/
```

### Restore

```bash
# Database
docker compose exec -T postgres psql -U timetracker time_tracker < backup.sql

# Files
tar -xzf uploads.tar.gz
```

---

## Related Documentation

- [DEPLOYMENT_RESALE_GUIDE.md](../DEPLOYMENT_RESALE_GUIDE.md) - Full deployment assessment
- [BRANDING_CUSTOMIZATION.md](BRANDING_CUSTOMIZATION.md) - White-label customization
- [EMAIL_CONFIGURATION.md](EMAIL_CONFIGURATION.md) - SMTP setup
- [ADMIN_GUIDE.md](ADMIN_GUIDE.md) - Administration tasks
- [CONTEXT.md](../CONTEXT.md) - Critical deployment rules

---

**Last Updated:** January 6, 2026
