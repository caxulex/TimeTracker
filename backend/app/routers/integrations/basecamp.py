"""Basecamp integration router.

Endpoints:

* ``GET    /api/integrations/basecamp/connect``     — super_admin: returns OAuth URL
* ``GET    /api/integrations/basecamp/callback``    — public + state-CSRF protected
* ``GET    /api/integrations/basecamp/status``      — admin/super_admin: connection summary
* ``POST   /api/integrations/basecamp/sync``        — super_admin: trigger sync
* ``DELETE /api/integrations/basecamp/disconnect``  — super_admin: drop credentials

CSRF state tokens are stored in Redis (``basecamp_oauth_state:`` prefix)
with a 10-minute TTL, reusing the existing ``token_blacklist`` Redis
client.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
import hashlib
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session, get_db
from app.dependencies import get_current_active_user
from app.middleware.rate_limit import rate_limiter
from app.models import (
    BasecampCredentials,
    BasecampProcessedEvent,
    BasecampProjectMapping,
    BasecampWebhookSubscription,
    Team,
    User,
)
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.basecamp_service import (
    BasecampAPIError,
    BasecampAuthError,
    BasecampError,
    BasecampNotConfiguredError,
    BasecampService,
)
from app.services.basecamp_webhook_handlers import BasecampWebhookHandlers
from app.services.encryption_service import EncryptionService
from app.services.token_blacklist import token_blacklist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/basecamp", tags=["Integrations: Basecamp"])

OAUTH_STATE_PREFIX = "basecamp_oauth_state:"
OAUTH_STATE_TTL_SECONDS = 10 * 60
SETTINGS_REDIRECT_PATH = "/settings/integrations"


# ----------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------


def require_super_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


def require_admin_or_super(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role not in ("super_admin", "admin", "company_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def _ensure_configured() -> None:
    if not BasecampService.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Basecamp integration not configured",
        )


def _ensure_company_scope(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no company; Basecamp integration requires a company scope",
        )
    return user.company_id


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class ConnectResponse(BaseModel):
    authorization_url: str


class StatusResponse(BaseModel):
    connected: bool
    account_name: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    target_team_id: Optional[int] = None
    target_team_name: Optional[str] = None
    auto_sync_enabled: bool = False


class SettingsUpdateRequest(BaseModel):
    target_team_id: Optional[int] = None
    auto_sync_enabled: Optional[bool] = None

    model_config = {"extra": "forbid"}


class SyncRequest(BaseModel):
    dry_run: bool = False


class SyncResponse(BaseModel):
    # Project counts (unchanged from v1+v2): per-Basecamp-project mirror
    # results.
    created: int
    updated: int
    unchanged: int
    errors: list[str]
    # To-do counts (new in v3.0): per-Basecamp-to-do mirror results.
    # Only populated for projects that have a basecamp_project_mappings
    # row. dry_run=True returns counts without writing to either tier.
    todos_created: int = 0
    todos_updated: int = 0
    todos_unchanged: int = 0
    todo_errors: list[str] = []
    dry_run: bool


class WebhookAckResponse(BaseModel):
    accepted: bool = True


# ----------------------------------------------------------------------
# State token helpers (Redis-backed CSRF)
# ----------------------------------------------------------------------


async def _store_state_token(state: str, payload: dict) -> None:
    redis_client = await token_blacklist.get_redis()
    await redis_client.setex(
        f"{OAUTH_STATE_PREFIX}{state}",
        OAUTH_STATE_TTL_SECONDS,
        json.dumps(payload),
    )


async def _consume_state_token(state: str) -> Optional[dict]:
    """Look up + delete the state token. Returns the stored payload or None."""
    redis_client = await token_blacklist.get_redis()
    key = f"{OAUTH_STATE_PREFIX}{state}"
    raw = await redis_client.get(key)
    if not raw:
        return None
    await redis_client.delete(key)
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _hash_webhook_token(secret_token: str) -> str:
    return hashlib.sha256(secret_token.encode("utf-8")).hexdigest()


def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_bucket_id_from_recording(recording: dict) -> str:
    bucket = recording.get("bucket")
    if isinstance(bucket, dict):
        return _safe_str(bucket.get("id"))
    if recording.get("bucket_id") is not None:
        return _safe_str(recording.get("bucket_id"))
    parent = recording.get("parent")
    if isinstance(parent, dict):
        parent_bucket = parent.get("bucket")
        if isinstance(parent_bucket, dict):
            return _safe_str(parent_bucket.get("id"))
    return ""


async def _process_basecamp_event_background(
    *,
    creds_id: int,
    event_payload: dict,
) -> None:
    event_kind = _safe_str(event_payload.get("kind")).lower()
    event_id = _safe_str(event_payload.get("id"))
    recording = event_payload.get("recording") if isinstance(event_payload, dict) else {}
    if not isinstance(recording, dict):
        recording = {}
    bucket_id = _extract_bucket_id_from_recording(recording)

    async with async_session() as db:
        try:
            creds = await db.get(BasecampCredentials, creds_id)
            if creds is None:
                return

            await BasecampWebhookHandlers.handle_event(
                event=event_payload,
                credentials=creds,
                db=db,
            )

            if bucket_id:
                sub_result = await db.execute(
                    select(BasecampWebhookSubscription).where(
                        BasecampWebhookSubscription.credentials_id == creds.id,
                        BasecampWebhookSubscription.basecamp_project_id == bucket_id,
                    )
                )
                sub = sub_result.scalar_one_or_none()
                if sub is not None:
                    sub.last_error = None
                    sub.last_error_at = None
                    sub.last_event_at = datetime.now(timezone.utc)

            await AuditLogger.log(
                db=db,
                action=AuditAction.UPDATE,
                resource_type="basecamp.webhook.received",
                user_id=None,
                user_email="basecamp-webhook@system",
                details=f"Processed Basecamp webhook kind={event_kind} event_id={event_id}",
                new_values={
                    "kind": event_kind,
                    "event_id": event_id,
                    "bucket_id": bucket_id,
                },
            )
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            try:
                creds = await db.get(BasecampCredentials, creds_id)
                if creds is not None and bucket_id:
                    sub_result = await db.execute(
                        select(BasecampWebhookSubscription).where(
                            BasecampWebhookSubscription.credentials_id == creds.id,
                            BasecampWebhookSubscription.basecamp_project_id == bucket_id,
                        )
                    )
                    sub = sub_result.scalar_one_or_none()
                    if sub is not None:
                        sub.last_error = str(exc)
                        sub.last_error_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                await db.rollback()
            logger.exception(
                "basecamp.webhook.background_failed kind=%s event_id=%s",
                event_kind,
                event_id,
            )


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------


@router.get("/connect", response_model=ConnectResponse)
async def connect(
    current_user: User = Depends(require_super_admin),
):
    """Start the OAuth flow: returns the URL to redirect the user to."""
    _ensure_configured()
    company_id = _ensure_company_scope(current_user)

    state = secrets.token_urlsafe(32)
    await _store_state_token(
        state,
        {
            "user_id": current_user.id,
            "company_id": company_id,
        },
    )
    url = BasecampService.get_authorization_url(state)
    logger.info(
        "basecamp.oauth.connect_initiated user_id=%s company_id=%s",
        current_user.id, company_id,
    )
    return ConnectResponse(authorization_url=url)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """OAuth callback: validates state, exchanges code, persists credentials."""
    _ensure_configured()

    payload = await _consume_state_token(state)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token",
        )
    company_id = payload.get("company_id")
    user_id = payload.get("user_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token missing company context",
        )

    try:
        tokens = BasecampService.exchange_code_for_tokens(code)
    except BasecampAuthError as exc:
        logger.warning("basecamp.oauth.exchange_failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Basecamp OAuth failed: {exc}",
        )

    enc = EncryptionService()

    # UPSERT: replace existing row for this company.
    existing_row = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.company_id == company_id
        )
    )
    creds = existing_row.scalar_one_or_none()

    if creds is None:
        creds = BasecampCredentials(
            company_id=company_id,
            account_id=tokens["account_id"],
            account_name=tokens.get("account_name"),
            access_token_encrypted=enc.encrypt(tokens["access_token"]),
            refresh_token_encrypted=enc.encrypt(tokens["refresh_token"]),
            expires_at=tokens["expires_at"],
            connected_by_user_id=user_id,
        )
        db.add(creds)
    else:
        creds.account_id = tokens["account_id"]
        creds.account_name = tokens.get("account_name")
        creds.access_token_encrypted = enc.encrypt(tokens["access_token"])
        creds.refresh_token_encrypted = enc.encrypt(tokens["refresh_token"])
        creds.expires_at = tokens["expires_at"]
        creds.connected_by_user_id = user_id

    await db.commit()

    logger.info(
        "basecamp.oauth.connected company_id=%s account_id=%s by_user_id=%s",
        company_id, tokens["account_id"], user_id,
    )

    return RedirectResponse(
        url=f"{SETTINGS_REDIRECT_PATH}?status=connected",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(
    current_user: User = Depends(require_admin_or_super),
    db: AsyncSession = Depends(get_db),
):
    """Return current connection status (no token material)."""
    if current_user.company_id is None:
        return StatusResponse(connected=False)

    row = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.company_id == current_user.company_id
        )
    )
    creds = row.scalar_one_or_none()
    if creds is None:
        return StatusResponse(connected=False)

    target_team_name: Optional[str] = None
    if creds.target_team_id is not None:
        team_row = await db.execute(
            select(Team).where(
                Team.id == creds.target_team_id,
                Team.deleted_at.is_(None),
            )
        )
        team = team_row.scalar_one_or_none()
        if team is not None:
            target_team_name = team.name

    return StatusResponse(
        connected=True,
        account_name=creds.account_name,
        last_sync_at=creds.last_sync_at,
        expires_at=creds.expires_at,
        target_team_id=creds.target_team_id,
        target_team_name=target_team_name,
        auto_sync_enabled=creds.auto_sync_enabled,
    )


@router.patch("/settings", response_model=StatusResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update Basecamp integration settings (target team, auto-sync)."""
    company_id = _ensure_company_scope(current_user)

    row = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.company_id == company_id
        )
    )
    creds = row.scalar_one_or_none()
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Basecamp is not connected for this company",
        )

    fields = body.model_dump(exclude_unset=True)
    target_team_name: Optional[str] = None

    if "target_team_id" in fields:
        new_team_id = fields["target_team_id"]
        if new_team_id is None:
            creds.target_team_id = None
        else:
            team_row = await db.execute(
                select(Team).where(
                    Team.id == new_team_id,
                    Team.deleted_at.is_(None),
                )
            )
            team = team_row.scalar_one_or_none()
            if team is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target team not found",
                )
            if team.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target team belongs to a different company",
                )
            creds.target_team_id = team.id
            target_team_name = team.name

    if "auto_sync_enabled" in fields and fields["auto_sync_enabled"] is not None:
        creds.auto_sync_enabled = bool(fields["auto_sync_enabled"])

    await db.commit()
    await db.refresh(creds)

    if creds.target_team_id is not None and target_team_name is None:
        team_row = await db.execute(
            select(Team).where(
                Team.id == creds.target_team_id,
                Team.deleted_at.is_(None),
            )
        )
        team = team_row.scalar_one_or_none()
        if team is not None:
            target_team_name = team.name

    logger.info(
        "basecamp.settings.updated company_id=%s target_team_id=%s "
        "auto_sync_enabled=%s by_user_id=%s",
        company_id, creds.target_team_id, creds.auto_sync_enabled,
        current_user.id,
    )

    return StatusResponse(
        connected=True,
        account_name=creds.account_name,
        last_sync_at=creds.last_sync_at,
        expires_at=creds.expires_at,
        target_team_id=creds.target_team_id,
        target_team_name=target_team_name,
        auto_sync_enabled=creds.auto_sync_enabled,
    )


