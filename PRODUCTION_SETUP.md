# 🚀 Production Setup Guide - Time Tracker

This guide will help you set up the Time Tracker system for production use with real workers, teams, and projects.

## 📋 Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ with virtualenv
- Node.js 18+ and npm
- PostgreSQL and Redis (running via Docker)

## 🔧 Step 1: Start Required Services

```powershell
# Start PostgreSQL and Redis
cd "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker"
docker compose up -d postgres redis
```

Verify services are running:
```powershell
docker compose ps
```

## 🗄️ Step 2: Reset Database to Production State

This will remove all demo/test data and create only the admin account:

```powershell
cd backend
& "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\.venv\Scripts\python.exe" -m scripts.reset_production
```

**Follow the prompts to:**
1. Confirm deletion of all data (type `YES`)
2. Enter admin email (or use default: admin@laboratoriodelolor.com)
3. Enter admin password (must meet strength requirements — 12+ chars with mixed case, numbers, and symbols)
4. Enter admin name (or use default: Sistema Administrador)

**⚠️ SAVE THE ADMIN CREDENTIALS SECURELY!**

## 🎯 Step 3: Start the Application

### Backend (API Server)
```powershell
cd backend
& "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (Web Interface)
```powershell
cd frontend
npm run dev
```

Access the application at: **http://localhost:5173**

## 👥 Step 4: Set Up Your Organization

### 4.1 Login as Admin
1. Go to http://localhost:5173
2. Login with admin credentials

### 4.2 Create Teams
Teams organize your workers by department, project, or any grouping you need.

1. Navigate to **Teams** page
2. Click **Create Team**
3. Enter team name (e.g., "Production Team", "Clinic Staff")
4. Save

### 4.3 Create Workers
1. Navigate to **Staff** page (from sidebar)
2. Click **Add Staff Member**
3. Fill in:
   - Name
   - Email
   - Password (worker will use this to login)
   - Role: `Worker` (or `Admin` for administrative access)
4. Click **Create Staff**

### 4.4 Add Workers to Teams
1. On the **Staff** page, find the worker
2. Click the **Manage Teams** icon (👥 teams icon)
3. Select team to add worker to
4. Click **Add to Team**
5. Close modal

**✨ Real-time Update:** The worker will immediately see the team in their account if they're logged in!

### 4.5 Create Projects
Projects are what workers track time against.

1. Navigate to **Projects**
2. Click **Create Project**
3. Fill in:
   - Project Name
   - Description (optional)
   - Team (select the team that will work on this)
   - Color (for visual identification)
4. Save

**✨ Real-time Update:** All team members will immediately see this project in their dashboard!

### 4.6 Create Tasks (Optional)
Tasks break down projects into smaller trackable items.

1. Open a project
2. Click **Create Task**
3. Fill in:
   - Task Name
   - Description
   - Status: `TODO`, `IN_PROGRESS`, or `DONE`
4. Save

**✨ Real-time Update:** Team members see new tasks instantly!

## 🎨 Step 5: Worker Experience

When a worker logs in, they will automatically see:
- ✅ All teams they're members of
- ✅ All projects from their teams
- ✅ All tasks assigned to those projects
- ✅ Real-time updates when admin creates new items
- ✅ Ability to start/stop timers on any project

## 📊 Step 6: Admin Monitoring

As admin, you can:
- View all worker time entries
- See real-time active timers
- Generate reports by worker, project, or date range
- Monitor team productivity
- Export data to Excel/PDF

Navigate to **Admin** menu to access these features.

## 🔔 Real-Time Features

The system uses WebSockets for instant updates:

### Workers get notified when:
- ✅ They're added to a team
- ✅ A new project is created in their team
- ✅ A new task is created
- ✅ Another team member starts/stops a timer

### No page refresh needed!
All updates appear automatically in the UI.

## 📱 Daily Workflow

### For Workers:
1. Login
2. Go to Dashboard
3. Select project
4. Click **Start Timer**
5. Work on task
6. Click **Stop Timer**
7. View weekly summary and reports

### For Admin:
1. Login
2. View Dashboard (see all team activity)
3. Check Active Timers panel
4. Generate reports as needed
5. Manage teams/projects/workers

## 🔒 Security Best Practices

1. **Change default admin password immediately**
2. **Use strong passwords for all workers**
3. **Regularly backup the database:**
   ```powershell
   docker exec time-tracker-postgres pg_dump -U postgres time_tracker > backup_$(Get-Date -Format "yyyyMMdd_HHmmss").sql
   ```
4. **Enable SSL/HTTPS in production**
5. **Set up firewall rules to restrict access**

## 🔄 Database Backups

### Manual Backup
```powershell
docker exec time-tracker-postgres pg_dump -U postgres time_tracker > backup.sql
```

### Restore Backup
```powershell
cat backup.sql | docker exec -i time-tracker-postgres psql -U postgres -d time_tracker
```

### Automated Backups (recommended)
Set up a scheduled task to run backups daily at 2 AM:
```powershell
# Use Windows Task Scheduler or the provided script:
.\scripts\backup-db.ps1
```

## 📞 Support & Troubleshooting

### Workers can't see projects
- Verify they're added to the correct team
- Check that projects belong to that team
- Ensure worker is active (not deactivated)

### Real-time updates not working
- Check WebSocket connection in browser console
- Verify both backend and frontend are running
- Check Redis is running: `docker compose ps redis`

### Database connection errors
- Ensure PostgreSQL container is running
- Check connection string in backend/.env
- Verify port 5434 is not blocked

## 🛠️ Configuration Files

### Backend Environment (.env)
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/time_tracker
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
ENVIRONMENT=production
DEBUG=False
```

