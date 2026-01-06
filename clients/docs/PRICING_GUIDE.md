# TimeTracker Pricing Guide

This guide helps you calculate costs and set pricing for TimeTracker deployments.

---

## Infrastructure Cost Calculator

### Server Sizing by User Count

| Users | RAM | vCPU | Storage | Recommended |
|-------|-----|------|---------|-------------|
| 1-10 | 1 GB | 1 | 25 GB | Starter |
| 10-50 | 2 GB | 1 | 50 GB | Standard |
| 50-200 | 4 GB | 2 | 100 GB | Professional |
| 200-500 | 8 GB | 4 | 200 GB | Enterprise |
| 500+ | 16 GB+ | 8+ | 500 GB+ | Custom |

### Monthly Infrastructure Costs

#### AWS Lightsail
| Instance | RAM | Price/Month |
|----------|-----|-------------|
| Nano | 512 MB | $3.50 |
| Micro | 1 GB | $5.00 |
| Small | 2 GB | $10.00 |
| Medium | 4 GB | $20.00 |
| Large | 8 GB | $40.00 |
| XLarge | 16 GB | $80.00 |

#### DigitalOcean
| Droplet | RAM | Price/Month |
|---------|-----|-------------|
| Basic | 1 GB | $6.00 |
| Basic | 2 GB | $12.00 |
| Basic | 4 GB | $24.00 |
| Basic | 8 GB | $48.00 |
| Premium | 16 GB | $96.00 |

#### Hetzner (Best Value)
| Server | RAM | Price/Month |
|--------|-----|-------------|
| CX11 | 2 GB | €3.79 (~$4) |
| CX21 | 4 GB | €5.83 (~$6) |
| CX31 | 8 GB | €10.59 (~$11) |
| CX41 | 16 GB | €18.59 (~$20) |

---

## Additional Costs

### Optional Services

| Service | Cost/Month | Notes |
|---------|------------|-------|
| Automated backups | $1-5 | Cloud provider dependent |
| Monitoring (UptimeRobot) | $0-7 | Free tier available |
| Email (SendGrid) | $0-15 | Free tier: 100 emails/day |
| Domain | $1-2 | Annual cost amortized |
| SSL | $0 | Free via Let's Encrypt/Caddy |

### One-Time Costs

| Service | Cost | Notes |
|---------|------|-------|
| Deployment setup | 1-2 hours | Your time |
| Custom branding | 0-2 hours | If requested |
| Data migration | Variable | From existing system |
| Training session | 1-2 hours | If included |

---

## Suggested Pricing Structure

### Plan Comparison

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| **Price/Month** | $29 | $79 | $199+ |
| Users | Up to 10 | Up to 50 | Unlimited |
| Projects | Unlimited | Unlimited | Unlimited |
| Time Tracking | ✅ | ✅ | ✅ |
| Reports | Basic | Advanced | Advanced + Export |
| Teams | 1 | Unlimited | Unlimited |
| Support | Email (48h) | Priority (24h) | Premium (4h) |
| Backups | Weekly | Daily | Real-time |
| Custom Branding | ❌ | ✅ | ✅ |
| API Access | ❌ | ❌ | ✅ |
| AI Features | ❌ | ❌ | ✅ |
| Dedicated Support | ❌ | ❌ | ✅ |

### Margin Analysis

| Plan | Your Cost | Client Price | Margin | Margin % |
|------|-----------|--------------|--------|----------|
| Starter | ~$6/mo | $29/mo | $23 | 79% |
| Professional | ~$15/mo | $79/mo | $64 | 81% |
| Enterprise | ~$30/mo | $199/mo | $169 | 85% |

---

## Pricing Calculator

### Formula

```
Monthly Price = Infrastructure Cost + Support Cost + Profit Margin

Where:
- Infrastructure Cost = Server + Backups + Email
- Support Cost = (Hours/month × Hourly Rate) / Clients in tier
- Profit Margin = Target % of total
```

### Example: Professional Plan

