# Session Report - January 20, 2026 (Monday)

## 🎯 Session Goal: Email/SMTP Integration Feature

**Session Focus:** Configure SMTP email sending with white-label support  
**Previous Session:** SESSION_REPORT_JAN_19_2026.md (Burnout Fix + Team Timesheet)  
**Environment:** Production (AWS Lightsail)  
**URL:** https://timetracker.shaemarcus.com

---

## ✅ SESSION STATUS: IMPLEMENTATION COMPLETE ✅

### Summary
All 15 tasks have been completed. The email/SMTP integration feature is now fully implemented with:
- Database schema for per-company SMTP settings
- Backend API endpoints for email configuration and testing
- Company-aware email service with fallback to environment variables
- Report email sending with attachment support (PDF, Excel, CSV)
- Admin UI for configuring email settings
- Email Report modal for sending reports to recipients

---

## 🎉 COMPLETED TASKS

| # | Task | Status |
|---|------|--------|
| 1 | Create migration file (013_add_email_settings.py) | ✅ |
| 2 | Update Company model with SMTP fields | ✅ |
| 3 | Create email settings schemas | ✅ |
| 4 | Create GET email settings endpoint | ✅ |
| 5 | Create PUT email settings endpoint | ✅ |
| 6 | Create test email endpoint | ✅ |
| 7 | Add company-aware email method | ✅ |
| 8 | Add email with attachment method | ✅ |
| 9 | Create email report endpoint | ✅ |
| 10 | Add frontend API client methods | ✅ |
| 11 | Create EmailSettingsForm component | ✅ |
| 12 | Add Email tab to Admin Settings | ✅ |
| 13 | Create EmailReportModal component | ✅ |
| 14 | Add email button to Reports page | ✅ |
| 15 | Migration file ready | ✅ |

---

## 📁 FILES MODIFIED/CREATED

### Backend
| File | Change |
|------|--------|
| `backend/alembic/versions/013_add_email_settings.py` | **NEW** - Migration for SMTP columns |
| `backend/app/models/__init__.py` | Added 8 SMTP fields to Company |
| `backend/app/routers/companies.py` | Added 3 email settings endpoints |
| `backend/app/services/email_service.py` | Added company-aware email methods |
| `backend/app/routers/reports.py` | Added email report endpoint |

### Frontend
| File | Change |
|------|--------|
| `frontend/src/api/client.ts` | Added email settings types and API methods |
| `frontend/src/components/settings/EmailSettingsForm.tsx` | **NEW** - SMTP config form |
| `frontend/src/components/settings/index.ts` | **NEW** - Export index |
| `frontend/src/components/reports/EmailReportModal.tsx` | **NEW** - Email report modal |
| `frontend/src/components/reports/index.ts` | Added EmailReportModal export |
| `frontend/src/pages/AdminSettingsPage.tsx` | Added Email Settings tab |
| `frontend/src/components/reports/TeamTimesheetReport.tsx` | Added email button |

---

## 🚀 DEPLOYMENT INSTRUCTIONS

### 1. Run Database Migration
```bash
cd backend
alembic upgrade head
```

### 2. Verify New Endpoints
- `GET /api/companies/my-company/email-settings`
- `PUT /api/companies/my-company/email-settings`
- `POST /api/companies/my-company/email-settings/test`
- `POST /api/reports/email`

### 3. Test the Feature
1. Go to **Admin Settings** → **Email Settings** tab
2. Configure SMTP settings
3. Send a test email
4. Go to **Team Timesheet Report**
5. Click **Email Report** button
6. Enter recipients and send

---

## 📋 Feature Request Summary

The user wants to implement email functionality across the platform:

1. **SMTP Configuration** - Use provided credentials for email sending ✅
2. **Reports via Email** - Send reports (time reports, team timesheets) via email ✅
3. **Account Request Notifications** - Email users when account is approved/rejected ✅ (already existed)
4. **Admin Email Settings** - UI to configure SMTP for white-label support ✅
5. **Other Email Features** - Identify additional opportunities for email notifications