### Frontend Proxy (vite.config.ts)
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  }
}
```

## 📈 Scaling for Production

For larger deployments:
1. Use PostgreSQL replication
2. Deploy Redis in cluster mode
3. Run multiple backend instances behind a load balancer
4. Use CDN for frontend assets
5. Enable database connection pooling
6. Set up monitoring with Prometheus/Grafana

## ✅ Production Checklist

- [ ] Admin account created with strong password
- [ ] All demo data removed
- [ ] Teams created and organized
- [ ] Workers created with proper credentials
- [ ] Workers added to appropriate teams
- [ ] Projects created and assigned to teams
- [x] Database backup scheduled (see below)
- [x] SSL/HTTPS configured (AWS Lightsail)
- [ ] Firewall rules set up
- [ ] Monitoring configured
- [ ] Worker training completed

---

## 🔒 SSL/HTTPS Configuration

**Status: ✅ Configured via AWS Lightsail**

TimeTracker uses AWS Lightsail's built-in load balancer for SSL termination:
- Certificate managed by AWS Certificate Manager (ACM)
- Automatic renewal (no manual intervention needed)
- HTTPS enforced on `https://<YOUR_DOMAIN>`

### Verify SSL Status
```bash
# Check certificate details
curl -vI https://<YOUR_DOMAIN> 2>&1 | grep -A 5 "Server certificate"

# Test SSL grade (visit in browser)
# https://www.ssllabs.com/ssltest/analyze.html?d=<YOUR_DOMAIN>
```

### Security Headers (Already Configured)
The application includes these security headers:
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy` (CSP)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`

---

## 💾 Database Backup System

### Setup Automated Backups

1. **Copy scripts to server:**
```bash
scp backend/scripts/backup_database.sh ubuntu@your-server:/home/ubuntu/scripts/
scp backend/scripts/restore_database.sh ubuntu@your-server:/home/ubuntu/scripts/
```

2. **Make executable:**
```bash
chmod +x /home/ubuntu/scripts/backup_database.sh
chmod +x /home/ubuntu/scripts/restore_database.sh
```

3. **Configure cron for daily backups at 2 AM:**
```bash
crontab -e
# Add this line:
0 2 * * * /home/ubuntu/scripts/backup_database.sh >> /home/ubuntu/backups/cron.log 2>&1
```

### Backup Configuration

Set environment variables in the script or export them:
```bash
export BACKUP_DIR="/home/ubuntu/backups"
export RETENTION_DAYS=30
export DB_CONTAINER="timetracker-db-1"
export DB_NAME="time_tracker"

# Optional: S3 upload
export S3_BUCKET="your-bucket-name"

# Optional: Slack/Discord notifications
export WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### Manual Backup
```bash
# Create immediate backup
/home/ubuntu/scripts/backup_database.sh

# Create full backup
/home/ubuntu/scripts/backup_database.sh --full
```

### Restore from Backup
```bash
# List available backups
/home/ubuntu/scripts/restore_database.sh --list

# Restore latest backup
/home/ubuntu/scripts/restore_database.sh --latest

# Restore specific backup
/home/ubuntu/scripts/restore_database.sh /home/ubuntu/backups/daily/time_tracker_daily_20260121_020000.sql.gz
```

### Backup Schedule
| Type | Frequency | Retention |
|------|-----------|-----------|
| Daily | Every day at 2 AM | 30 days |
| Weekly | Sunday at 3 AM | 90 days |

---

## 🎉 You're Ready!

Your Time Tracker system is now configured for production use with:
- ✅ Real workers (no demo accounts)
- ✅ Real teams and projects
- ✅ Real-time synchronization
- ✅ Instant visibility for all team members
- ✅ Secure admin controls

Workers will see their teams, projects, and tasks immediately when admins create them - no manual refresh needed!
