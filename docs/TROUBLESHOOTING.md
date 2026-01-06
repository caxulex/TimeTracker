# TimeTracker Troubleshooting Guide

Common issues and their solutions.

---

## Table of Contents

1. [Deployment Issues](#deployment-issues)
2. [Login Problems](#login-problems)
3. [Performance Issues](#performance-issues)
4. [Database Issues](#database-issues)
5. [Email Problems](#email-problems)
6. [Docker Issues](#docker-issues)
7. [SSL/HTTPS Issues](#sslhttps-issues)

---

## Deployment Issues

### Server crashes during build

**Symptom:** Server becomes unresponsive during `docker compose up --build`

**Cause:** Simultaneous builds consume too much RAM (common on <2GB servers)

**Solution:** Use sequential build script:
```bash
./scripts/deploy-sequential.sh
```

### Build fails with "no space left"

**Solution:**
```bash
# Clean Docker cache
docker system prune -a -f
docker builder prune -a -f

# Check disk space
df -h
```

### Container fails to start

**Solution:**
```bash
# Check logs
docker logs timetracker-backend
docker logs timetracker-frontend

# Verify environment
docker exec timetracker-backend env | grep -E "DATABASE|SECRET"
```

---

## Login Problems

### "Invalid credentials" error

**Checks:**
1. Verify email is correct (case-sensitive)
2. Check if account is active
3. Try password reset

**Admin fix:**
```bash
# Check user in database
docker exec -it timetracker-db psql -U postgres -d time_tracker -c \
  "SELECT email, is_active FROM users WHERE email='user@example.com';"

# Activate user
docker exec -it timetracker-db psql -U postgres -d time_tracker -c \
  "UPDATE users SET is_active=true WHERE email='user@example.com';"
```

### "Session expired" frequently

**Cause:** JWT token expiration or clock sync issues

**Solution:**
```bash
# Check server time
date

# Sync time
sudo ntpdate -u pool.ntp.org
```

### Can't access admin pages

**Check role assignment:**
```bash
docker exec -it timetracker-db psql -U postgres -d time_tracker -c \
  "SELECT u.email, r.name FROM users u JOIN roles r ON u.role_id = r.id;"
```

---

## Performance Issues

### App loads slowly

**Quick diagnosis:**
```bash
./scripts/health-check.sh
```

**Common causes:**
1. **Too many API calls** - Check browser Network tab
2. **Database queries slow** - Check backend logs
3. **High memory usage** - Check container stats

```bash
docker stats --no-stream
```

### Dashboard timeout

**Increase timeout:**
```env
# In backend/.env
REQUEST_TIMEOUT=60
```

**Optimize database:**
```bash
docker exec -it timetracker-db psql -U postgres -d time_tracker -c "VACUUM ANALYZE;"
```

### High CPU usage

**Check which container:**
```bash
docker stats --no-stream
```

**Common fixes:**
- Restart affected container
- Check for infinite loops in logs
- Increase resources if needed

---

## Database Issues

### "Connection refused" error

**Solution:**
```bash
# Check if database is running
docker ps | grep db

# Restart database
docker restart timetracker-db

# Wait for startup
sleep 10

# Restart backend
docker restart timetracker-backend
```

### Migration fails

**Solution:**
```bash
# View migration status
docker exec timetracker-backend alembic current

# Run pending migrations
docker exec timetracker-backend alembic upgrade head

# If stuck, check history
docker exec timetracker-backend alembic history
```

### Data corruption

**Restore from backup:**
```bash
./scripts/restore-backup.sh --list
./scripts/restore-backup.sh --verify latest
./scripts/restore-backup.sh latest
```

### Out of connections

**Symptoms:** "too many connections" errors

**Solution:**
```bash
# Check active connections
docker exec -it timetracker-db psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Kill idle connections
docker exec -it timetracker-db psql -U postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'idle' AND pid <> pg_backend_pid();"
```

---

## Email Problems

### Emails not sending

**Check SMTP configuration:**
```bash
# Verify env vars
docker exec timetracker-backend env | grep SMTP
```

**Required settings:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=app-password
SMTP_FROM_EMAIL=your@gmail.com
```

**Test manually:**
```bash
docker exec -it timetracker-backend python -c "
from app.services.email_service import email_service
email_service.send_test_email('test@example.com')
"
```

### Gmail authentication failed

**Solution:** Use App Password, not regular password:
1. Go to https://myaccount.google.com/apppasswords
2. Generate new app password
3. Use that in `SMTP_PASSWORD`

### Emails going to spam

**Solutions:**
1. Set up SPF record for your domain
2. Set up DKIM
3. Use professional email service (SendGrid, Mailgun)

---

## Docker Issues

### Container keeps restarting

**Check logs:**
```bash
docker logs --tail 100 timetracker-backend
```

**Common causes:**
- Missing environment variables
- Database not ready
- Port already in use

### "Port already in use"

**Solution:**
```bash
# Find process using port
sudo lsof -i :8080
sudo lsof -i :3000

# Kill process
sudo kill -9 <PID>

# Or change port in docker-compose
```

### Cannot connect to Docker daemon

**Solution:**
```bash
# Start Docker service
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Images not pulling

**Solutions:**
```bash
# Login to registry
docker login ghcr.io

# Clear DNS cache
sudo systemd-resolve --flush-caches

# Try pulling explicitly
docker pull ghcr.io/yourusername/timetracker-backend:latest
```

---

## SSL/HTTPS Issues

### Certificate not generating

**Check Caddy logs:**
```bash
docker logs timetracker-caddy
```

**Common causes:**
1. DNS not propagated yet (wait 15-60 min)
2. Port 80/443 blocked by firewall
3. Domain pointing to wrong IP

**Fix firewall:**
```bash
sudo ufw allow 80
sudo ufw allow 443
```

### Mixed content warnings

**Cause:** HTTP resources loaded on HTTPS page

**Solution:** Ensure all URLs use HTTPS:
```env
ALLOWED_ORIGINS=https://yourdomain.com
VITE_API_URL=https://yourdomain.com/api
```

### Certificate expired

**Force renewal:**
```bash
docker restart timetracker-caddy
# Caddy auto-renews certificates
```

---

## Quick Diagnostic Commands

```bash
# Full health check
./scripts/health-check.sh

# Container status
docker ps -a

# Resource usage
docker stats --no-stream

# Backend logs
docker logs --tail 100 timetracker-backend

# Frontend logs
docker logs --tail 100 timetracker-frontend

# Database logs
docker logs --tail 100 timetracker-db

# Check disk space
df -h

# Check memory
free -h

# Network connectivity
curl -I http://localhost:8080/health
```

---

## Getting Help

1. **Check logs first** - Most issues have clear error messages
2. **Run health check** - `./scripts/health-check.sh`
3. **Search this guide** - Ctrl+F for error message
4. **Check GitHub Issues** - Someone may have solved it

---

## Emergency Recovery

### Complete restart:
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Factory reset (⚠️ destroys data):
```bash
docker compose -f docker-compose.prod.yml down -v
docker system prune -a -f
./scripts/deploy-sequential.sh
```

### Restore from backup:
```bash
./scripts/restore-backup.sh --list
./scripts/restore-backup.sh <backup-file>
```

---

*For additional help, see [Admin Guide](ADMIN_GUIDE.md) or [Deployment Guide](../DEPLOYMENT_RESALE_GUIDE.md)*