### 3. Email Service Enhancement

```python
# Enhanced EmailService that respects company branding

class EmailService:
    async def send_email_for_company(
        self,
        company_id: int,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        db: AsyncSession
    ) -> bool:
        """Send email using company-specific SMTP settings"""
        # 1. Fetch company SMTP config
        # 2. Decrypt password if encrypted
        # 3. Use company branding (from_name, from_email)
        # 4. Fall back to env vars if company has no SMTP
        pass
```

---

### 4. API Endpoints Design

#### GET /api/companies/my-company/email-settings
```json
{
  "email_enabled": true,
  "smtp_server": "smtp.example.com",
  "smtp_port": 587,
  "smtp_username": "user@example.com",
  "smtp_password_set": true,  // Don't expose actual password
  "smtp_from_email": "noreply@company.com",
  "smtp_from_name": "Company Time Tracker",
  "smtp_use_tls": true
}
```

#### PUT /api/companies/my-company/email-settings
```json
{
  "smtp_server": "smtp.example.com",
  "smtp_port": 587,
  "smtp_username": "user@example.com",
  "smtp_password": "new-password",  // Only if changing
  "smtp_from_email": "noreply@company.com",
  "smtp_from_name": "Company Time Tracker",
  "smtp_use_tls": true,
  "email_enabled": true
}
```

#### POST /api/companies/my-company/email-settings/test
```json
{
  "test_recipient": "admin@company.com"
}
```
Response:
```json
{
  "success": true,
  "message": "Test email sent successfully",
  "latency_ms": 1250
}
```

#### POST /api/reports/email
```json
{
  "report_type": "time_report",  // or "team_timesheet", "payroll_summary"
  "start_date": "2026-01-01",
  "end_date": "2026-01-15",
  "recipients": ["manager@company.com", "hr@company.com"],
  "format": "pdf",  // or "excel", "csv"
  "include_charts": true
}
```

---

## 📧 EMAIL FEATURE OPPORTUNITIES

### Currently Supported (Backend Ready)
| Feature | Method | Button Needed |
|---------|--------|---------------|
| Account Approved | `send_account_approved_email()` | Auto-send ✅ |
| Account Rejected | `send_account_rejected_email()` | Auto-send ✅ |
| New Account Request | `send_account_request_notification()` | Auto-send ✅ |
| Password Reset | `send_password_reset_email()` | Forgot Password page |
| Welcome Email | `send_welcome_email()` | On user creation |
| Time Entry Reminder | `send_time_entry_reminder()` | Scheduler needed |
| Payroll Processed | `send_payroll_processed_notification()` | Payroll page |

### New Features to Build
| Feature | Description | Priority |
|---------|-------------|----------|
| **Email Time Report** | Send PDF/Excel report to email | 🔴 HIGH |
| **Email Team Timesheet** | Send team timesheet to managers | 🔴 HIGH |
| **Weekly Summary Email** | Auto-send weekly hours summary | 🟡 MEDIUM |
| **Project Deadline Alert** | Email when project nears deadline | 🟡 MEDIUM |
| **Burnout Risk Alert** | Email when employee burnout detected | 🟡 MEDIUM |
| **Overtime Alert** | Email when user exceeds X hours | 🟢 LOW |
| **Inactive User Alert** | Email admins about inactive users | 🟢 LOW |

---

## 🎨 FRONTEND UI DESIGN

### Admin Settings Page - Email Tab

