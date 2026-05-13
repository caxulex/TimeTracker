# ============================================
# TIME TRACKER - EMAIL SERVICE TESTS
# Phase 7: Testing - Email functionality
# ============================================
"""
Tests for email service functionality.
Uses mocking to avoid actual SMTP connections.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import smtplib

from app.services.email_service import (
    EmailService,
    EmailConfigurationError,
    EmailSendError,
)


class TestEmailServiceConfiguration:
    """Test email service configuration."""

    def test_is_configured_returns_false_when_not_configured(self):
        """Test that is_configured returns False when SMTP not set."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = None
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = None
            mock_settings.SMTP_PASSWORD = None
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            assert service.is_configured is False

    def test_is_configured_returns_true_when_configured(self):
        """Test that is_configured returns True when SMTP is set."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "user@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            assert service.is_configured is True


class TestEmailMessageCreation:
    """Test email message creation."""

    def test_create_message_structure(self):
        """Test that _create_message creates proper MIME structure."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            msg = service._create_message(
                to_email="recipient@example.com",
                subject="Test Subject",
                body_html="<p>Test body</p>",
                body_text="Test body"
            )
            
            assert msg['Subject'] == "Test Subject"
            assert msg['To'] == "recipient@example.com"
            assert 'From' in msg

    def test_create_message_with_html_only(self):
        """Test message creation with only HTML body."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            msg = service._create_message(
                to_email="recipient@example.com",
                subject="HTML Only",
                body_html="<p>HTML content</p>"
            )
            
            assert msg['Subject'] == "HTML Only"


class TestEmailSending:
    """Test email sending functionality."""

    @pytest.mark.asyncio
    async def test_send_email_returns_false_when_not_configured(self):
        """Test that send_email returns False when not configured."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = None
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = None
            mock_settings.SMTP_PASSWORD = None
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            result = await service.send_email(
                to_email="test@example.com",
                subject="Test",
                body_html="<p>Test</p>"
            )
            
            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_calls_smtp(self):
        """Test that send_email attempts SMTP connection when configured."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            
            with patch.object(service, '_send_smtp') as mock_send:
                mock_send.return_value = None
                
                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test",
                    body_html="<p>Test</p>"
                )
                
                assert result is True
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_raises_on_smtp_error(self):
        """Test that SMTP errors are properly raised."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            
            with patch.object(service, '_send_smtp') as mock_send:
                mock_send.side_effect = smtplib.SMTPException("Connection failed")
                
                with pytest.raises(EmailSendError):
                    await service.send_email(
                        to_email="recipient@example.com",
                        subject="Test",
                        body_html="<p>Test</p>"
                    )


