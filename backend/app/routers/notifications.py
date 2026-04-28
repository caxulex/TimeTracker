# ============================================
# TIME TRACKER - NOTIFICATIONS ROUTER
# ============================================
# API endpoints for in-app notifications.
# Users can view, mark as read, and delete their notifications.
# Admins can send notifications to users.
# ============================================

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_admin_user,
    get_current_user,
)
from app.models import Notification, User
from app.schemas.notifications import (
    NotificationBulkCreate,
    NotificationCreate,
    NotificationDeleteRequest,
    NotificationDeleteResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
    NotificationResponse,
    UnreadCountResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============================================
# USER NOTIFICATION ENDPOINTS
# ============================================

@router.get("", response_model=NotificationListResponse)
async def get_my_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Filter to show only unread notifications"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's notifications with pagination.
    Returns notifications ordered by creation date (newest first).
    """
    # Build base query
    base_filter = Notification.user_id == current_user.id

    if unread_only:
        base_filter = and_(base_filter, Notification.is_read == False)

    if type:
        base_filter = and_(base_filter, Notification.type == type)

    # Get total count
    count_result = await db.execute(
        select(func.count(Notification.id)).where(base_filter)
    )
    total = count_result.scalar() or 0

    # Get unread count (always fetch for badge display)
    unread_result = await db.execute(
        select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False
            )
        )
    )
    unread_count = unread_result.scalar() or 0

    # Get paginated notifications
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Notification)
        .where(base_filter)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    notifications = result.scalars().all()

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get count of unread notifications for the current user.
    Lightweight endpoint for notification badge updates.
    """
    result = await db.execute(
        select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False
            )
        )
    )
    unread_count = result.scalar() or 0

    return UnreadCountResponse(unread_count=unread_count)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific notification by ID.
    Users can only access their own notifications.
    """
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id
            )
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    return NotificationResponse.model_validate(notification)


@router.post("/mark-read", response_model=NotificationMarkReadResponse)
async def mark_notifications_read(
    request: NotificationMarkReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark notifications as read.
    If notification_ids is provided, mark specific notifications.
    If notification_ids is None or empty, mark all as read.
    """
    now = datetime.now(timezone.utc)

    if request.notification_ids:
        # Mark specific notifications as read
        result = await db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.id.in_(request.notification_ids),
                    Notification.user_id == current_user.id,
                    Notification.is_read == False
                )
            )
            .values(is_read=True, read_at=now)
        )
    else:
        # Mark all as read
        result = await db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.is_read == False
                )
            )
            .values(is_read=True, read_at=now)
        )

    await db.commit()
    updated_count = result.rowcount

    return NotificationMarkReadResponse(
        updated_count=updated_count,
        message=f"Marked {updated_count} notification(s) as read"
    )


@router.delete("", response_model=NotificationDeleteResponse)
async def delete_notifications(
    request: NotificationDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete notifications.
    If notification_ids is provided, delete specific notifications.
    If notification_ids is None or empty, delete all read notifications.
    """
    if request.notification_ids:
        # Delete specific notifications
        result = await db.execute(
            delete(Notification)
            .where(
                and_(
                    Notification.id.in_(request.notification_ids),
                    Notification.user_id == current_user.id
                )
            )
        )
    else:
        # Delete all read notifications
        result = await db.execute(
            delete(Notification)
            .where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.is_read == True
                )
            )
        )

    await db.commit()
    deleted_count = result.rowcount

    return NotificationDeleteResponse(
        deleted_count=deleted_count,
        message=f"Deleted {deleted_count} notification(s)"
    )


# ============================================
# ADMIN NOTIFICATION ENDPOINTS
# ============================================

@router.post("/send", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def send_notification(
    notification: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Send a notification to a specific user.
    Admin only.
    """
    # Verify target user exists
    target_result = await db.execute(
        select(User).where(User.id == notification.user_id)
    )
    target_user = target_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    # Company admins can only send to users in their company
    if current_user.role != "super_admin" and current_user.company_id:
        if target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot send notifications to users in other companies"
            )

    # Create notification
    new_notification = Notification(
        user_id=notification.user_id,
        company_id=target_user.company_id,
        type=notification.type.value,
        title=notification.title,
        message=notification.message,
        link=notification.link,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        metadata=notification.metadata
    )

    db.add(new_notification)
    await db.commit()
    await db.refresh(new_notification)

    logger.info(f"Notification sent to user {notification.user_id} by admin {current_user.id}")

    # Send via WebSocket if user is connected
    try:
        from app.routers.websocket import manager
        await manager.send_personal_message({
            "type": "notification",
            "data": NotificationResponse.model_validate(new_notification).model_dump(mode="json")
        }, notification.user_id)
    except Exception as e:
        logger.warning(f"Failed to send WebSocket notification: {e}")

    return NotificationResponse.model_validate(new_notification)