```
┌─────────────────────────────────────────────────────────────┐
│ Admin Settings                                               │
├─────────────────────────────────────────────────────────────┤
│ [🔑 API Keys] [🤖 AI Features] [📧 Email Settings]          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 📧 Email Configuration                                       │
│ ─────────────────────────────────────────────────────────── │
│                                                              │
│ ┌─ Enable Email ─────────────────────────────────────────┐ │
│ │ [🔘 ON] Email notifications are enabled                 │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ SMTP Server Settings ─────────────────────────────────┐ │
│ │ SMTP Server:    [smtp.gmail.com________________]        │ │
│ │ Port:           [587_____]                              │ │
│ │ Username:       [noreply@company.com___________]        │ │
│ │ Password:       [••••••••••••] [👁]                     │ │
│ │ Use TLS:        [✓]                                     │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ Sender Identity (White-Label) ────────────────────────┐ │
│ │ From Name:      [Company Time Tracker__________]        │ │
│ │ From Email:     [noreply@company.com___________]        │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ Test Configuration ───────────────────────────────────┐ │
│ │ Send test email to: [admin@company.com_________]        │ │
│ │ [📤 Send Test Email]                                    │ │
│ │                                                          │ │
│ │ ✅ Last test: Success (1.2s) - Jan 20, 2026 10:30 AM    │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                              │
│                              [💾 Save Settings]              │
└─────────────────────────────────────────────────────────────┘
```

### Reports Page - Email Button

```
┌─────────────────────────────────────────────────────────────┐
│ Reports                                    [📊 Export ▼]    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Date Range: [Jan 1, 2026] to [Jan 15, 2026]  [Apply]        │
│                                                              │
│ ┌─ Export Options ───────────────────────────────────────┐ │
│ │ 📥 Download PDF                                         │ │
│ │ 📥 Download Excel                                       │ │
│ │ 📥 Download CSV                                         │ │
│ │ ────────────────────────                               │ │
│ │ 📧 Email Report...                                      │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Email Report Modal

```
┌─────────────────────────────────────────────────────────────┐
│ 📧 Email Report                                        [✕] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Recipients (comma-separated):                                │
│ [manager@company.com, hr@company.com________________]        │
│                                                              │
│ Format:  ○ PDF  ● Excel  ○ CSV                              │
│                                                              │
│ Include:                                                     │
│ [✓] Summary statistics                                       │
│ [✓] Detailed breakdown                                       │
│ [ ] Charts and graphs                                        │
│                                                              │
│ Custom Message (optional):                                   │
│ ┌──────────────────────────────────────────────────────────┐│
│ │ Please find attached the time report for January...      ││
│ └──────────────────────────────────────────────────────────┘│
│                                                              │
│                        [Cancel] [📧 Send Report]             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗂️ IMPLEMENTATION PLAN - DETAILED TODO LIST

> **Instructions:** Work through tasks sequentially. Mark each `[ ]` as `[x]` when complete.
> After completing each task, verify it works before moving to the next.

---

### 📦 PHASE 1: DATABASE MIGRATION (30 min)

#### Task 1.1: Create Migration File
- [ ] **Create file:** `backend/alembic/versions/017_add_email_settings.py`
- [ ] **Add columns to `companies` table:**
  - `smtp_server` VARCHAR(255) nullable
  - `smtp_port` INTEGER default 587
  - `smtp_username` VARCHAR(255) nullable
  - `smtp_password_encrypted` TEXT nullable
  - `smtp_from_email` VARCHAR(255) nullable
  - `smtp_from_name` VARCHAR(255) nullable
  - `smtp_use_tls` BOOLEAN default true
  - `email_enabled` BOOLEAN default false
- [ ] **Verify migration syntax** with `py_compile`

#### Task 1.2: Update Company Model
- [ ] **Edit file:** `backend/app/models/__init__.py`
- [ ] **Add SMTP fields to `Company` class** (after timezone field ~line 115)
- [ ] **Verify model syntax** with `py_compile`

#### Task 1.3: Run Migration Locally (Optional)
- [ ] **Test migration:** `alembic upgrade head`
- [ ] **Verify columns exist** in database

---

### 🔧 PHASE 2: BACKEND EMAIL SETTINGS API (2 hours)

#### Task 2.1: Create Email Settings Schemas
- [ ] **Edit file:** `backend/app/routers/companies.py`
- [ ] **Add `EmailSettingsResponse` schema:**
  ```python
  class EmailSettingsResponse(BaseModel):
      email_enabled: bool
      smtp_server: Optional[str]
      smtp_port: int
      smtp_username: Optional[str]
      smtp_password_set: bool  # True if password exists, never expose actual
      smtp_from_email: Optional[str]
      smtp_from_name: Optional[str]
      smtp_use_tls: bool
  ```
