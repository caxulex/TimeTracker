"""
Email Template Branding Service
TASK 8.4: Ensures all email templates use configurable branding values
from white_label_configs table or environment variables.

Usage:
    from app.services.email_branding import get_email_branding, build_branded_email

    branding = await get_email_branding(db, company_id=1)
    html = build_branded_email("Welcome", body_content, branding)
"""

import logging
import os
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================
# DEFAULT BRANDING VALUES
# ============================================

DEFAULT_BRANDING = {
    "app_name": getattr(settings, "APP_NAME", "Time Tracker"),
    "company_name": "",
    "logo_url": "",
    "primary_color": "#2563eb",
    "support_email": getattr(settings, "SMTP_FROM_EMAIL", "")
    or getattr(settings, "SMTP_USERNAME", "")
    or "",
    "support_url": "",
    "terms_url": "",
    "privacy_url": "",
    "tagline": "",
}


async def get_email_branding(
    db: Optional[AsyncSession] = None,
    company_id: Optional[int] = None,
) -> dict:
    """
    Get branding values for email templates.

    Priority:
    1. Company-specific white_label_configs from database
    2. Environment variables (VITE_APP_NAME, etc.)
    3. Hardcoded defaults

    Returns:
        dict with keys: app_name, company_name, logo_url, primary_color,
                        support_email, support_url, terms_url, privacy_url, tagline
    """
    branding = dict(DEFAULT_BRANDING)

    # Override with environment-based VITE_* values if available
    env_overrides = {
        "app_name": os.environ.get("VITE_APP_NAME"),
        "company_name": os.environ.get("VITE_COMPANY_NAME"),
        "logo_url": os.environ.get("VITE_LOGO_URL"),
        "primary_color": os.environ.get("VITE_PRIMARY_COLOR"),
        "support_email": os.environ.get("VITE_SUPPORT_EMAIL"),
        "support_url": os.environ.get("VITE_SUPPORT_URL"),
        "terms_url": os.environ.get("VITE_TERMS_URL"),
        "privacy_url": os.environ.get("VITE_PRIVACY_URL"),
        "tagline": os.environ.get("VITE_TAGLINE"),
    }
    for key, val in env_overrides.items():
        if val:
            branding[key] = val

    # Override with database white_label_configs if available
    if db and company_id:
        try:
            from app.models import WhiteLabelConfig

            result = await db.execute(
                select(WhiteLabelConfig).where(
                    WhiteLabelConfig.company_id == company_id
                )
            )
            config = result.scalar_one_or_none()
            if config:
                db_overrides = {
                    "app_name": getattr(config, "app_name", None),
                    "company_name": getattr(config, "company_name", None),
                    "logo_url": getattr(config, "logo_url", None),
                    "primary_color": getattr(config, "primary_color", None),
                    "support_email": getattr(config, "support_email", None),
                    "support_url": getattr(config, "support_url", None),
                    "terms_url": getattr(config, "terms_url", None),
                    "privacy_url": getattr(config, "privacy_url", None),
                    "tagline": getattr(config, "tagline", None),
                }
                for key, val in db_overrides.items():
                    if val:
                        branding[key] = val
                logger.debug(
                    "Loaded email branding from white_label_configs for company %s",
                    company_id,
                )
        except Exception as e:
            logger.warning(
                "Could not load white_label_configs for company %s: %s. "
                "Using environment/default branding.",
                company_id,
                e,
            )

    return branding


class _BrandingSafeDict(dict):
    """Dict subclass that returns the key placeholder for missing keys."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_email_html(
    template_content: str,
    branding: dict,
    **context: object,
) -> str:
    """
    Render an email template string with branding and context variables.

    Uses simple {variable_name} substitution. Unrecognized placeholders
    are preserved rather than raising.

    Args:
        template_content: HTML template string with {placeholders}
        branding: dict from get_email_branding()
        **context: Additional template variables (user_name, reset_link, etc.)

    Returns:
        Rendered HTML string
    """
    all_vars = {**branding, **context}
    try:
        return template_content.format_map(_BrandingSafeDict(all_vars))
    except (KeyError, ValueError) as e:
        logger.error("Email template rendering error: %s", e)
        return template_content


# ============================================
# BASE EMAIL TEMPLATE
# ============================================

BASE_EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background-color: #f3f4f6;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background-color: {primary_color};
            padding: 24px;
            text-align: center;
        }}
        .header img {{
            max-height: 40px;
            margin-bottom: 8px;
        }}
        .header h1 {{
            color: #ffffff;
            margin: 0;
            font-size: 20px;
            font-weight: 600;
        }}
        .content {{
            padding: 32px 24px;
        }}
        .footer {{
            background-color: #f9fafb;
            padding: 16px 24px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #e5e7eb;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: {primary_color};
            color: #ffffff !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 500;
            margin: 16px 0;
        }}
    </style>
</head>
<body>
    <div style="padding: 24px;">
        <div class="container">
            <div class="header">
                {logo_html}
                <h1>{app_name}</h1>
            </div>
            <div class="content">
                {body_content}
            </div>
            <div class="footer">
                <p>&copy; {app_name}{company_suffix}</p>
                {footer_links}
                {support_line}
            </div>
        </div>
    </div>
</body>
</html>"""


