# Email Configuration Guide

**Last Updated:** January 6, 2026

This guide explains how to configure email notifications for TimeTracker.

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration Variables](#configuration-variables)
3. [SMTP Providers](#smtp-providers)
4. [Testing Email](#testing-email)
5. [Email Templates](#email-templates)
6. [Troubleshooting](#troubleshooting)

---

## Overview

TimeTracker uses SMTP to send transactional emails for:

| Email Type | Trigger | Recipients |
|------------|---------|------------|
| **Account Request Notification** | New account request submitted | All super admins |
| **Account Approved** | Admin approves account request | Applicant |
| **Account Rejected** | Admin rejects account request | Applicant |
| **Password Reset** | User requests password reset | User |
| **Welcome Email** | New user created | New user |
| **Payroll Notification** | Payroll processed | Affected users |
| **Time Entry Reminder** | Missing time entries | User |

---

## Configuration Variables

Add these to your `.env.production` file:

```env
# ========== Email Configuration ==========
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=your_app_password_here
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Time Tracker
SMTP_USE_TLS=true
```

### Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_SERVER` | Yes | None | SMTP server hostname |
| `SMTP_PORT` | No | 587 | SMTP port (587 for TLS, 465 for SSL) |
| `SMTP_USERNAME` | Yes | None | SMTP authentication username |
| `SMTP_PASSWORD` | Yes | None | SMTP authentication password |
| `SMTP_FROM_EMAIL` | No | `SMTP_USERNAME` | "From" email address |
| `SMTP_FROM_NAME` | No | "Time Tracker" | Display name for sender |
| `SMTP_USE_TLS` | No | true | Use STARTTLS encryption |

---

## SMTP Providers

### Amazon SES (Recommended for AWS)

```env
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=YOUR_SES_SMTP_USERNAME
SMTP_PASSWORD=YOUR_SES_SMTP_PASSWORD
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Time Tracker
```

**Setup:**
1. Verify your domain in SES
2. Request production access (sandbox has limitations)
3. Create SMTP credentials in SES console
4. Add verified email addresses

### Gmail / Google Workspace

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=Time Tracker
```

**Setup:**
1. Enable 2-factor authentication
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Use the App Password (not your regular password)

⚠️ **Note:** Gmail has daily sending limits (500/day personal, 2000/day Workspace)

### Microsoft 365

```env
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yourdomain.com
SMTP_PASSWORD=your_password
SMTP_FROM_EMAIL=your-email@yourdomain.com
SMTP_FROM_NAME=Time Tracker
```

### SendGrid

```env
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your_sendgrid_api_key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Time Tracker
```

### Mailgun

```env
SMTP_SERVER=smtp.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=postmaster@yourdomain.com
SMTP_PASSWORD=your_mailgun_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Time Tracker
```

### Self-Hosted (Postfix)

```env
SMTP_SERVER=mail.yourdomain.com
SMTP_PORT=587
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=your_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=Time Tracker
```

---

## Testing Email

### Quick Test Script

Create a test script to verify email configuration:

```python
#!/usr/bin/env python3
"""Test email configuration"""

import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.email_service import email_service

async def test_email():
    if not email_service.is_configured:
        print("❌ Email is not configured!")
        print("   Set SMTP_SERVER, SMTP_USERNAME, and SMTP_PASSWORD")
        return False
    
    print(f"✅ Email configured:")
    print(f"   Server: {email_service.smtp_server}:{email_service.smtp_port}")
    print(f"   From: {email_service.from_name} <{email_service.from_email}>")
    
    # Try sending a test email
    test_email = input("Enter test email address: ").strip()
    if test_email:
        try:
            await email_service.send_email(
                to_email=test_email,
                subject="TimeTracker Email Test",
                body_html="<h1>Test Successful!</h1><p>Email is working correctly.</p>",
                body_text="Test Successful! Email is working correctly."
            )
            print(f"✅ Test email sent to {test_email}")
            return True
        except Exception as e:
            print(f"❌ Failed to send: {e}")
            return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_email())
```

### Test from Docker Container

```bash
# Enter the backend container
docker compose exec backend bash

# Run Python test
python -c "
from app.services.email_service import email_service
print('Configured:', email_service.is_configured)
print('Server:', email_service.smtp_server)
"
```

---

## Email Templates

Emails are generated using inline HTML templates within the EmailService. Each email type has:

- **HTML version** - Rich formatting with branding colors
- **Plain text fallback** - For email clients that don't support HTML

### Customizing Templates

The email templates are defined in:
```
backend/app/services/email_service.py
```

Each template method (e.g., `send_welcome_email`, `send_password_reset_email`) contains:
- `body_html` - The HTML template
- `body_text` - Plain text version

### Branding Integration

Templates use:
- `self.from_name` - Your configured app name (SMTP_FROM_NAME)
- Primary color `#2563eb` - Matches default theme

To customize for your brand:
1. Modify the color values in the HTML templates
2. Update `SMTP_FROM_NAME` in environment

### Future: Jinja2 Templates

For more advanced customization, the service supports Jinja2 templates:

1. Create directory: `backend/app/templates/email/`
2. Add templates: `welcome.html`, `password_reset.html`, etc.
3. Service will automatically use file templates when present

---

## Troubleshooting

### Common Issues

#### "Email not configured - skipping send"

**Cause:** Missing SMTP configuration  
**Fix:** Set `SMTP_SERVER`, `SMTP_USERNAME`, and `SMTP_PASSWORD` in your environment

#### "Connection refused"

**Cause:** Wrong port or server  
**Fix:** Verify `SMTP_SERVER` and `SMTP_PORT` values. Try port 587 or 465.

#### "Authentication failed"

**Cause:** Wrong credentials or app passwords required  
**Fix:** 
- For Gmail: Use App Passwords, not regular password
- For Microsoft: Check if modern auth is required
- For SES: Use SMTP credentials (different from IAM credentials)

#### "Sender address rejected"

**Cause:** From address not verified/authorized  
**Fix:**
- SES: Verify the sender email address or domain
- Others: Ensure `SMTP_FROM_EMAIL` matches an authorized sender

#### Emails going to spam

**Fix:**
1. Set up SPF record: `v=spf1 include:_spf.google.com ~all`
2. Configure DKIM signing
3. Set up DMARC policy
4. Use a verified domain (not free email providers)

### Debug Logging

Enable debug logging to see SMTP communication:

```env
LOG_LEVEL=DEBUG
```

Check logs:
```bash
docker compose logs backend | grep -i email
```

---

## Security Best Practices

1. **Never commit credentials** - Use environment variables
2. **Use App Passwords** - Never use account passwords for SMTP
3. **Enable TLS** - Always use `SMTP_USE_TLS=true`
4. **Limit sender scope** - Create dedicated email accounts for sending
5. **Monitor sending** - Track bounce rates and delivery issues
6. **Rate limit** - The email service doesn't queue; implement if needed

---

## Email Service API

The `EmailService` class provides these methods:

```python
from app.services.email_service import email_service

# Send raw email
await email_service.send_email(
    to_email="user@example.com",
    subject="Subject",
    body_html="<h1>HTML</h1>",
    body_text="Plain text"
)

# Send templated emails
await email_service.send_welcome_email(to_email, user_name, login_url)
await email_service.send_password_reset_email(to_email, user_name, reset_url)
await email_service.send_account_request_notification(admin_email, requester_name, requester_email)
await email_service.send_account_approved_email(to_email, user_name, temp_password, login_url)
await email_service.send_account_rejected_email(to_email, user_name, reason)
await email_service.send_time_entry_reminder(to_email, user_name, missing_date)
await email_service.send_payroll_processed_notification(to_email, user_name, period, hours, amount)

# Check if configured
if email_service.is_configured:
    # Email is ready
```

---

## Summary Checklist

- [ ] Choose an SMTP provider
- [ ] Set up SMTP credentials
- [ ] Add configuration to `.env.production`
- [ ] Test email delivery
- [ ] Verify emails not going to spam
- [ ] Set up SPF/DKIM/DMARC (production)
- [ ] Monitor delivery rates