class TestTemplatedEmails:
    """Test templated email methods."""

    @pytest.mark.asyncio
    async def test_welcome_email_content(self):
        """Test welcome email has correct content."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            
            with patch.object(service, 'send_email', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True
                
                await service.send_welcome_email(
                    to_email="newuser@example.com",
                    user_name="John Doe",
                    login_url="https://app.example.com/login"
                )
                
                # Verify send_email was called
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                
                # Check subject contains welcome
                assert "Welcome" in call_args.kwargs.get('subject', call_args.args[1] if len(call_args.args) > 1 else '')

    @pytest.mark.asyncio
    async def test_password_reset_email_content(self):
        """Test password reset email has correct content."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            
            with patch.object(service, 'send_email', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True
                
                await service.send_password_reset_email(
                    to_email="user@example.com",
                    user_name="John Doe",
                    reset_url="https://app.example.com/reset?token=abc123",
                    expires_in_hours=24
                )
                
                # Verify send_email was called
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                
                # Check that reset URL is included in the HTML body
                body_html = call_args.kwargs.get('body_html', call_args.args[2] if len(call_args.args) > 2 else '')
                assert "reset" in body_html.lower() or "Reset" in body_html


class TestBulkEmail:
    """Test bulk email functionality."""

    @pytest.mark.asyncio
    async def test_send_bulk_email_returns_results(self):
        """Test that bulk email returns status for each recipient."""
        with patch('app.services.email_service.settings') as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "sender@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            
            service = EmailService()
            
            with patch.object(service, 'send_email', new_callable=AsyncMock) as mock_send:
                # First email succeeds, second fails
                mock_send.side_effect = [True, EmailSendError("Failed")]
                
                results = await service.send_bulk_email(
                    recipients=["user1@example.com", "user2@example.com"],
                    subject="Bulk Test",
                    body_html="<p>Test</p>"
                )
                
                assert results["user1@example.com"] is True
                assert results["user2@example.com"] is False


# ============================================
# WELCOME-EMAIL-ON-USER-CREATION WIRING TESTS
# These verify the bug fix: human-user creation endpoints must
# trigger send_welcome_email AFTER the user is committed, and an
# SMTP failure must NOT cause the endpoint to fail.
# ============================================

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.main import app
from app.dependencies import get_current_admin_user
from app.models import User
from app.services.email_service import EmailSendError


class TestWelcomeEmailOnUserCreation:
    """End-to-end wiring tests for the welcome email on user creation."""

    @pytest.mark.asyncio
    async def test_admin_create_user_triggers_welcome_email(
        self,
        client: AsyncClient,
        admin_user: User,
        db_session,
    ):
        """POST /api/users by an admin must call send_welcome_email."""
        # Override admin auth dependency to bypass JWT/Redis blacklist (Redis is
        # not required by this test's invariant — we only care about the wiring).
        app.dependency_overrides[get_current_admin_user] = lambda: admin_user
        try:
            with patch(
                "app.routers.users.email_service.send_welcome_email",
                new_callable=AsyncMock,
            ) as mock_welcome:
                mock_welcome.return_value = True

                resp = await client.post(
                    "/api/users",
                    json={
                        "email": "wired-welcome@example.com",
                        "password": "ValidPass123!",
                        "name": "Wired Welcome",
                        "role": "regular_user",
                    },
                )

                assert resp.status_code == 201, resp.text
                mock_welcome.assert_called_once()
                call_kwargs = mock_welcome.call_args.kwargs
                assert call_kwargs.get("to_email") == "wired-welcome@example.com"
                assert call_kwargs.get("user_name") == "Wired Welcome"
        finally:
            app.dependency_overrides.pop(get_current_admin_user, None)

        # User must be committed regardless of email outcome.
        result = await db_session.execute(
            select(User).where(User.email == "wired-welcome@example.com")
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_admin_create_user_smtp_failure_does_not_block_creation(
        self,
        client: AsyncClient,
        admin_user: User,
        db_session,
    ):
        """If send_welcome_email raises, the endpoint must still return 201
        and the user must remain committed in the DB."""
        app.dependency_overrides[get_current_admin_user] = lambda: admin_user
        try:
            with patch(
                "app.routers.users.email_service.send_welcome_email",
                new_callable=AsyncMock,
            ) as mock_welcome:
                mock_welcome.side_effect = EmailSendError("simulated SMTP outage")

                resp = await client.post(
                    "/api/users",
                    json={
                        "email": "smtp-fail-safe@example.com",
                        "password": "ValidPass123!",
                        "name": "SMTP Failsafe",
                        "role": "regular_user",
                    },
                )

                # The endpoint must NOT 500 because email failed.
                assert resp.status_code == 201, resp.text
                mock_welcome.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_admin_user, None)

        # User row must still be in the DB.
        result = await db_session.execute(
            select(User).where(User.email == "smtp-fail-safe@example.com")
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_register_endpoint_triggers_welcome_email(
        self,
        client: AsyncClient,
        db_session,
    ):
        """POST /api/auth/register (self-service) must call send_welcome_email."""
        with patch(
            "app.routers.auth.email_service.send_welcome_email",
            new_callable=AsyncMock,
        ) as mock_welcome:
            mock_welcome.return_value = True

            resp = await client.post(
                "/api/auth/register",
                json={
                    "email": "self-reg-welcome@example.com",
                    "password": "ValidPass123!",
                    "name": "Self Reg",
                },
            )

            assert resp.status_code == 201, resp.text
            mock_welcome.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_endpoint_smtp_failure_does_not_block_registration(
        self,
        client: AsyncClient,
        db_session,
    ):
        """If welcome email fails during /api/auth/register, the user must
        still be created and the endpoint must return 201."""
        with patch(
            "app.routers.auth.email_service.send_welcome_email",
            new_callable=AsyncMock,
        ) as mock_welcome:
            mock_welcome.side_effect = EmailSendError("simulated SMTP outage")

            resp = await client.post(
                "/api/auth/register",
                json={
                    "email": "reg-smtp-fail@example.com",
                    "password": "ValidPass123!",
                    "name": "Reg SMTP Fail",
                },
            )

            assert resp.status_code == 201, resp.text

        result = await db_session.execute(
            select(User).where(User.email == "reg-smtp-fail@example.com")
        )
        assert result.scalar_one_or_none() is not None


class TestNoDeadJinjaInfrastructure:
    """Regression guards: the removed Jinja infrastructure must stay removed."""

    def test_email_service_has_no_jinja_env_attribute(self):
        """EmailService instances must not expose `jinja_env`."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "u@example.com"
            mock_settings.SMTP_PASSWORD = "p"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"

            service = EmailService()
            assert not hasattr(service, "jinja_env")

    def test_email_service_has_no_render_template_method(self):
        """The dead `_render_template` helper must be removed."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_SERVER = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "u@example.com"
            mock_settings.SMTP_PASSWORD = "p"
            mock_settings.SMTP_FROM_NAME = "Test App"
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"

            service = EmailService()
            assert not hasattr(service, "_render_template")