- [ ] **Add `EmailSettingsUpdate` schema:**
  ```python
  class EmailSettingsUpdate(BaseModel):
      email_enabled: Optional[bool] = None
      smtp_server: Optional[str] = None
      smtp_port: Optional[int] = None
      smtp_username: Optional[str] = None
      smtp_password: Optional[str] = None  # Only when changing
      smtp_from_email: Optional[str] = None
      smtp_from_name: Optional[str] = None
      smtp_use_tls: Optional[bool] = None
  ```
- [ ] **Add `TestEmailRequest` schema:**
  ```python
  class TestEmailRequest(BaseModel):
      recipient: EmailStr
  ```
- [ ] **Verify syntax** with `py_compile`

#### Task 2.2: Create GET Email Settings Endpoint
- [ ] **Add endpoint:** `GET /api/companies/my-company/email-settings`
- [ ] **Require admin role** (company_admin or higher)
- [ ] **Return `EmailSettingsResponse`** with `smtp_password_set` flag
- [ ] **Verify syntax** with `py_compile`

#### Task 2.3: Create PUT Email Settings Endpoint
- [ ] **Add endpoint:** `PUT /api/companies/my-company/email-settings`
- [ ] **Require admin role**
- [ ] **Encrypt password** if provided using `encrypt_api_key()` from utils
- [ ] **Update company record** with new settings
- [ ] **Return updated `EmailSettingsResponse`**
- [ ] **Verify syntax** with `py_compile`

#### Task 2.4: Create Test Email Endpoint
- [ ] **Add endpoint:** `POST /api/companies/my-company/email-settings/test`
- [ ] **Accept `TestEmailRequest`** with recipient email
- [ ] **Use company SMTP settings** to send test email
- [ ] **Return success/failure** with latency
- [ ] **Verify syntax** with `py_compile`

#### Task 2.5: Import Encryption Utilities
- [ ] **Add import** for encryption functions in companies.py
- [ ] **Verify** `encrypt_api_key` and `decrypt_api_key` exist in utils
- [ ] **Verify syntax** with `py_compile`

---

### 📧 PHASE 3: ENHANCED EMAIL SERVICE (2 hours)

#### Task 3.1: Add Company-Aware Email Method
- [ ] **Edit file:** `backend/app/services/email_service.py`
- [ ] **Add method `send_email_for_company()`:**
  - Accept `company_id`, `to_email`, `subject`, `body_html`, `body_text`, `db`
  - Fetch company from database
  - Use company SMTP if configured, else fall back to env vars
  - Decrypt company SMTP password
  - Apply company branding (from_name, from_email)
- [ ] **Verify syntax** with `py_compile`

#### Task 3.2: Add SMTP Connection Factory
- [ ] **Add method `_get_smtp_connection()`:**
  - Accept optional company SMTP config
  - Return configured SMTP connection
  - Handle both company and env-based configs
- [ ] **Verify syntax** with `py_compile`

#### Task 3.3: Update Existing Email Methods
- [ ] **Update `send_welcome_email()`** to optionally use company branding
- [ ] **Update `send_account_approved_email()`** to use company branding
- [ ] **Update `send_account_rejected_email()`** to use company branding
- [ ] **Verify syntax** with `py_compile`

#### Task 3.4: Add Email Templates with Company Branding
- [ ] **Create method `_get_branded_template()`:**
  - Accept company white-label config
  - Return HTML template with company colors/logo
- [ ] **Update email HTML** to use company primary_color
- [ ] **Verify syntax** with `py_compile`

---

### 📊 PHASE 4: EMAIL REPORT FEATURE (3 hours)