def build_branded_email(
    subject: str,
    body_content: str,
    branding: dict,
) -> str:
    """
    Wrap body content in the branded base email template.

    Args:
        subject: Email subject (used in <title>)
        body_content: Inner HTML content
        branding: dict from get_email_branding()

    Returns:
        Complete HTML email string
    """
    logo_html = ""
    if branding.get("logo_url"):
        logo_html = (
            f'<img src="{branding["logo_url"]}" alt="{branding["app_name"]}" />'
        )

    company_suffix = ""
    if branding.get("company_name"):
        company_suffix = f' — {branding["company_name"]}'

    footer_links_parts = []
    if branding.get("terms_url"):
        footer_links_parts.append(
            f'<a href="{branding["terms_url"]}" style="color:#6b7280;">Terms</a>'
        )
    if branding.get("privacy_url"):
        footer_links_parts.append(
            f'<a href="{branding["privacy_url"]}" style="color:#6b7280;">Privacy</a>'
        )
    footer_links = ""
    if footer_links_parts:
        footer_links = f'<p>{" | ".join(footer_links_parts)}</p>'

    support_line = ""
    if branding.get("support_email"):
        support_line = (
            f'<p>Questions? Contact '
            f'<a href="mailto:{branding["support_email"]}" style="color:#6b7280;">'
            f'{branding["support_email"]}</a></p>'
        )

    template_vars = {
        **branding,
        "subject": subject,
        "body_content": body_content,
        "logo_html": logo_html,
        "company_suffix": company_suffix,
        "footer_links": footer_links,
        "support_line": support_line,
    }

    return render_email_html(BASE_EMAIL_TEMPLATE, template_vars)


# ============================================
# PRE-BUILT EMAIL BODY TEMPLATES
# ============================================

WELCOME_BODY = """\
<h2>Welcome to {app_name}!</h2>
<p>Hi {user_name},</p>
<p>Your account has been created. Here are your login details:</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
    <tr>
        <td style="padding:8px;font-weight:600;color:#374151;">Email:</td>
        <td style="padding:8px;">{user_email}</td>
    </tr>
    <tr>
        <td style="padding:8px;font-weight:600;color:#374151;">Temporary Password:</td>
        <td style="padding:8px;font-family:monospace;background:#f3f4f6;border-radius:4px;">\
{temp_password}</td>
    </tr>
</table>
<p><strong>Please change your password after your first login.</strong></p>
<a href="{login_url}" class="button">Log In Now</a>"""

PASSWORD_RESET_BODY = """\
<h2>Password Reset Request</h2>
<p>Hi {user_name},</p>
<p>We received a request to reset your password for {app_name}.</p>
<a href="{reset_url}" class="button">Reset Password</a>
<p style="font-size:14px;color:#6b7280;margin-top:16px;">
    This link expires in {expiry_minutes} minutes. \
If you didn't request this, you can ignore this email.
</p>"""

ACCOUNT_REQUEST_NOTIFICATION_BODY = """\
<h2>New Account Request</h2>
<p>A new account request has been submitted:</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
    <tr>
        <td style="padding:8px;font-weight:600;color:#374151;border-bottom:1px solid #e5e7eb;">\
Name:</td>
        <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{requester_name}</td>
    </tr>
    <tr>
        <td style="padding:8px;font-weight:600;color:#374151;border-bottom:1px solid #e5e7eb;">\
Email:</td>
        <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{requester_email}</td>
    </tr>
    <tr>
        <td style="padding:8px;font-weight:600;color:#374151;">Company:</td>
        <td style="padding:8px;">{requester_company}</td>
    </tr>
</table>
<a href="{admin_url}" class="button">Review Request</a>"""

ACCOUNT_APPROVED_BODY = """\
<h2>Account Approved!</h2>
<p>Hi {user_name},</p>
<p>Your account request for {app_name} has been approved. You can now log in:</p>
<a href="{login_url}" class="button">Log In</a>"""

ACCOUNT_REJECTED_BODY = """\
<h2>Account Request Update</h2>
<p>Hi {user_name},</p>
<p>Unfortunately, your account request for {app_name} could not be approved at this time.</p>
<p>If you believe this is an error, please contact \
<a href="mailto:{support_email}">{support_email}</a>.</p>"""
