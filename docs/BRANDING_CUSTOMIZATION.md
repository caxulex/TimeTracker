# Time Tracker - Branding Customization Guide

**Last Updated:** January 6, 2026  
**Version:** 1.0

---

## Quick Start

To customize branding for a client deployment, set these environment variables before building:

```bash
# Required branding
VITE_APP_NAME=Client Time Tracker
VITE_COMPANY_NAME=Client Company Inc.
VITE_PRIMARY_COLOR=#2563eb

# Optional branding
VITE_LOGO_URL=/logo.svg
VITE_SUPPORT_EMAIL=support@client.com
```

---

## Environment Variables Reference

### Application Identity

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_APP_NAME` | Time Tracker | Application name shown in UI, browser tab, sidebar |
| `VITE_COMPANY_NAME` | Your Company | Company name in footer and copyright |
| `VITE_TAGLINE` | Track time. Boost productivity. | Tagline/description for PWA and meta tags |

### Visual Assets

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_LOGO_URL` | /logo.svg | Logo path (relative to public/) or external URL |
| `VITE_FAVICON_URL` | /favicon.svg | Favicon path or external URL |
| `VITE_PRIMARY_COLOR` | #2563eb | Primary brand color (hex with or without #) |

### Contact & Support

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_SUPPORT_EMAIL` | support@example.com | Support contact email |
| `VITE_SUPPORT_URL` | /help | Help/documentation URL |

### Legal Links

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_TERMS_URL` | /terms | Terms of Service page URL |
| `VITE_PRIVACY_URL` | /privacy | Privacy Policy page URL |

### Footer Options

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_SHOW_POWERED_BY` | true | Show "Powered by" text (set to 'false' to hide) |

---

## Where to Set Variables

### 1. Local Development

Edit `frontend/.env.local`:

```bash
# frontend/.env.local
VITE_APP_NAME=My Dev Tracker
VITE_COMPANY_NAME=Dev Company
VITE_PRIMARY_COLOR=#10b981
VITE_SUPPORT_EMAIL=dev@example.com
```

### 2. Production Deployment

Edit `.env.production` in project root:

```bash
# .env.production
VITE_APP_NAME=Client Time Tracker
VITE_COMPANY_NAME=Client Corp
VITE_LOGO_URL=/logo.svg
VITE_PRIMARY_COLOR=#2563eb
VITE_SUPPORT_EMAIL=support@client.com
```

### 3. Docker Compose

Add to `docker-compose.prod.yml`:

```yaml
services:
  frontend:
    environment:
      - VITE_APP_NAME=Client Time Tracker
      - VITE_COMPANY_NAME=Client Corp
      - VITE_PRIMARY_COLOR=#2563eb
      - VITE_SUPPORT_EMAIL=support@client.com
```

### 4. Command Line (Quick Test)

```powershell
# PowerShell (Windows)
cd frontend
$env:VITE_APP_NAME="Test App"
$env:VITE_PRIMARY_COLOR="#10b981"
npm run dev
```

```bash
# Bash (Linux/Mac)
cd frontend
VITE_APP_NAME="Test App" VITE_PRIMARY_COLOR="#10b981" npm run dev
```

---

## Custom Logo Instructions

### Option A: Replace Default Logo

1. Create your logo as SVG (recommended) or PNG
2. Replace `frontend/public/logo.svg`
3. Keep `VITE_LOGO_URL=/logo.svg` (default)

### Option B: External URL

1. Host logo on CDN or client's server
2. Set environment variable:
   ```bash
   VITE_LOGO_URL=https://cdn.client.com/logo.png
   ```

### Logo Requirements

- **Recommended size:** 64x64 pixels (or SVG for scalability)
- **Format:** SVG (preferred), PNG, or JPG
- **Background:** Should look good on white background
- **Shape:** Square or close to square ratio works best

---

## Color Customization

### Primary Color Effects

The primary color is applied to:
- ✅ Buttons (Sign in, Submit, etc.)
- ✅ Links and text links
- ✅ Navigation active states
- ✅ Form focus states (inputs, checkboxes)
- ✅ Accent highlights

### Color Examples

```bash
VITE_PRIMARY_COLOR=#2563eb    # Blue (default)
VITE_PRIMARY_COLOR=#10b981    # Green
VITE_PRIMARY_COLOR=#8b5cf6    # Purple
VITE_PRIMARY_COLOR=#ef4444    # Red
VITE_PRIMARY_COLOR=#f59e0b    # Orange/Amber
VITE_PRIMARY_COLOR=#ec4899    # Pink
VITE_PRIMARY_COLOR=#06b6d4    # Cyan
```

### Auto-Generated Variants

The branding system automatically generates:
- **Hover color:** 10% darker than primary
- **Light color:** 40% lighter than primary

---

## PWA Manifest Customization

For full Progressive Web App branding, update `frontend/public/manifest.json`:

```json
{
  "name": "Client Time Tracker",
  "short_name": "TimeTracker",
  "description": "Client's custom tagline here",
  "theme_color": "#CLIENT_PRIMARY_COLOR",
  "background_color": "#ffffff"
}
```

---

## Components Using Branding

The branding configuration is used by these components:

| Component | Branding Elements Used |
|-----------|------------------------|
| `LoginPage.tsx` | Logo, app name, colors, support email, copyright |
| `Sidebar.tsx` | Logo, app name |
| `main.tsx` | Document title, CSS variables |

---

## Architecture

```
frontend/src/config/branding.ts    # Central configuration
│
├── Reads environment variables (VITE_*)
├── Provides sensible defaults
├── Auto-generates color variants
│
├── Exports:
│   ├── branding              # Main config object
│   ├── applyBrandingStyles() # Sets CSS custom properties
│   ├── setDocumentTitle()    # Updates browser tab title
│   └── getCopyrightText()    # Returns "© 2026 Company"
│
└── Used by:
    ├── LoginPage.tsx
    ├── Sidebar.tsx
    └── main.tsx (initialization)
