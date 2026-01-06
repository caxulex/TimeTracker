# TimeTracker Client Management

This directory contains tools and templates for managing TimeTracker client deployments.

## Directory Structure

```
clients/
├── README.md                 # This file
├── clients.json              # Client registry (track all deployments)
├── template/
│   └── .env.template         # Environment configuration template
└── docs/
    ├── ONBOARDING_CHECKLIST.md   # Client onboarding steps
    ├── HANDOFF_TEMPLATE.md       # Client handoff email template
    ├── SUPPORT_TIERS.md          # Support tier definitions
    └── PRICING_GUIDE.md          # Pricing calculator guide
```

## Quick Start

### 1. Register a New Client

Add entry to `clients.json`:
```json
{
  "client_id": "acme-corp",
  "company_name": "Acme Corporation",
  "domain": "timetracker.acme.com",
  "plan": "professional",
  "deployed_at": "2026-01-06",
  "status": "active"
}
```

### 2. Deploy Client

```bash
# Generate configuration
./scripts/generate-secrets.sh --env > clients/acme-corp/.env

# Deploy
./scripts/deploy-client.sh timetracker.acme.com admin@acme.com
```

### 3. Complete Onboarding

Follow the checklist in `docs/ONBOARDING_CHECKLIST.md`

### 4. Hand Off to Client

Use the template in `docs/HANDOFF_TEMPLATE.md`

## Client Registry

The `clients.json` file tracks all deployed clients:

| Field | Description |
|-------|-------------|
| `client_id` | Unique identifier (slug) |
| `company_name` | Display name |
| `domain` | Deployed domain |
| `plan` | starter / professional / enterprise |
| `deployed_at` | ISO date of deployment |
| `status` | active / suspended / cancelled |
| `server_ip` | Server IP address |
| `admin_email` | Primary contact |
| `notes` | Additional notes |

## Support Tiers

| Tier | Response Time | Includes |
|------|---------------|----------|
| Starter | 48 hours | Email support |
| Professional | 24 hours | Email + priority fixes |
| Enterprise | 4 hours | Phone + dedicated support |

See `docs/SUPPORT_TIERS.md` for full details.

## Pricing Guide

See `docs/PRICING_GUIDE.md` for:
- Infrastructure cost calculator
- Suggested client pricing
- Margin calculations

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/deploy-client.sh` | Full client deployment |
| `scripts/backup-client.sh` | Create client backup |
| `scripts/restore-backup.sh` | Restore from backup |
| `scripts/health-check.sh` | Monitor client health |
| `scripts/generate-secrets.sh` | Generate secure credentials |

## Best Practices

1. **Always use unique secrets** - Never share JWT secrets between clients
2. **Regular backups** - Set up automated backups for each client
3. **Monitor health** - Use health-check.sh regularly
4. **Document everything** - Keep client notes updated
5. **Version control** - Track client configurations in git (exclude secrets!)
