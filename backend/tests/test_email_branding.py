"""
Tests for email template branding system.
TASK 8.4: Verify email templates use configurable branding values.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================
# DEFAULT BRANDING
# ============================================

class TestEmailBrandingDefaults:
    """Test that default branding values are populated."""

    def test_default_branding_has_required_keys(self):
        from app.services.email_branding import DEFAULT_BRANDING

        required_keys = [
            "app_name", "company_name", "logo_url", "primary_color",
            "support_email", "support_url", "terms_url", "privacy_url", "tagline",
        ]
        for key in required_keys:
            assert key in DEFAULT_BRANDING, f"Missing default branding key: {key}"

    def test_default_primary_color_is_valid_hex(self):
        from app.services.email_branding import DEFAULT_BRANDING

        color = DEFAULT_BRANDING["primary_color"]
        assert color.startswith("#"), f"Primary color should be hex: {color}"
        assert len(color) == 7, f"Primary color should be #RRGGBB: {color}"

    def test_default_app_name_is_not_empty(self):
        from app.services.email_branding import DEFAULT_BRANDING

        assert DEFAULT_BRANDING["app_name"], "app_name should not be empty"


# ============================================
# ENVIRONMENT OVERRIDES
# ============================================

class TestEmailBrandingFromEnvironment:
    """Test branding values extracted from environment variables."""

    @pytest.mark.asyncio
    async def test_env_overrides_defaults(self):
        from app.services.email_branding import get_email_branding

        with patch.dict(os.environ, {
            "VITE_APP_NAME": "Acme Tracker",
            "VITE_COMPANY_NAME": "Acme Corp",
            "VITE_PRIMARY_COLOR": "#FF5733",
            "VITE_SUPPORT_EMAIL": "help@acme.com",
        }):
            branding = await get_email_branding(db=None, company_id=None)

        assert branding["app_name"] == "Acme Tracker"
        assert branding["company_name"] == "Acme Corp"
        assert branding["primary_color"] == "#FF5733"
        assert branding["support_email"] == "help@acme.com"

    @pytest.mark.asyncio
    async def test_partial_env_overrides(self):
        from app.services.email_branding import get_email_branding

        with patch.dict(os.environ, {"VITE_APP_NAME": "Custom Name"}, clear=False):
            branding = await get_email_branding(db=None, company_id=None)

        assert branding["app_name"] == "Custom Name"
        assert branding["primary_color"].startswith("#")


# ============================================
# DATABASE OVERRIDES
# ============================================

class TestEmailBrandingFromDatabase:
    """Test branding loaded from white_label_configs table."""

    @pytest.mark.asyncio
    async def test_db_overrides_env_and_defaults(self):
        from app.services.email_branding import get_email_branding

        mock_config = MagicMock()
        mock_config.app_name = "DB App Name"
        mock_config.company_name = "DB Company"
        mock_config.logo_url = "https://cdn.example.com/logo.png"
        mock_config.primary_color = "#00FF00"
        mock_config.support_email = "db-support@example.com"
        mock_config.support_url = "https://help.example.com"
        mock_config.terms_url = "https://example.com/terms"
        mock_config.privacy_url = "https://example.com/privacy"
        mock_config.tagline = "Track smarter"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch.dict(os.environ, {"VITE_APP_NAME": "Env Name"}, clear=False):
            branding = await get_email_branding(db=mock_db, company_id=42)

        # DB should win over env
        assert branding["app_name"] == "DB App Name"
        assert branding["company_name"] == "DB Company"
        assert branding["logo_url"] == "https://cdn.example.com/logo.png"
        assert branding["primary_color"] == "#00FF00"
        assert branding["support_email"] == "db-support@example.com"

    @pytest.mark.asyncio
    async def test_db_graceful_fallback_on_error(self):
        from app.services.email_branding import get_email_branding

        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB connection failed")

        branding = await get_email_branding(db=mock_db, company_id=1)

        assert "app_name" in branding
        assert "primary_color" in branding

    @pytest.mark.asyncio
    async def test_no_db_no_company_returns_defaults(self):
        from app.services.email_branding import get_email_branding

        branding = await get_email_branding(db=None, company_id=None)
        assert "app_name" in branding
        assert isinstance(branding["primary_color"], str)


# ============================================
# TEMPLATE RENDERING
# ============================================

class TestEmailTemplateRendering:
    """Test that email templates render with branding values."""

    def test_render_welcome_email_with_custom_branding(self):
        from app.services.email_branding import (
            build_branded_email, render_email_html, WELCOME_BODY,
        )

        branding = {
            "app_name": "Acme Tracker",
            "company_name": "Acme Corp",
            "logo_url": "https://acme.com/logo.png",
            "primary_color": "#E74C3C",
            "support_email": "help@acme.com",
            "support_url": "",
            "terms_url": "https://acme.com/terms",
            "privacy_url": "https://acme.com/privacy",
            "tagline": "",
        }

        body = render_email_html(
            WELCOME_BODY, branding,
            user_name="Alice Smith",
            user_email="alice@acme.com",
            temp_password="TempPass!99",
            login_url="https://tracker.acme.com/login",
        )

        html = build_branded_email(
            subject="Welcome to Acme Tracker",
            body_content=body,
            branding=branding,
        )

        # Custom branding in output
        assert "Acme Tracker" in html
        assert "Acme Corp" in html
        assert "#E74C3C" in html
        assert "https://acme.com/logo.png" in html
        assert "help@acme.com" in html
        assert "https://acme.com/terms" in html
        assert "https://acme.com/privacy" in html

        # Template data
        assert "Alice Smith" in html
        assert "alice@acme.com" in html
        assert "TempPass!99" in html
        assert "https://tracker.acme.com/login" in html

    def test_render_password_reset_with_custom_branding(self):
        from app.services.email_branding import (
            build_branded_email, render_email_html, PASSWORD_RESET_BODY,
        )

        branding = {
            "app_name": "XYZ Time",
            "company_name": "XYZ Corp",
            "logo_url": "",
            "primary_color": "#7C3AED",
            "support_email": "support@xyz.com",
            "support_url": "",
            "terms_url": "",
            "privacy_url": "",
            "tagline": "",
        }

        body = render_email_html(
            PASSWORD_RESET_BODY, branding,
            user_name="Bob",
            reset_url="https://xyz.com/reset?token=abc123",
            expiry_minutes="30",
        )

        html = build_branded_email(
            subject="Password Reset",
            body_content=body,
            branding=branding,
        )

        assert "XYZ Time" in html
        assert "XYZ Corp" in html
        assert "#7C3AED" in html
        assert "https://xyz.com/reset?token=abc123" in html
        assert "support@xyz.com" in html
        assert "30 minutes" in html

    def test_render_account_request_notification(self):
        from app.services.email_branding import (
            build_branded_email, render_email_html, ACCOUNT_REQUEST_NOTIFICATION_BODY,
        )

        branding = {
            "app_name": "Time Pro",
            "company_name": "",
            "logo_url": "",
            "primary_color": "#2563EB",
            "support_email": "",
            "support_url": "",
            "terms_url": "",
            "privacy_url": "",
            "tagline": "",
        }

        body = render_email_html(
            ACCOUNT_REQUEST_NOTIFICATION_BODY, branding,
            requester_name="Charlie Brown",
            requester_email="charlie@newco.com",
            requester_company="NewCo Inc",
            admin_url="https://timepro.com/admin/requests",
        )

        html = build_branded_email(
            subject="New Account Request",
            body_content=body,
            branding=branding,
        )

        assert "Time Pro" in html
        assert "Charlie Brown" in html
        assert "charlie@newco.com" in html
        assert "NewCo Inc" in html
        assert "https://timepro.com/admin/requests" in html

    def test_safe_dict_handles_missing_keys(self):
        from app.services.email_branding import render_email_html

        template = "<p>Hello {user_name}, welcome to {app_name}. Code: {missing_var}.</p>"
        branding = {"app_name": "Test"}

        result = render_email_html(template, branding, user_name="Alice")

        assert "Alice" in result
        assert "Test" in result
        assert "{missing_var}" in result

    def test_base_template_no_logo_when_not_configured(self):
        from app.services.email_branding import build_branded_email

        branding = {
            "app_name": "No Logo App", "company_name": "", "logo_url": "",
            "primary_color": "#333333", "support_email": "",
            "support_url": "", "terms_url": "", "privacy_url": "", "tagline": "",
        }

        html = build_branded_email("Test", "<p>Hello</p>", branding)

        assert "<img" not in html
        assert "No Logo App" in html

    def test_base_template_includes_logo_when_configured(self):
        from app.services.email_branding import build_branded_email

        branding = {
            "app_name": "Logo App", "company_name": "", "primary_color": "#111111",
            "logo_url": "https://cdn.example.com/logo.svg",
            "support_email": "", "support_url": "", "terms_url": "",
            "privacy_url": "", "tagline": "",
        }

        html = build_branded_email("Test", "<p>Hi</p>", branding)

        assert '<img src="https://cdn.example.com/logo.svg"' in html

    def test_footer_links_only_when_urls_provided(self):
        from app.services.email_branding import build_branded_email

        branding_no_links = {
            "app_name": "Test", "company_name": "", "logo_url": "",
            "primary_color": "#000", "support_email": "",
            "support_url": "", "terms_url": "", "privacy_url": "", "tagline": "",
        }
        html_no = build_branded_email("Test", "<p>Hi</p>", branding_no_links)
        assert "Terms" not in html_no
        assert "Privacy" not in html_no

        branding_with_links = dict(branding_no_links)
        branding_with_links["terms_url"] = "https://t.co/terms"
        branding_with_links["privacy_url"] = "https://t.co/privacy"
        html_yes = build_branded_email("Test", "<p>Hi</p>", branding_with_links)
        assert "Terms" in html_yes
        assert "Privacy" in html_yes
        assert "https://t.co/terms" in html_yes
        assert "https://t.co/privacy" in html_yes

    def test_account_approved_uses_branding(self):
        from app.services.email_branding import (
            build_branded_email, render_email_html, ACCOUNT_APPROVED_BODY,
        )

        branding = {
            "app_name": "Custom App", "company_name": "Custom Co",
            "logo_url": "", "primary_color": "#FF0000",
            "support_email": "s@c.com", "support_url": "",
            "terms_url": "", "privacy_url": "", "tagline": "",
        }

        body = render_email_html(
            ACCOUNT_APPROVED_BODY, branding,
            user_name="Dana", login_url="https://c.com/login",
        )
        html = build_branded_email("Approved", body, branding)

        assert "Custom App" in html
        assert "Custom Co" in html
        assert "Dana" in html
        assert "https://c.com/login" in html

    def test_account_rejected_uses_branding(self):
        from app.services.email_branding import (
            build_branded_email, render_email_html, ACCOUNT_REJECTED_BODY,
        )

        branding = {
            "app_name": "Reject App", "company_name": "",
            "logo_url": "", "primary_color": "#222",
            "support_email": "help@r.com", "support_url": "",
            "terms_url": "", "privacy_url": "", "tagline": "",
        }

        body = render_email_html(
            ACCOUNT_REJECTED_BODY, branding, user_name="Eve",
        )
        html = build_branded_email("Rejected", body, branding)

        assert "Reject App" in html
        assert "Eve" in html
        assert "help@r.com" in html
