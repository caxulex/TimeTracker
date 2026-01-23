# ============================================
# TIME TRACKER - EMAIL LOG UTILITY
# ============================================
# Utility functions for logging emails to the database.
# Called from routers that send emails.
# ============================================

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailLog

logger = logging.getLogger(__name__)


async def log_email(
    db: AsyncSession,
    to_email: str,
    from_email: str,
    subject: str,
    email_type: str,
    status: str = "sent",
    error_message: Optional[str] = None,
    company_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> EmailLog:
    """
    Log an email to the database for tracking.
    
    Args:
        db: Database session
        to_email: Recipient email address
        from_email: Sender email address
        subject: Email subject
        email_type: Type of email (welcome, password_reset, approval, etc.)
        status: Email status (pending, sent, delivered, failed, bounced)
        error_message: Error message if failed
        company_id: Company ID for multi-tenant filtering
        metadata: Additional metadata
        
    Returns:
        Created EmailLog record
    """
    try:
        email_log = EmailLog(
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            email_type=email_type,
            status=status,
            error_message=error_message,
            company_id=company_id,
            email_metadata=metadata,
            sent_at=datetime.now(timezone.utc) if status == "sent" else None,
            delivered_at=datetime.now(timezone.utc) if status == "delivered" else None
        )
        
        db.add(email_log)
        await db.commit()
        await db.refresh(email_log)
        
        logger.info(f"Email logged: {email_type} to {to_email} - {status}")
        return email_log
        
    except Exception as e:
        logger.error(f"Failed to log email: {e}")
        await db.rollback()
        raise


async def log_email_sent(
    db: AsyncSession,
    to_email: str,
    subject: str,
    email_type: str,
    company_id: Optional[int] = None,
    from_email: str = "noreply@timetracker.com",
    metadata: Optional[Dict[str, Any]] = None
) -> EmailLog:
    """
    Convenience function to log a successfully sent email.
    """
    return await log_email(
        db=db,
        to_email=to_email,
        from_email=from_email,
        subject=subject,
        email_type=email_type,
        status="sent",
        company_id=company_id,
        metadata=metadata
    )


async def log_email_failed(
    db: AsyncSession,
    to_email: str,
    subject: str,
    email_type: str,
    error_message: str,
    company_id: Optional[int] = None,
    from_email: str = "noreply@timetracker.com",
    metadata: Optional[Dict[str, Any]] = None
) -> EmailLog:
    """
    Convenience function to log a failed email.
    """
    return await log_email(
        db=db,
        to_email=to_email,
        from_email=from_email,
        subject=subject,
        email_type=email_type,
        status="failed",
        error_message=error_message,
        company_id=company_id,
        metadata=metadata
    )
