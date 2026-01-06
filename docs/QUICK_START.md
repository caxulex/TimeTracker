# TimeTracker Quick Start Guide
**Get TimeTracker running in 5 minutes**

---

## Prerequisites

- Docker & Docker Compose installed
- Domain name pointed to your server IP
- SSH access to server

---

## 5-Minute Deployment

### Step 1: Clone Repository (30 sec)

```bash
git clone https://github.com/yourusername/timetracker.git
cd timetracker
```

### Step 2: Generate Secrets (30 sec)

```bash
chmod +x scripts/generate-secrets.sh
./scripts/generate-secrets.sh --env > backend/.env
```

### Step 3: Configure Environment (2 min)

Edit `backend/.env` with your values:

```env
# Required changes:
ALLOWED_ORIGINS=https://yourdomain.com
FIRST_SUPER_ADMIN_EMAIL=admin@yourdomain.com
FIRST_SUPER_ADMIN_PASSWORD=YourSecurePassword123!

# Optional branding:
VITE_APP_NAME=Your Company TimeTracker
VITE_PRIMARY_COLOR=#3B82F6
```

### Step 4: Deploy (2 min)

```bash
chmod +x scripts/deploy-sequential.sh
./scripts/deploy-sequential.sh
```

That's it! 🎉

---

## Access Your App

- **URL:** https://yourdomain.com
- **Admin Login:** Use credentials from Step 3

---

## Next Steps

| Task | Guide |
|------|-------|
| Add users | [Admin Guide](ADMIN_GUIDE.md) |
| Configure email | [Email Setup](EMAIL_CONFIGURATION.md) |
| Customize branding | [Branding Guide](BRANDING_CUSTOMIZATION.md) |
| Set up backups | Run `scripts/backup-client.sh` |

---

## Troubleshooting

**App not loading?**
```bash
./scripts/health-check.sh
docker logs timetracker-backend
```

**Database issues?**
```bash
docker exec timetracker-backend alembic upgrade head
```

**Need to restart?**
```bash
docker compose -f docker-compose.prod.yml restart
```

---

## Script Reference

| Script | Purpose |
|--------|---------|
| `deploy-sequential.sh` | Safe deployment (prevents RAM crashes) |
| `generate-secrets.sh` | Generate secure credentials |
| `backup-client.sh` | Create full backup |
| `restore-backup.sh` | Restore from backup |
| `health-check.sh` | Monitor system health |

---

*For detailed deployment options, see [DEPLOYMENT_RESALE_GUIDE.md](../DEPLOYMENT_RESALE_GUIDE.md)*
