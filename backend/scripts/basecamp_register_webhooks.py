#!/usr/bin/env python3
"""Bootstrap Basecamp webhook subscriptions for existing tenants.

Deployment-time workflow:
1. Ensure each Basecamp credential has a webhook secret hash
2. Reconcile per-project webhook subscriptions
3. Print plaintext token once per credential for operator capture
4. Run one catch-up Basecamp sync
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass

# Allow "python scripts/basecamp_register_webhooks.py".
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import BasecampCredentials
from app.services.basecamp_service import BasecampService
from app.services.basecamp_webhook_service import BasecampWebhookService

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    company_id: int
    created_secret: bool
    token: str | None
    registered: int
    re_registered: int
    failed: int
    sync_errors: int


async def _run_for_company(creds: BasecampCredentials, db: AsyncSession) -> BootstrapResult:
    created_secret = False
    plaintext_token: str | None = None

    if not creds.webhook_secret_hash:
        plaintext_token = await BasecampWebhookService.ensure_secret_token(creds, db)
        created_secret = True

    reconcile = await BasecampWebhookService.reconcile_subscriptions(creds, db)

    todo_report = await BasecampService.sync_todos_for_company(
        creds,
        creds.company_id,
        db,
        dry_run=False,
    )

    await db.commit()

    return BootstrapResult(
        company_id=creds.company_id,
        created_secret=created_secret,
        token=plaintext_token,
        registered=int(reconcile.get("registered", 0)),
        re_registered=int(reconcile.get("re_registered", 0)),
        failed=int(reconcile.get("failed", 0)),
        sync_errors=len(todo_report.get("todo_errors", [])),
    )


async def main() -> int:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker",
    )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Session() as db:
            rows = await db.execute(select(BasecampCredentials).order_by(BasecampCredentials.id))
            creds_rows = rows.scalars().all()
            if not creds_rows:
                print("[basecamp-webhooks] No Basecamp credentials found.")
                return 0

            results: list[BootstrapResult] = []
            print("[basecamp-webhooks] Starting webhook bootstrap...")
            for creds in creds_rows:
                company_tx = await db.begin_nested()
                try:
                    result = await _run_for_company(creds, db)
                    if company_tx.is_active:
                        await company_tx.commit()
                    results.append(result)
                    print(
                        "[basecamp-webhooks] company_id="
                        f"{result.company_id} registered={result.registered} "
                        f"re_registered={result.re_registered} failed={result.failed} "
                        f"sync_errors={result.sync_errors}"
                    )
                    if result.created_secret and result.token:
                        print(
                            "[basecamp-webhooks] ONE_TIME_TOKEN "
                            f"company_id={result.company_id} token={result.token}"
                        )
                except Exception as exc:  # noqa: BLE001
                    if company_tx.is_active:
                        await company_tx.rollback()
                    logger.exception(
                        "basecamp.webhooks.bootstrap_company_failed company_id=%s",
                        creds.company_id,
                    )
                    print(
                        "[basecamp-webhooks] company_id="
                        f"{creds.company_id} failed: {exc}"
                    )

            print("[basecamp-webhooks] Bootstrap complete.")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main()))