@router.post("/send-bulk", response_model=dict, status_code=status.HTTP_201_CREATED)
async def send_bulk_notifications(
    notification: NotificationBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Send a notification to multiple users.
    Admin only.
    """
    # Verify target users exist
    users_result = await db.execute(
        select(User).where(User.id.in_(notification.user_ids))
    )
    target_users = users_result.scalars().all()

    if not target_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid target users found"
        )

    # Company admins can only send to users in their company
    if current_user.role != "super_admin" and current_user.company_id:
        target_users = [u for u in target_users if u.company_id == current_user.company_id]
        if not target_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot send notifications to users in other companies"
            )

    # Create notifications
    created_count = 0
    websocket_sent = 0

    for user in target_users:
        new_notification = Notification(
            user_id=user.id,
            company_id=user.company_id,
            type=notification.type.value,
            title=notification.title,
            message=notification.message,
            link=notification.link,
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
            metadata=notification.metadata
        )
        db.add(new_notification)
        created_count += 1

    await db.commit()

    # Send via WebSocket to connected users
    try:
        from app.routers.websocket import manager
        for user in target_users:
            try:
                await manager.send_personal_message({
                    "type": "notification",
                    "data": {
                        "type": notification.type.value,
                        "title": notification.title,
                        "message": notification.message,
                        "link": notification.link
                    }
                }, user.id)
                websocket_sent += 1
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                # Bulk fan-out must not swallow shutdown/cancellation.
                raise
            except Exception as ws_exc:
                # One disconnected/dead socket should not abort the rest of
                # the bulk send; log and continue. The DB row is already
                # persisted, so the user will still see the notification on
                # next reconnect.
                logger.warning(
                    "notifications.bulk_ws_delivery_failed",
                    extra={"user_id": user.id, "error": str(ws_exc)},
                )
    except Exception as e:
        logger.warning(f"Failed to send WebSocket notifications: {e}")

    logger.info(f"Bulk notification sent to {created_count} users by admin {current_user.id}")

    return {
        "message": f"Sent {created_count} notifications",
        "created_count": created_count,
        "websocket_delivered": websocket_sent,
        "user_ids": [u.id for u in target_users]
    }


# ============================================
# NOTIFICATION SERVICE HELPER FUNCTIONS
# ============================================

async def create_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    type: str = "info",
    link: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    metadata: Optional[dict] = None,
    company_id: Optional[int] = None,
    send_websocket: bool = True
) -> Notification:
    """
    Helper function to create a notification programmatically.
    Can be imported and used by other services.
    """
    notification = Notification(
        user_id=user_id,
        company_id=company_id,
        type=type,
        title=title,
        message=message,
        link=link,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Send via WebSocket if enabled
    if send_websocket:
        try:
            from app.routers.websocket import manager
            await manager.send_personal_message({
                "type": "notification",
                "data": {
                    "id": notification.id,
                    "type": notification.type,
                    "title": notification.title,
                    "message": notification.message,
                    "link": notification.link,
                    "created_at": notification.created_at.isoformat()
                }
            }, user_id)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")

    return notification


async def notify_user(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    type: str = "info",
    **kwargs
) -> Notification:
    """
    Convenience wrapper for create_notification.
    Simplified API for common notification creation.
    """
    return await create_notification(db, user_id, title, message, type, **kwargs)