```
Infrastructure:
  Server (2GB): $12
  Backups: $2
  Email: $0 (free tier)
  Subtotal: $14

Support allocation:
  Estimated 1 hour/month support
  At $50/hour = $50
  Split across ~5 clients = $10/client

Target margin: 80%

Calculation:
  Costs: $14 + $10 = $24
  With 80% margin: $24 / (1 - 0.80) = $120

Rounded price: $79/month (conservative)
Actual margin: ($79 - $24) / $79 = 70%
```

---

## Volume Discounts

### Annual Payment Discount
- 10-15% discount for annual prepayment
- Example: $79/mo → $69/mo (annual)

### Multi-Instance Discount
| Instances | Discount |
|-----------|----------|
| 2-5 | 10% |
| 6-10 | 15% |
| 11+ | 20% |

---

## Add-On Services

### One-Time Services

| Service | Price | Notes |
|---------|-------|-------|
| Initial setup | $0-200 | Often included |
| Data migration | $200-500 | Depends on complexity |
| Custom branding setup | $100-200 | Logo, colors |
| Training (1 hour) | $100 | Remote session |
| Training (on-site) | $500+ | Plus travel |

### Recurring Add-Ons

| Service | Price/Month | Notes |
|---------|-------------|-------|
| Extra backups | $10 | Daily → Hourly |
| Custom domain SSL | $5 | If not using Caddy |
| Priority support upgrade | $30 | Starter → Professional support |
| Additional storage (50GB) | $5 | For file uploads |

---

## Competitive Pricing Reference

### Market Comparison

| Competitor | Price | Users | Notes |
|------------|-------|-------|-------|
| Toggl Track | $9/user | Per user | No self-host |
| Harvest | $12/user | Per user | No self-host |
| Clockify | $4.99/user | Per user | Limited features |
| Hubstaff | $7/user | Per user | No self-host |

### Your Advantage
- **Flat pricing** - Not per-user
- **Self-hosted** - Client owns data
- **No vendor lock-in** - Open deployment
- **Customizable** - Branding, features

---

## Quoting Template

```
═══════════════════════════════════════════════════
          TIMETRACKER QUOTE
═══════════════════════════════════════════════════

Client: [COMPANY_NAME]
Date: [DATE]
Valid for: 30 days

───────────────────────────────────────────────────
SELECTED PLAN: [PLAN_NAME]
───────────────────────────────────────────────────

Monthly Fee:                          $[PRICE]

Includes:
• [USER_LIMIT] users
• Unlimited time tracking
• [FEATURES_LIST]
• [SUPPORT_LEVEL] support

───────────────────────────────────────────────────
ONE-TIME FEES
───────────────────────────────────────────────────

Setup & Deployment:                   $[SETUP_FEE]
Data Migration:                       $[MIGRATION_FEE]
Training (optional):                  $[TRAINING_FEE]

───────────────────────────────────────────────────
PAYMENT OPTIONS
───────────────────────────────────────────────────

Monthly:  $[MONTHLY_TOTAL]/month
Annual:   $[ANNUAL_TOTAL]/year (save [DISCOUNT]%)

───────────────────────────────────────────────────
TOTAL DUE TODAY
───────────────────────────────────────────────────

First month + setup:                  $[TOTAL_TODAY]

═══════════════════════════════════════════════════

Terms:
• 30-day money-back guarantee
• Cancel anytime (monthly plans)
• Annual plans: prorated refund

Questions? Contact [YOUR_EMAIL]
```

---

## Revenue Projections

### Per-Client Annual Revenue

| Plan | Monthly | Annual | 3-Year LTV |
|------|---------|--------|------------|
| Starter | $29 | $348 | $1,044 |
| Professional | $79 | $948 | $2,844 |
| Enterprise | $199 | $2,388 | $7,164 |

### Growth Scenarios

| Clients | Avg Revenue | Monthly Revenue | Annual Revenue |
|---------|-------------|-----------------|----------------|
| 5 | $50 | $250 | $3,000 |
| 10 | $60 | $600 | $7,200 |
| 25 | $70 | $1,750 | $21,000 |
| 50 | $80 | $4,000 | $48,000 |
| 100 | $90 | $9,000 | $108,000 |

---

## Notes

- Prices are suggestions; adjust for your market
- Consider local purchasing power for international clients
- Enterprise pricing should be custom-quoted
- Always factor in your support time costs