#### Task 4.1: Create Email Report Schemas
- [ ] **Edit file:** `backend/app/routers/reports.py`
- [ ] **Add `EmailReportRequest` schema:**
  ```python
  class EmailReportRequest(BaseModel):
      report_type: str  # "time_report", "team_timesheet", "payroll_summary"
      start_date: date
      end_date: date
      recipients: List[EmailStr]
      format: str = "pdf"  # "pdf", "excel", "csv"
      custom_message: Optional[str] = None
  ```
- [ ] **Add `EmailReportResponse` schema:**
  ```python
  class EmailReportResponse(BaseModel):
      success: bool
      message: str
      recipients_sent: int
      recipients_failed: int
  ```
- [ ] **Verify syntax** with `py_compile`

#### Task 4.2: Create Email Report Endpoint
- [ ] **Add endpoint:** `POST /api/reports/email`
- [ ] **Require admin role**
- [ ] **Validate report_type** is one of allowed values
- [ ] **Generate report** using existing export functions
- [ ] **Send email with attachment** to each recipient
- [ ] **Return `EmailReportResponse`**
- [ ] **Verify syntax** with `py_compile`

#### Task 4.3: Add Report Generation Helper
- [ ] **Create method `_generate_report_attachment()`:**
  - Accept report_type, date range, format, user
  - Call existing PDF/Excel/CSV generators
  - Return bytes and filename
- [ ] **Verify syntax** with `py_compile`

#### Task 4.4: Add Email with Attachment Method
- [ ] **Edit file:** `backend/app/services/email_service.py`
- [ ] **Add method `send_email_with_attachment()`:**
  - Accept attachment bytes, filename, mimetype
  - Build MIME multipart message
  - Attach file to email
- [ ] **Verify syntax** with `py_compile`

---

### 🖥️ PHASE 5: FRONTEND EMAIL SETTINGS (3 hours)

#### Task 5.1: Add Email Settings API Client
- [ ] **Edit file:** `frontend/src/api/client.ts`
- [ ] **Add to `companiesApi`:**
  ```typescript
  getEmailSettings: () => api.get('/companies/my-company/email-settings'),
  updateEmailSettings: (data) => api.put('/companies/my-company/email-settings', data),
  testEmailSettings: (recipient) => api.post('/companies/my-company/email-settings/test', { recipient }),
  ```
- [ ] **Add TypeScript types** for email settings

#### Task 5.2: Create EmailSettingsForm Component
- [ ] **Create file:** `frontend/src/components/settings/EmailSettingsForm.tsx`
- [ ] **Add form fields:**
  - Email Enabled toggle
  - SMTP Server input
  - SMTP Port input
  - SMTP Username input
  - SMTP Password input (with show/hide)
  - From Email input
  - From Name input
  - Use TLS toggle
- [ ] **Add form validation**
- [ ] **Add save button with loading state**

#### Task 5.3: Add Test Email Section
- [ ] **Add to `EmailSettingsForm.tsx`:**
  - Test recipient input
  - Send Test Email button
  - Success/error message display
  - Loading state during test
- [ ] **Show last test result** (if available)

#### Task 5.4: Add Email Tab to AdminSettingsPage
- [ ] **Edit file:** `frontend/src/pages/AdminSettingsPage.tsx`
- [ ] **Add "📧 Email Settings" tab** to tab navigation
- [ ] **Import `EmailSettingsForm`** component
- [ ] **Render form** when email tab is active
- [ ] **Add React Query** for fetching/updating email settings

#### Task 5.5: Style and Polish
- [ ] **Add info boxes** explaining SMTP setup
- [ ] **Add links** to common SMTP provider docs
- [ ] **Add password visibility toggle**
- [ ] **Add success notifications** on save

---

### 📤 PHASE 6: FRONTEND EMAIL REPORT (2 hours)

#### Task 6.1: Add Email Report API Client
- [ ] **Edit file:** `frontend/src/api/client.ts`
- [ ] **Add to `reportsApi`:**
  ```typescript
  emailReport: (data) => api.post('/reports/email', data),
  ```

