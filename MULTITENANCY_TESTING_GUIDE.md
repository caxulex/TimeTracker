# Multi-Tenancy & White-Label Testing Guide

## Overview

This guide walks you through testing the new multi-tenancy and white-label features implemented for TimeTracker. These features allow you to register separate companies with custom branding.

## Test Company: XYZ Corp

A test company "XYZ Corp" has been configured with the following details:

### Company Information
- **Name**: XYZ Corp
- **Slug**: `xyz-corp`
- **Email**: shaeadam@gmail.com
- **Subscription**: Professional (trial)
- **Status**: Active

### White-Label Branding
- **App Name**: XYZ Time
- **Tagline**: "Track Time Like a Pro"
- **Primary Color**: #7c3aed (Purple)
- **Secondary Color**: #4f46e5 (Indigo)
- **Accent Color**: #f97316 (Orange)
- **Show Powered By**: No (hidden)

---

## Step 1: Run Database Migration

Before testing, you need to apply the database migration that creates the companies and white_label_configs tables.

### Using Docker:
```bash
cd backend
docker compose exec backend alembic upgrade head
```

### Using Local Environment:
```bash
cd backend
alembic upgrade head
```

This migration:
- Creates the `companies` table
- Creates the `white_label_configs` table
- Adds `company_id` column to `users` table

---

## Step 2: Seed XYZ Corp Test Data

Run the seed script to create XYZ Corp with its branding and users:

### Using Docker:
```bash
docker compose exec backend python -m scripts.seed_xyz_corp
```

### Using Local Environment:
```bash
cd backend
python -m scripts.seed_xyz_corp
```

Expected output:
```
============================================================
XYZ Corp Seed Script
============================================================

📦 Creating XYZ Corp company...
   ✓ Company created (ID: 1)

🎨 Creating white-label branding...
   ✓ Branding created
      App Name: XYZ Time
      Primary Color: #7c3aed
      Subdomain: xyz-corp

👤 Creating admin user...
   ✓ Admin user created

👥 Creating sample employee...
   ✓ Employee created

============================================================
✅ XYZ CORP SEEDED SUCCESSFULLY!
============================================================

📋 LOGIN CREDENTIALS:
----------------------------------------
Admin Account:
   Email: shaeadam@gmail.com
   Password: XyzTest123!
   Role: company_admin

Employee Account:
   Email: employee@xyzcorp.com
   Password: Employee123!
   Role: employee
```

---

## Step 3: Test API Endpoints

### Test Company Branding API (Public)
```bash
# Get XYZ Corp branding configuration
curl http://localhost:8000/api/companies/branding/xyz-corp
```

Expected response:
```json
{
  "id": 1,
  "company_id": 1,
  "app_name": "XYZ Time",
  "company_name": "XYZ Corp",
  "tagline": "Track Time Like a Pro",
  "subdomain": "xyz-corp",
  "primary_color": "#7c3aed",
  "secondary_color": "#4f46e5",
  "accent_color": "#f97316",
  "show_powered_by": false,
  ...
}
```

### Test Company Info API (Public)
```bash
# Get XYZ Corp company info
curl http://localhost:8000/api/companies/by-slug/xyz-corp
```

Expected response:
```json
{
  "id": 1,
  "name": "XYZ Corp",
  "slug": "xyz-corp",
  "email": "shaeadam@gmail.com",
  "subscription_tier": "professional",
  "status": "active",
  "max_users": 100,
  "max_projects": 500,
  ...
}
```

### Test Company Registration API
```bash
# Register a new company
curl -X POST http://localhost:8000/api/companies/register \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Company",
    "admin_email": "admin@testcompany.com",
    "admin_password": "TestPass123!",
    "admin_name": "Test Admin"
  }'
```

---

## Step 4: Test White-Label Login Page

### Access XYZ Corp Login
Open your browser and navigate to:

```
http://localhost:5173/login?company=xyz-corp
```

You should see:
1. ✅ **Purple theme** instead of default blue
2. ✅ **"XYZ Time"** as the app name
3. ✅ **"Track Time Like a Pro"** tagline
4. ✅ **"XYZ Corp"** in the footer
5. ✅ **No "Powered by Time Tracker"** text

### Login with XYZ Corp Admin
- **Email**: shaeadam@gmail.com
- **Password**: XyzTest123!

### Login with XYZ Corp Employee
- **Email**: employee@xyzcorp.com
- **Password**: Employee123!

---

## Step 5: Test Authenticated Endpoints

After logging in, test the authenticated company endpoints:

### Get My Company (Authenticated)
```bash
# Replace TOKEN with actual access token from login
curl http://localhost:8000/api/companies/my-company \
  -H "Authorization: Bearer TOKEN"
```

### Get My Company Branding (Authenticated)
```bash
curl http://localhost:8000/api/companies/my-company/branding \
  -H "Authorization: Bearer TOKEN"
```

### Update Company Branding (Company Admin Only)
```bash
curl -X PUT http://localhost:8000/api/companies/my-company/branding \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tagline": "Time Tracking Made Simple",
    "primary_color": "#059669"
  }'
```

---

## Step 6: Compare Default vs White-Labeled Login

### Default Login (No company)
```
http://localhost:5173/login
```
- Blue theme (#2563eb)
- "Time Tracker" app name
- Shows "Powered by Time Tracker"

### XYZ Corp Login
```
http://localhost:5173/login?company=xyz-corp
```
- Purple theme (#7c3aed)
- "XYZ Time" app name
- No "Powered by" text

---

## API Reference

### Public Endpoints (No Auth Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/companies/register` | Register new company |
| GET | `/api/companies/by-slug/{slug}` | Get company by slug |
| GET | `/api/companies/branding/{slug}` | Get branding config |
| GET | `/api/companies/branding/by-domain/{domain}` | Get branding by domain |

### Authenticated Endpoints

| Method | Endpoint | Description | Required Role |
|--------|----------|-------------|---------------|
| GET | `/api/companies/my-company` | Get current user's company | Any |
| PUT | `/api/companies/my-company` | Update company settings | company_admin |
| GET | `/api/companies/my-company/branding` | Get company branding | Any |
| PUT | `/api/companies/my-company/branding` | Update branding | company_admin |
| GET | `/api/companies/list` | List all companies | super_admin |

---

## Database Schema

### Companies Table
```sql
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    subscription_tier VARCHAR(20) DEFAULT 'trial',
    status VARCHAR(20) DEFAULT 'trial',
    trial_ends_at TIMESTAMP,
    max_users INTEGER DEFAULT 10,
    max_projects INTEGER DEFAULT 20,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### White Label Configs Table
```sql
CREATE TABLE white_label_configs (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    app_name VARCHAR(100) DEFAULT 'Time Tracker',
    company_name VARCHAR(255),
    tagline VARCHAR(255),
    subdomain VARCHAR(100) UNIQUE,
    custom_domain VARCHAR(255) UNIQUE,
    logo_url TEXT,
    favicon_url TEXT,
    login_background_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#2563eb',
    secondary_color VARCHAR(7),
    accent_color VARCHAR(7),
    support_email VARCHAR(255),
    support_url TEXT,
    terms_url TEXT,
    privacy_url TEXT,
    show_powered_by BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Troubleshooting

### Migration Fails
```bash
# Check migration status
alembic current
alembic history

# If needed, manually run the migration
alembic upgrade 010
```

### Seed Script Fails
```bash
# Check if company already exists
curl http://localhost:8000/api/companies/by-slug/xyz-corp

# If exists, you can delete via SQL:
# DELETE FROM users WHERE company_id = 1;
# DELETE FROM white_label_configs WHERE company_id = 1;
# DELETE FROM companies WHERE slug = 'xyz-corp';
```

### Branding Not Loading
1. Check browser console for errors
2. Verify API is returning data: `curl http://localhost:8000/api/companies/branding/xyz-corp`
3. Clear localStorage: `localStorage.removeItem('tt_branding_config')`
4. Hard refresh the page (Ctrl+Shift+R)

### Colors Not Applying
Check that CSS custom properties are being set:
```javascript
// In browser console
document.documentElement.style.getPropertyValue('--color-primary')
```

---

## Next Steps

1. **Production Deployment**: Update allowed origins in CORS settings
2. **Custom Domains**: Configure DNS and nginx for custom domain routing
3. **File Uploads**: Add logo upload functionality
4. **Email Templates**: Brand email notifications per company
5. **Billing Integration**: Connect subscription_tier to payment system

---

## Files Modified/Created

### Backend
- `backend/app/models/__init__.py` - Added Company, WhiteLabelConfig models
- `backend/app/routers/companies.py` - Company/branding API endpoints
- `backend/app/main.py` - Router registration
- `backend/alembic/versions/010_add_company_multitenancy.py` - Migration
- `backend/scripts/seed_xyz_corp.py` - Test data seeder

### Frontend
- `frontend/src/services/brandingService.ts` - Branding API service
- `frontend/src/contexts/BrandingContext.tsx` - React context
- `frontend/src/pages/LoginPage.tsx` - Dynamic branding
- `frontend/src/App.tsx` - BrandingProvider wrapper
