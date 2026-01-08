# ============================================
# TIME TRACKER - EMAIL SERVICE
# ============================================
# Handles all email sending functionality for the application.
# Supports SMTP, with templates for common notifications.
#
# Configuration via environment variables:
#   SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
#   SMTP_FROM_EMAIL, SMTP_FROM_NAME
# ============================================

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional, List, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Base exception for email service errors"""
    pass


class EmailConfigurationError(EmailServiceError):
    """Raised when email is not properly configured"""
    pass


class EmailSendError(EmailServiceError):
    """Raised when email fails to send"""
    pass


class EmailService:
    """
    Email service for sending transactional emails.
    
    Usage:
        email_service = EmailService()
        await email_service.send_welcome_email("user@example.com", "John")
    """
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT or 587
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = getattr(settings, 'SMTP_FROM_EMAIL', None) or self.smtp_username
        self.from_name = getattr(settings, 'SMTP_FROM_NAME', 'Time Tracker')
        
        # Setup Jinja2 for email templates
        template_dir = Path(__file__).parent.parent / "templates" / "email"
        if template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            self.jinja_env = None
            logger.warning(f"Email template directory not found: {template_dir}")
    
    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return bool(
            self.smtp_server and 
            self.smtp_username and 
            self.smtp_password
        )
    
    def _create_message(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None
    ) -> MIMEMultipart:
        """Create a MIME message with HTML and optional text fallback"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        # Ensure from_name and from_email are strings for formataddr
        from_name = self.from_name or 'Time Tracker'
        from_email = self.from_email or ''
        msg['From'] = formataddr((from_name, from_email))
        msg['To'] = to_email
        
        # Add plain text version (fallback)
        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        
        # Add HTML version
        msg.attach(MIMEText(body_html, 'html'))
        
        return msg
    
    def _render_template(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """Render an email template with context"""
        if not self.jinja_env:
            raise EmailConfigurationError("Email templates not configured")
        
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            raise EmailServiceError(f"Template rendering failed: {e}")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None
    ) -> bool:
        """
        Send an email asynchronously.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_html: HTML body content
            body_text: Plain text body (optional fallback)
            
        Returns:
            True if email was sent successfully
            
        Raises:
            EmailConfigurationError: If SMTP not configured
            EmailSendError: If sending fails
        """
        if not self.is_configured:
            logger.warning("Email not configured - skipping send")
            return False
        
        msg = self._create_message(to_email, subject, body_html, body_text)
        
        try:
            # Run SMTP in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg, to_email)
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise EmailSendError(f"Failed to send email: {e}")
    
    def _send_smtp(self, msg: MIMEMultipart, to_email: str) -> None:
        """Synchronous SMTP send (called from thread pool)"""
        # Type guards for SMTP configuration
        if not self.smtp_server:
            raise EmailConfigurationError("SMTP_SERVER not configured")
        if not self.smtp_username:
            raise EmailConfigurationError("SMTP_USERNAME not configured")
        if not self.smtp_password:
            raise EmailConfigurationError("SMTP_PASSWORD not configured")
        
        from_email = self.from_email or self.smtp_username
        
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Send the same email to multiple recipients.
        
        Returns dict of {email: success_status}
        """
        results = {}
        for email in recipients:
            try:
                await self.send_email(email, subject, body_html, body_text)
                results[email] = True
            except EmailSendError:
                results[email] = False
        return results
    
    # ==========================================
    # TEMPLATED EMAIL METHODS
    # ==========================================
    
    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        login_url: str = ""
    ) -> bool:
        """Send welcome email to new user"""
        subject = f"Welcome to {self.from_name}!"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Welcome to {self.from_name}!</h1>
                <p>Hi {user_name},</p>
                <p>Your account has been created successfully. You can now start tracking your time and managing your projects.</p>
                <p>
                    <a href="{login_url}" style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px;">
                        Login to Your Account
                    </a>
                </p>
                <p>If you have any questions, feel free to reach out to our support team.</p>
                <p>Best regards,<br>{self.from_name} Team</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Welcome to {self.from_name}!
        
        Hi {user_name},
        
        Your account has been created successfully. You can now start tracking your time and managing your projects.
        
        Login at: {login_url}
        
        Best regards,
        {self.from_name} Team
        """
        
        return await self.send_email(to_email, subject, body_html, body_text)
    
    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_url: str,
        expires_in_hours: int = 24
    ) -> bool:
        """Send password reset email"""
        subject = f"Reset Your {self.from_name} Password"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Password Reset Request</h1>
                <p>Hi {user_name},</p>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <p>
                    <a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px;">
                        Reset Password
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">This link will expire in {expires_in_hours} hours.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
                <p>Best regards,<br>{self.from_name} Team</p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Password Reset Request
        
        Hi {user_name},
        
        We received a request to reset your password. Visit the link below to create a new password:
        
        {reset_url}
        
        This link will expire in {expires_in_hours} hours.
        
        If you didn't request this, you can safely ignore this email.
        
        Best regards,
        {self.from_name} Team
        """
        
        return await self.send_email(to_email, subject, body_html, body_text)
    
    async def send_account_request_notification(
        self,
        admin_email: str,
        requester_name: str,
        requester_email: str,
        admin_url: str = ""
    ) -> bool:
        """Notify admin of new account request"""
        subject = f"New Account Request - {requester_name}"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">New Account Request</h1>
                <p>A new account request has been submitted:</p>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p><strong>Name:</strong> {requester_name}</p>
                    <p><strong>Email:</strong> {requester_email}</p>
                </div>
                <p>
                    <a href="{admin_url}" style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px;">
                        Review Request
                    </a>
                </p>
                <p>Best regards,<br>{self.from_name} System</p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(admin_email, subject, body_html)
    
    async def send_account_approved_email(
        self,
        to_email: str,
        user_name: str,
        temp_password: str,
        login_url: str = ""
    ) -> bool:
        """Send account approval notification with temporary password"""
        subject = f"Your {self.from_name} Account Has Been Approved!"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #10b981;">Account Approved!</h1>
                <p>Hi {user_name},</p>
                <p>Great news! Your account request has been approved.</p>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p><strong>Email:</strong> {to_email}</p>
                    <p><strong>Temporary Password:</strong> <code style="background: #e5e5e5; padding: 2px 6px;">{temp_password}</code></p>
                </div>
                <p style="color: #ef4444;"><strong>⚠️ Please change your password after first login!</strong></p>
                <p>
                    <a href="{login_url}" style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px;">
                        Login Now
                    </a>
                </p>
                <p>Best regards,<br>{self.from_name} Team</p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, body_html)
    
    async def send_account_rejected_email(
        self,
        to_email: str,
        user_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """Send account rejection notification"""
        subject = f"Regarding Your {self.from_name} Account Request"
        
        reason_text = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #ef4444;">Account Request Update</h1>
                <p>Hi {user_name},</p>
                <p>We regret to inform you that your account request could not be approved at this time.</p>
                {reason_text}
                <p>If you believe this is an error or have questions, please contact our support team.</p>
                <p>Best regards,<br>{self.from_name} Team</p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, body_html)
    
    async def send_time_entry_reminder(
        self,
        to_email: str,
        user_name: str,
        missing_date: str
    ) -> bool:
        """Send reminder for missing time entries"""
        subject = f"Time Entry Reminder - {missing_date}"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #f59e0b;">⏰ Time Entry Reminder</h1>
                <p>Hi {user_name},</p>
                <p>It looks like you haven't logged any time for <strong>{missing_date}</strong>.</p>
                <p>Please remember to track your time to ensure accurate project tracking and payroll.</p>
                <p>Best regards,<br>{self.from_name} Team</p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, body_html)
    
    async def send_payroll_processed_notification(
        self,
        to_email: str,
        user_name: str,
        period_name: str,
        total_hours: float,
        total_amount: float
    ) -> bool:
        """Notify user their payroll has been processed"""
        subject = f"Payroll Processed - {period_name}"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #10b981;">💰 Payroll Processed</h1>
                <p>Hi {user_name},</p>
                <p>Your payroll for <strong>{period_name}</strong> has been processed.</p>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p><strong>Total Hours:</strong> {total_hours:.2f}</p>
                    <p><strong>Total Amount:</strong> ${total_amount:.2f}</p>
                </div>
                <p>Best regards,<br>{self.from_name} Team</p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, body_html)


# Singleton instance
email_service = EmailService()