#### Task 6.2: Create EmailReportModal Component
- [ ] **Create file:** `frontend/src/components/reports/EmailReportModal.tsx`
- [ ] **Add form fields:**
  - Recipients input (comma-separated emails)
  - Format selector (PDF/Excel/CSV)
  - Custom message textarea (optional)
- [ ] **Add validation** for email addresses
- [ ] **Add send button** with loading state
- [ ] **Show success/error** result

#### Task 6.3: Add Email Button to ReportsPage
- [ ] **Edit file:** `frontend/src/pages/ReportsPage.tsx`
- [ ] **Add "📧 Email Report" option** to export dropdown
- [ ] **Import `EmailReportModal`** component
- [ ] **Add modal state** (open/close)
- [ ] **Pass current date range** to modal

#### Task 6.4: Add Email Button to Team Timesheet
- [ ] **Edit file:** `frontend/src/components/reports/TeamTimesheetReport.tsx`
- [ ] **Add "📧 Email Timesheet" button** next to export buttons
- [ ] **Open modal** with report_type="team_timesheet"

---

### ✉️ PHASE 7: AUTO-SEND IMPROVEMENTS (1 hour)

#### Task 7.1: Ensure Account Approval Sends Email
- [ ] **Edit file:** `backend/app/routers/account_requests.py`
- [ ] **Verify** `send_account_approved_email()` is called on approval
- [ ] **Add company context** to email sending
- [ ] **Log email send result**

#### Task 7.2: Ensure Account Rejection Sends Email
- [ ] **Verify** `send_account_rejected_email()` is called on rejection
- [ ] **Include rejection reason** in email
- [ ] **Log email send result**

#### Task 7.3: Add Email Status Indicator
- [ ] **Edit file:** `frontend/src/pages/AccountRequestsPage.tsx`
- [ ] **Add email icon** showing if notification was sent
- [ ] **Show tooltip** with send status/timestamp

#### Task 7.4: Add Welcome Email on User Creation
- [ ] **Edit file:** `backend/app/routers/users.py`
- [ ] **Send welcome email** when admin creates new user
- [ ] **Include login URL** in email

---

### 🧪 PHASE 8: TESTING & VERIFICATION (1 hour)

#### Task 8.1: Test Email Settings CRUD
- [ ] **Test GET** email settings returns correct data
- [ ] **Test PUT** updates settings correctly
- [ ] **Test password** is encrypted in database
- [ ] **Test password_set** flag works correctly

#### Task 8.2: Test Email Sending
- [ ] **Test** test email endpoint works
- [ ] **Test** email report endpoint works
- [ ] **Test** fallback to env vars when company SMTP not set
- [ ] **Test** emails have correct branding

#### Task 8.3: Test Frontend
- [ ] **Test** email settings form loads
- [ ] **Test** form saves correctly
- [ ] **Test** test email button works
- [ ] **Test** email report modal works

---

### 🚀 PHASE 9: DEPLOYMENT (30 min)

#### Task 9.1: Git Commit
- [ ] **Stage all changes**
- [ ] **Commit:** "feat: Email settings and report email feature"
- [ ] **Push to origin/master**

#### Task 9.2: Production Deployment
- [ ] **SSH to Lightsail**
- [ ] **Pull latest changes**
- [ ] **Run migration:** `docker compose exec backend alembic upgrade head`
- [ ] **Rebuild containers:** `./scripts/deploy-sequential.sh`
- [ ] **Verify deployment**

#### Task 9.3: Configure Production SMTP
- [ ] **Add SMTP env vars** to production .env (as fallback)
- [ ] **Configure company SMTP** via admin UI
- [ ] **Send test email** to verify

---

