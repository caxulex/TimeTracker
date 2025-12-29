# TimeTracker Administrator Guide

Complete guide for administrators managing TimeTracker deployments.

---

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [User Management](#user-management)
3. [Role Permissions](#role-permissions)
4. [System Configuration](#system-configuration)
5. [Monitoring & Health](#monitoring--health)
6. [Backup & Recovery](#backup--recovery)
7. [Troubleshooting](#troubleshooting)
8. [Security Best Practices](#security-best-practices)

---

## Initial Setup

### First-Time Configuration

1. **Set Environment Variables**
   ```bash
   # Copy template
   cp backend/.env.example backend/.env
   
   # Generate secure secret key
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

2. **Configure Super Admin**
   ```env
   FIRST_SUPER_ADMIN_EMAIL=admin@yourcompany.com
   FIRST_SUPER_ADMIN_PASSWORD=YourSecurePassword123!
   ```

3. **Start Services**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Run Database Migrations**
   ```bash
   docker exec timetracker-backend alembic upgrade head
   ```

### Verifying Installation

Check system health:
```bash
curl https://your-domain.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

---

## User Management

### Creating Users

**Option 1: Account Requests (Recommended)**
1. Users visit `/register` and request an account
2. Admin receives notification
3. Admin approves/rejects in Admin Panel → Account Requests

**Option 2: Direct Creation (Admin Panel)**
1. Go to Admin Panel → Users
2. Click "Add User"
3. Fill in details and assign role
4. User receives login credentials

### Managing Users

| Action | Location | Notes |
|--------|----------|-------|
| View all users | Admin → Users | Search/filter available |
| Edit user | User row → Edit | Change name, email, role |
| Deactivate user | User row → Deactivate | Soft delete, preserves data |
| Reset password | User row → Reset | Sends reset email or shows temp password |
| Change role | User row → Edit → Role | Requires appropriate permissions |

### Bulk Operations

For bulk user imports, use the API:
```bash
POST /api/users/bulk
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "users": [
    {"name": "John Doe", "email": "john@company.com", "role": "employee"},
    {"name": "Jane Smith", "email": "jane@company.com", "role": "manager"}
  ]
}
```

---

## Role Permissions

### Role Hierarchy

```
Super Admin (Level 4)
    └── Admin (Level 3)
        └── Manager (Level 2)
            └── Employee (Level 1)
```

### Permission Matrix

| Feature | Employee | Manager | Admin | Super Admin |
|---------|----------|---------|-------|-------------|
| Track own time | ✅ | ✅ | ✅ | ✅ |
| View own reports | ✅ | ✅ | ✅ | ✅ |
| View team reports | ❌ | ✅ | ✅ | ✅ |
| Manage projects | ❌ | ✅ | ✅ | ✅ |
| Manage teams | ❌ | Own team | ✅ | ✅ |
| View all users | ❌ | ❌ | ✅ | ✅ |
| Create users | ❌ | ❌ | ✅ | ✅ |
| Delete users | ❌ | ❌ | ❌ | ✅ |
| System settings | ❌ | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ❌ | ✅ | ✅ |

### Assigning Roles

**Important**: Only assign roles based on job function:
- **Employee**: Individual contributors
- **Manager**: Team leads who need to review team time
- **Admin**: HR or operations staff
- **Super Admin**: IT administrators only (limit to 1-2 people)

---

## System Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | development/staging/production | development |
| `DEBUG` | Enable debug mode | false |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime | 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | 7 |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | API rate limit | 60 |
| `BCRYPT_ROUNDS` | Password hashing cost | 12 |

### Adjusting Rate Limits

For high-traffic deployments:
```env
RATE_LIMIT_REQUESTS_PER_MINUTE=120
RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE=10
```

### Session Configuration

```env
# Longer sessions for trusted networks
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
```

---

## Monitoring & Health

### Health Endpoints

| Endpoint | Purpose | Usage |
|----------|---------|-------|
| `GET /health` | Basic health check | Load balancers |
| `GET /api/health` | Detailed health with DB/Redis | Monitoring |
| `GET /api/version` | Version and build info | Debugging |

### Setting Up Monitoring

**Using cURL (cron job)**:
```bash
# Add to crontab -e
*/5 * * * * curl -s https://your-domain.com/api/health | grep -q '"status":"healthy"' || echo "Alert: TimeTracker unhealthy" | mail -s "Health Alert" admin@company.com
```

**Using Uptime Kuma**:
1. Add HTTP monitor
2. URL: `https://your-domain.com/api/health`
3. Expected: Contains `"status":"healthy"`

### Viewing Logs

```bash
# All logs
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

---

## Backup & Recovery

### Automated Backups

**Daily backup script** (add to cron):
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups/timetracker

# Database backup
docker exec timetracker-db pg_dump -U timetracker time_tracker > $BACKUP_DIR/db_$DATE.sql

# Compress
gzip $BACKUP_DIR/db_$DATE.sql

# Keep last 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete
```

### Manual Backup

```bash
# Database
docker exec timetracker-db pg_dump -U timetracker time_tracker > backup.sql

# Full data directory
docker run --rm -v timetracker_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz /data
```

### Restore from Backup

```bash
# Stop application
docker-compose down

# Restore database
docker-compose up -d postgres
cat backup.sql | docker exec -i timetracker-db psql -U timetracker time_tracker

# Start all services
docker-compose up -d
```

---

## Troubleshooting

### Common Issues

#### Users can't login
1. Check if user is active: Admin → Users → Check status
2. Verify email is correct (case-sensitive)
3. Reset password if needed
4. Check rate limiting (max 5 attempts/minute)

#### Slow performance
1. Check Redis: `docker exec timetracker-redis redis-cli ping`
2. Check database connections
3. Review container resources: `docker stats`

#### WebSocket disconnections
1. Check Caddy/nginx proxy timeout settings
2. Verify WebSocket upgrade headers
3. Check client network stability

#### 502 Bad Gateway
1. Check backend is running: `docker-compose ps`
2. Check backend logs: `docker-compose logs backend`
3. Verify port configuration

### Debug Mode

**⚠️ Never enable in production!**

For development debugging:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Getting Support

1. Check logs for error messages
2. Review this guide
3. Search existing issues on GitHub
4. Contact support with:
   - Error message
   - Steps to reproduce
   - Log output
   - System version (`/api/version`)

---

## Security Best Practices

### Regular Maintenance

- [ ] **Weekly**: Review failed login attempts
- [ ] **Monthly**: Audit user accounts and roles
- [ ] **Monthly**: Update Docker images
- [ ] **Quarterly**: Rotate SECRET_KEY (requires all users to re-login)
- [ ] **Quarterly**: Review and update dependencies

### Access Control

1. **Limit Super Admin accounts** to 1-2 trusted IT staff
2. **Review role assignments** when employees change positions
3. **Deactivate accounts** immediately when employees leave
4. **Use strong passwords** - enforce via password strength validation

### Network Security

1. **Always use HTTPS** - Caddy handles this automatically
2. **Restrict database access** - only from backend container
3. **Use firewall rules** - only expose ports 80/443

### Audit Logging

Enable audit logging to track:
- Login attempts (successful/failed)
- User creation/modification
- Role changes
- Data exports

View audit logs: Admin Panel → System → Audit Logs

---

## Quick Reference

### Important URLs

| URL | Purpose |
|-----|---------|
| `/` | Main application |
| `/login` | User login |
| `/admin` | Admin dashboard |
| `/api/docs` | API documentation (dev only) |
| `/api/health` | Health check |

### Docker Commands

```bash
# Start
docker-compose -f docker-compose.prod.yml up -d

# Stop
docker-compose -f docker-compose.prod.yml down

# Restart backend
docker-compose -f docker-compose.prod.yml restart backend

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Update images
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### Database Commands

```bash
# Connect to database
docker exec -it timetracker-db psql -U timetracker time_tracker

# Run migrations
docker exec timetracker-backend alembic upgrade head

# Check migration status
docker exec timetracker-backend alembic current
```

---

*Last updated: December 29, 2025*