```

---

## Testing Branding Changes

### Quick Test Checklist

After changing branding variables:

- [ ] **Login page** shows custom logo and app name
- [ ] **Login page** shows custom colors on buttons/links
- [ ] **Login page footer** shows company name and support email
- [ ] **Sidebar** shows custom logo and app name
- [ ] **Browser tab** shows custom title
- [ ] **PWA install** shows custom name/icon (if applicable)

### Local Testing Command

```bash
cd frontend
VITE_APP_NAME="Test Brand" \
VITE_COMPANY_NAME="Test Corp" \
VITE_PRIMARY_COLOR="#10b981" \
VITE_SUPPORT_EMAIL="test@example.com" \
npm run dev
```

---

## Client Deployment Checklist

When deploying for a new client:

1. [ ] Set `VITE_APP_NAME` to client's preferred app name
2. [ ] Set `VITE_COMPANY_NAME` to client's company name
3. [ ] Set `VITE_PRIMARY_COLOR` to client's brand color
4. [ ] Replace `/logo.svg` with client's logo OR set `VITE_LOGO_URL`
5. [ ] Set `VITE_SUPPORT_EMAIL` to client's support contact
6. [ ] Update `manifest.json` if PWA support needed
7. [ ] Rebuild frontend: `npm run build`
8. [ ] Verify all branding appears correctly

---

## Troubleshooting

### Variables Not Working?

1. **Check prefix:** Variables MUST start with `VITE_`
2. **Rebuild required:** Frontend env vars are baked in at build time
3. **Cache:** Clear browser cache and restart dev server

### Logo Not Showing?

1. Verify file exists in `frontend/public/`
2. Check file permissions
3. For external URLs, verify CORS allows loading

### Colors Not Applying?

1. Ensure hex format: `#2563eb` or `2563eb`
2. Check browser dev tools for CSS variable `--color-primary`
3. Hard refresh browser (Ctrl+Shift+R)

---

## Email Template Branding

All outgoing emails (welcome, password reset, account notifications) automatically use your configured branding. No additional email-specific configuration is needed.

### How It Works

The email branding system (`backend/app/services/email_branding.py`) loads values from three sources in priority order:

| Priority | Source | When Used |
|----------|--------|-----------|
| 1 (highest) | `white_label_configs` table | Multi-tenant: per-company branding |
| 2 | Environment variables (`VITE_*`) | Single-tenant or default branding |
| 3 (lowest) | Hardcoded defaults | Fallback when nothing is configured |

### What Gets Branded in Emails

| Element | Source Variable | Default |
|---------|----------------|---------|
| App name in header | `VITE_APP_NAME` / `app_name` | Time Tracker |
| Header background color | `VITE_PRIMARY_COLOR` / `primary_color` | `#2563eb` |
| Logo in header | `VITE_LOGO_URL` / `logo_url` | (none — text only) |
| Footer company name | `VITE_COMPANY_NAME` / `company_name` | (none) |
| Support email in footer | `VITE_SUPPORT_EMAIL` / `support_email` | (none) |
| Terms link in footer | `VITE_TERMS_URL` / `terms_url` | (none) |
| Privacy link in footer | `VITE_PRIVACY_URL` / `privacy_url` | (none) |

### Email Templates Available

| Template | Trigger | Key Variables |
|----------|---------|---------------|
| Welcome | New user created via Staff wizard | `user_name`, `user_email`, `temp_password` |
| Password Reset | User requests reset | `user_name`, `reset_url`, `expiry_minutes` |
| Account Request | Public registration | `requester_name`, `requester_email`, `requester_company` |
| Account Approved | Admin approves request | `user_name`, `login_url` |
| Account Rejected | Admin rejects request | `user_name` |

### Testing Email Branding

```bash
cd backend
pytest tests/test_email_branding.py -v
```

The tests verify that:
- Custom branding values appear in rendered emails (not defaults)
- Missing logo URLs produce no `<img>` tag
- Footer links only appear when URLs are configured
- Database branding overrides environment variables
- Template rendering gracefully handles missing variables

---

## Related Files

- `frontend/src/config/branding.ts` - Frontend branding configuration
- `backend/app/services/email_branding.py` - Email template branding service
- `frontend/.env.local` - Local development variables
- `frontend/.env.example` - Example environment template
- `frontend/public/logo.svg` - Default logo
- `frontend/public/manifest.json` - PWA manifest
- `clients/template/.env.template` - Full client config template

---

*Document updated: February 12, 2026*