## 📋 TASK PROGRESS TRACKER

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Phase 1: Database | 3 | 0 | ⏳ Not Started |
| Phase 2: Backend API | 5 | 0 | ⏳ Not Started |
| Phase 3: Email Service | 4 | 0 | ⏳ Not Started |
| Phase 4: Email Reports | 4 | 0 | ⏳ Not Started |
| Phase 5: Frontend Settings | 5 | 0 | ⏳ Not Started |
| Phase 6: Frontend Reports | 4 | 0 | ⏳ Not Started |
| Phase 7: Auto-Send | 4 | 0 | ⏳ Not Started |
| Phase 8: Testing | 3 | 0 | ⏳ Not Started |
| Phase 9: Deployment | 3 | 0 | ⏳ Not Started |
| **TOTAL** | **35** | **0** | **0%** |

---

## 📝 ENVIRONMENT VARIABLES NEEDED

User needs to add these to production `.env`:

```env
# SMTP Configuration
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Time Tracker
SMTP_USE_TLS=true
```

### Common SMTP Providers

| Provider | Server | Port | Notes |
|----------|--------|------|-------|
| Gmail | smtp.gmail.com | 587 | Requires App Password |
| Outlook/O365 | smtp.office365.com | 587 | |
| SendGrid | smtp.sendgrid.net | 587 | Use API key as password |
| Amazon SES | email-smtp.{region}.amazonaws.com | 587 | IAM credentials |
| Mailgun | smtp.mailgun.org | 587 | |

---

## 🔒 SECURITY CONSIDERATIONS

1. **Password Encryption**: Store SMTP passwords encrypted in DB using existing `API_KEY_ENCRYPTION_KEY`
2. **Rate Limiting**: Limit email sends to prevent abuse (e.g., 100/hour per company)
3. **Email Validation**: Validate recipient emails before sending
4. **Audit Logging**: Log all email sends for security audit
5. **SPF/DKIM**: Document that customers should configure DNS for deliverability

---

## 📊 ESTIMATED EFFORT

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Migration | 30 min | None |
| Phase 2: Backend Settings | 2h | Phase 1 |
| Phase 3: Email Service | 2h | Phase 2 |
| Phase 4: Email Reports | 3h | Phase 3 |
| Phase 5: Frontend Settings | 3h | Phase 2 |
| Phase 6: Frontend Reports | 2h | Phase 4 |
| Phase 7: Auto-Send | 1h | Phase 3 |
| **TOTAL** | **~14 hours** | |

---

## 🚀 QUICK START FOR IMPLEMENTATION

### Step 1: User provides SMTP credentials
```
Please provide your SMTP credentials:
- SMTP Server: ________
- Port: 587
- Username: ________
- Password: ________
- From Email: ________
- From Name: ________
```

### Step 2: We implement in order
1. Backend migration + endpoints
2. Frontend settings UI
3. Email report feature
4. Testing and deployment

---

## 📁 FILES TO CREATE/MODIFY

### New Files
| File | Purpose |
|------|---------|
| `backend/alembic/versions/017_add_email_settings.py` | Migration |
| `frontend/src/components/settings/EmailSettingsForm.tsx` | Settings form |
| `frontend/src/components/reports/EmailReportModal.tsx` | Email modal |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/models/__init__.py` | Add SMTP fields to Company |
| `backend/app/routers/companies.py` | Email settings endpoints |
| `backend/app/services/email_service.py` | Company-aware sending |
| `frontend/src/pages/AdminSettingsPage.tsx` | Add Email tab |
| `frontend/src/pages/ReportsPage.tsx` | Add email button |
| `frontend/src/api/client.ts` | Email settings API methods |

---

## ✅ SESSION STATUS

| Item | Status |
|------|--------|
| Codebase Analysis | ✅ Complete |
| Architecture Design | ✅ Complete |
| Implementation Plan | ✅ Complete |
| Awaiting | 🔄 SMTP credentials from user |

---

## 🔮 NEXT STEPS

1. **User provides SMTP credentials** for `.env`
2. **Decide implementation priority:**
   - Start with backend + settings UI?
   - Or full feature including email reports?
3. **Begin Phase 1:** Database migration

---

*Session Date: January 20, 2026*  
*Focus: Email/SMTP Integration Assessment*  
*Status: ✅ ASSESSMENT COMPLETE - AWAITING USER INPUT*