@router.post("/sync", response_model=SyncResponse)
async def sync_projects(
    body: SyncRequest = SyncRequest(),
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a Basecamp -> TimeTracker project sync."""
    _ensure_configured()
    company_id = _ensure_company_scope(current_user)

    row = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.company_id == company_id
        )
    )
    creds = row.scalar_one_or_none()
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Basecamp is not connected for this company",
        )

    try:
        report = await BasecampService.sync_projects_to_company(
            creds,
            company_id,
            db,
            dry_run=body.dry_run,
            triggered_by_user_id=current_user.id,
            triggered_by_user_email=current_user.email,
        )
        todo_report = await BasecampService.sync_todos_for_company(
            creds,
            company_id,
            db,
            dry_run=body.dry_run,
            triggered_by_user_id=current_user.id,
            triggered_by_user_email=current_user.email,
        )
    except BasecampError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Basecamp sync failed: {exc}",
        )

    if not body.dry_run:
        await db.commit()

    logger.info(
        "basecamp.sync.completed company_id=%s dry_run=%s created=%s updated=%s "
        "unchanged=%s errors=%s todos_created=%s todos_updated=%s "
        "todos_unchanged=%s todo_errors=%s",
        company_id, body.dry_run, report["created"], report["updated"],
        report["unchanged"], len(report.get("errors", [])),
        todo_report["todos_created"], todo_report["todos_updated"],
        todo_report["todos_unchanged"],
        len(todo_report.get("todo_errors", [])),
    )
    merged = {
        **report,
        "todos_created": todo_report["todos_created"],
        "todos_updated": todo_report["todos_updated"],
        "todos_unchanged": todo_report["todos_unchanged"],
        "todo_errors": todo_report.get("todo_errors", []),
    }
    return SyncResponse(**merged)


@router.post("/webhook/{secret_token}", response_model=WebhookAckResponse)
async def receive_webhook(
    secret_token: str,
    body: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Receive Basecamp webhook payloads (public endpoint, URL-secret auth)."""
    token_hash = _hash_webhook_token(secret_token)

    allowed, *_ = await rate_limiter.check_rate_limit(
        identifier=f"basecamp-webhook:{token_hash[:24]}",
        path="/api/integrations/basecamp/webhook",
    )
    if not allowed:
        logger.warning("basecamp.webhook.rate_limited token_hash_prefix=%s", token_hash[:12])
        return WebhookAckResponse(accepted=True)

    row = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.webhook_secret_hash == token_hash
        )
    )
    creds = row.scalar_one_or_none()
    if creds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    event_id = _safe_str(body.get("id"))
    kind = _safe_str(body.get("kind"))
    recording = body.get("recording")
    if not event_id or not kind or not isinstance(recording, dict):
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="basecamp.webhook.invalid_payload",
            user_id=None,
            user_email="basecamp-webhook@system",
            details="Ignored malformed Basecamp webhook payload",
            new_values={"event_id": event_id, "kind": kind},
        )
        await db.commit()
        return WebhookAckResponse(accepted=True)

    bucket_id = _extract_bucket_id_from_recording(recording)
    if not bucket_id:
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="basecamp.webhook.invalid_payload",
            user_id=None,
            user_email="basecamp-webhook@system",
            details="Ignored Basecamp webhook payload missing recording.bucket.id",
            new_values={"event_id": event_id, "kind": kind},
        )
        await db.commit()
        return WebhookAckResponse(accepted=True)

    mapping_row = await db.execute(
        select(BasecampProjectMapping).where(
            BasecampProjectMapping.company_id == creds.company_id,
            BasecampProjectMapping.basecamp_account_id == creds.account_id,
            BasecampProjectMapping.basecamp_project_id == bucket_id,
        )
    )
    mapping = mapping_row.scalar_one_or_none()
    if mapping is None:
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="basecamp.webhook.cross_tenant_rejected",
            user_id=None,
            user_email="basecamp-webhook@system",
            details=(
                f"Webhook bucket {bucket_id} not mapped for credentials company_id={creds.company_id}"
            ),
            new_values={"event_id": event_id, "kind": kind, "bucket_id": bucket_id},
        )
        await db.commit()
        return WebhookAckResponse(accepted=True)

    stmt = (
        insert(BasecampProcessedEvent)
        .values(event_id=event_id, kind=kind)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        await db.commit()
        return WebhookAckResponse(accepted=True)

    sub_row = await db.execute(
        select(BasecampWebhookSubscription).where(
            BasecampWebhookSubscription.credentials_id == creds.id,
            BasecampWebhookSubscription.basecamp_project_id == bucket_id,
        )
    )
    sub = sub_row.scalar_one_or_none()
    if sub is not None:
        sub.last_event_at = datetime.now(timezone.utc)

    await db.commit()

    background_tasks.add_task(
        _process_basecamp_event_background,
        creds_id=creds.id,
        event_payload=body,
    )
    return WebhookAckResponse(accepted=True)


@router.delete("/disconnect")
async def disconnect(
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete the company's Basecamp credentials. Mappings are retained."""
    company_id = _ensure_company_scope(current_user)

    row = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.company_id == company_id
        )
    )
    creds = row.scalar_one_or_none()
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Basecamp connection to disconnect",
        )

    # Best-effort revoke at Launchpad.
    try:
        access_token = EncryptionService().decrypt(creds.access_token_encrypted)
        await BasecampService.revoke_token(access_token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("basecamp.disconnect.revoke_failed: %s", exc)

    await db.delete(creds)
    await db.commit()

    logger.info(
        "basecamp.oauth.disconnected company_id=%s by_user_id=%s",
        company_id, current_user.id,
    )
    return {"detail": "Disconnected"}
