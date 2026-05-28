"""Basecamp webhook subscription lifecycle service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BasecampCredentials,
    BasecampProjectMapping,
    BasecampWebhookSubscription,
)
from app.services.basecamp_service import BasecampService, USER_AGENT

logger = logging.getLogger(__name__)


class BasecampWebhookService:
    @classmethod
    def _derive_secret_token(cls, creds: BasecampCredentials) -> str:
        """Derive a stable, unguessable per-credential token.

        The token is derived from API_KEY_ENCRYPTION_KEY and tenant identity so
        we never persist plaintext, but can still recreate the URL token for
        future re-registration/reconciliation flows.
        """
        key = (settings.API_KEY_ENCRYPTION_KEY or "").encode("utf-8")
        if not key:
            raise RuntimeError("API_KEY_ENCRYPTION_KEY must be configured")
        message = f"basecamp-webhook:{creds.id}:{creds.company_id}".encode("utf-8")
        digest = hmac.new(key, message, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @classmethod
    def _hash_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    async def ensure_secret_token(
        cls,
        creds: BasecampCredentials,
        db: AsyncSession,
    ) -> str:
        """Populate `webhook_secret_hash` once and return plaintext token once."""
        if creds.webhook_secret_hash:
            raise RuntimeError("Webhook secret already exists for credentials")
        token = cls._derive_secret_token(creds)
        creds.webhook_secret_hash = cls._hash_token(token)
        await db.flush()
        return token

    @classmethod
    async def _resolve_payload_token(
        cls,
        creds: BasecampCredentials,
        db: AsyncSession,
    ) -> str:
        if not creds.webhook_secret_hash:
            return await cls.ensure_secret_token(creds, db)

        token = cls._derive_secret_token(creds)
        token_hash = cls._hash_token(token)
        if token_hash != creds.webhook_secret_hash:
            raise RuntimeError(
                "Webhook secret hash mismatch for credentials; cannot reconcile"
            )
        return token

    @classmethod
    async def _basecamp_headers(
        cls,
        creds: BasecampCredentials,
        db: AsyncSession,
    ) -> dict[str, str]:
        access_token = await BasecampService._get_valid_access_token(creds, db)
        return {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        }

    @classmethod
    async def _list_remote_webhooks(
        cls,
        creds: BasecampCredentials,
        project_id: str,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        url = (
            f"https://3.basecampapi.com/{creds.account_id}/buckets/"
            f"{project_id}/webhooks.json"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=await cls._basecamp_headers(creds, db))
        if resp.status_code != 200:
            raise RuntimeError(
                f"Basecamp list webhooks failed for project {project_id}: HTTP {resp.status_code}"
            )
        payload = resp.json()
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, dict)]

    @classmethod
    async def register_for_project(
        cls,
        creds: BasecampCredentials,
        project_id: str,
        db: AsyncSession,
    ) -> BasecampWebhookSubscription:
        token = await cls._resolve_payload_token(creds, db)
        payload_url = (
            f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/api/integrations/basecamp/"
            f"webhook/{token}"
        )

        url = (
            f"https://3.basecampapi.com/{creds.account_id}/buckets/"
            f"{project_id}/webhooks.json"
        )
        body = {
            "payload_url": payload_url,
            "types": ["Todo", "Todolist"],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers=await cls._basecamp_headers(creds, db),
                json=body,
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Basecamp webhook register failed for project {project_id}: HTTP {resp.status_code}"
            )
        data = resp.json() if resp.content else {}
        webhook_id = str((data or {}).get("id") or "").strip()
        if not webhook_id:
            raise RuntimeError(
                f"Basecamp webhook register missing id for project {project_id}"
            )

        row_result = await db.execute(
            select(BasecampWebhookSubscription).where(
                BasecampWebhookSubscription.credentials_id == creds.id,
                BasecampWebhookSubscription.basecamp_project_id == str(project_id),
            )
        )
        sub = row_result.scalar_one_or_none()
        if sub is None:
            sub = BasecampWebhookSubscription(
                credentials_id=creds.id,
                basecamp_project_id=str(project_id),
                basecamp_webhook_id=webhook_id,
                active=True,
                last_error=None,
                last_error_at=None,
            )
            db.add(sub)
        else:
            sub.basecamp_webhook_id = webhook_id
            sub.active = True
            sub.last_error = None
            sub.last_error_at = None

        await db.flush()
        return sub

    @classmethod
    async def delete_subscription(
        cls,
        sub_row: BasecampWebhookSubscription,
        creds: BasecampCredentials,
        db: AsyncSession,
    ) -> None:
        url = (
            f"https://3.basecampapi.com/{creds.account_id}/buckets/"
            f"{sub_row.basecamp_project_id}/webhooks/{sub_row.basecamp_webhook_id}.json"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(url, headers=await cls._basecamp_headers(creds, db))
        # Best effort delete: 404 means already gone remotely.
        if resp.status_code not in (200, 202, 204, 404):
            raise RuntimeError(
                "Basecamp webhook delete failed "
                f"project={sub_row.basecamp_project_id} webhook={sub_row.basecamp_webhook_id} "
                f"HTTP {resp.status_code}"
            )
        await db.delete(sub_row)
        await db.flush()

    @classmethod
    async def flag_stale_subscriptions(
        cls,
        creds: BasecampCredentials,
        db: AsyncSession,
        stale_days: int = 7,
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        rows = await db.execute(
            select(BasecampWebhookSubscription).where(
                BasecampWebhookSubscription.credentials_id == creds.id,
                BasecampWebhookSubscription.active.is_(True),
            )
        )
        updated = 0
        for sub in rows.scalars().all():
            is_stale_with_events = (
                sub.last_event_at is not None and sub.last_event_at < cutoff
            )
            is_stale_without_events = (
                sub.last_event_at is None and sub.created_at is not None and sub.created_at < cutoff
            )
            if is_stale_with_events or is_stale_without_events:
                sub.last_error = (
                    f"No webhook events observed in the last {stale_days} days"
                )
                sub.last_error_at = datetime.now(timezone.utc)
                updated += 1
        if updated:
            await db.flush()
        return updated

    @classmethod
    async def reconcile_subscriptions(
        cls,
        creds: BasecampCredentials,
        db: AsyncSession,
    ) -> dict[str, int]:
        """Ensure local + remote webhook subscriptions exist per mapped project."""
        stats = {
            "registered": 0,
            "re_registered": 0,
            "unchanged": 0,
            "failed": 0,
            "stale_flagged": 0,
        }

        mappings_result = await db.execute(
            select(BasecampProjectMapping).where(
                BasecampProjectMapping.company_id == creds.company_id,
                BasecampProjectMapping.basecamp_account_id == creds.account_id,
            )
        )
        project_ids = [str(m.basecamp_project_id) for m in mappings_result.scalars().all()]

        for project_id in project_ids:
            project_tx = await db.begin_nested()
            try:
                local_result = await db.execute(
                    select(BasecampWebhookSubscription).where(
                        BasecampWebhookSubscription.credentials_id == creds.id,
                        BasecampWebhookSubscription.basecamp_project_id == project_id,
                    )
                )
                local = local_result.scalar_one_or_none()

                remote_rows = await cls._list_remote_webhooks(
                    creds=creds,
                    project_id=project_id,
                    db=db,
                )
                remote_ids = {str(r.get("id")) for r in remote_rows if r.get("id") is not None}

                if local is None:
                    await cls.register_for_project(creds, project_id, db)
                    stats["registered"] += 1
                    await project_tx.commit()
                    continue

                if local.basecamp_webhook_id not in remote_ids:
                    local.active = False
                    local.last_error = "Remote webhook missing; re-registering"
                    local.last_error_at = datetime.now(timezone.utc)
                    await db.flush()
                    await cls.register_for_project(creds, project_id, db)
                    stats["re_registered"] += 1
                    await project_tx.commit()
                    continue

                local.active = True
                local.last_error = None
                local.last_error_at = None
                stats["unchanged"] += 1
                await db.flush()
                await project_tx.commit()
            except Exception as exc:
                await project_tx.rollback()
                stats["failed"] += 1
                logger.exception(
                    "basecamp.webhook.reconcile_project_failed creds_id=%s project_id=%s",
                    creds.id,
                    project_id,
                )
                local_result = await db.execute(
                    select(BasecampWebhookSubscription).where(
                        BasecampWebhookSubscription.credentials_id == creds.id,
                        BasecampWebhookSubscription.basecamp_project_id == project_id,
                    )
                )
                local = local_result.scalar_one_or_none()
                if local is not None:
                    local.last_error = str(exc)
                    local.last_error_at = datetime.now(timezone.utc)
                    await db.flush()

        stats["stale_flagged"] = await cls.flag_stale_subscriptions(creds, db)
        return stats
