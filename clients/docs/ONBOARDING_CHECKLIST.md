# Client Onboarding Checklist

Use this checklist for every new TimeTracker client deployment.

---

## Pre-Deployment (Sales/Planning)

- [ ] **Contract signed** - EULA, Terms of Service accepted
- [ ] **Plan selected** - Starter / Professional / Enterprise
- [ ] **Domain decided** - Client provides domain or subdomain
- [ ] **Admin contact** - Primary admin email confirmed
- [ ] **Branding assets** - Logo, colors (if custom branding)
- [ ] **User count estimate** - For capacity planning

---

## Server Setup

- [ ] **Server provisioned**
  - Provider: ________________
  - IP: ________________
  - RAM: _______ GB
  - Storage: _______ GB

- [ ] **DNS configured**
  - A record pointing to server IP
  - Propagation verified (use dig or nslookup)

- [ ] **SSH access confirmed**
  - SSH key added
  - Root/sudo access verified

---

## Deployment

- [ ] **Repository cloned**
  ```bash
  git clone https://github.com/yourrepo/timetracker.git
  ```

- [ ] **Secrets generated**
  ```bash
  ./scripts/generate-secrets.sh --env > backend/.env
  ```

- [ ] **Environment configured**
  - [ ] Domain set
  - [ ] Admin email set
  - [ ] SMTP configured (if email enabled)
  - [ ] Branding variables set (if custom)

- [ ] **Deployment executed**
  ```bash
  ./scripts/deploy-sequential.sh
  ```

- [ ] **Health check passed**
  ```bash
  ./scripts/health-check.sh
  ```

---

## Post-Deployment Verification

- [ ] **SSL certificate active** - HTTPS working
- [ ] **Login page accessible** - No errors
- [ ] **Admin login works** - Using provided credentials
- [ ] **Timer functionality** - Start/stop timer works
- [ ] **WebSocket connected** - Real-time updates working
- [ ] **Database migrations** - All applied

---

## Client Configuration

- [ ] **Admin user created** - Password communicated securely
- [ ] **Teams set up** - If client provided team structure
- [ ] **Projects created** - If client provided project list
- [ ] **Additional users** - Invitations sent (if applicable)

---

## Documentation Provided

- [ ] **Credentials document** - Secure channel (not email!)
- [ ] **User Quick Start guide** - Link or PDF
- [ ] **Admin guide** - Link or PDF
- [ ] **Support contact info** - Email/phone for support tier

---

## Backup & Monitoring

- [ ] **Initial backup created**
  ```bash
  ./scripts/backup-client.sh
  ```

- [ ] **Backup schedule set** - Cron job or manual reminder
- [ ] **Monitoring configured** - Health checks scheduled

---

## Client Registry

- [ ] **Added to clients.json**
  ```json
  {
    "client_id": "slug-name",
    "company_name": "Company Name",
    "domain": "timetracker.company.com",
    "plan": "professional",
    "deployed_at": "2026-01-06",
    "status": "active"
  }
  ```

---

## Handoff

- [ ] **Handoff email sent** - Using HANDOFF_TEMPLATE.md
- [ ] **Training call scheduled** - If included in plan
- [ ] **Billing set up** - Invoice or subscription

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Deployer | | | |
| Client Admin | | | |

---

## Notes

_Add any client-specific notes here:_

```
[Date] - Note
```
