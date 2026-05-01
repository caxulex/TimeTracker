"""Basecamp integration service.

Wraps the Basecamp 4 OAuth + API surface for the v1 one-way project
mirror. We use the existing ``httpx`` async client directly rather than
``basecampy3`` because basecampy3 is synchronous and its ``Basecamp3``
constructor expects pre-issued tokens; doing the OAuth dance + async
DB persistence ourselves with ``httpx`` is simpler and avoids dragging
sync HTTP I/O into the async event loop.

References:
* https://github.com/basecamp/bc3-api
* https://github.com/basecamp/api/blob/master/sections/authentication.md
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BasecampCredentials,
    BasecampProjectMapping,
    Project,
    Team,
)
from app.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)


# Basecamp Launchpad OAuth + API endpoints
LAUNCHPAD_AUTHORIZATION_URL = "https://launchpad.37signals.com/authorization/new"
LAUNCHPAD_TOKEN_URL = "https://launchpad.37signals.com/authorization/token"
LAUNCHPAD_AUTHORIZATION_INFO_URL = "https://launchpad.37signals.com/authorization.json"
LAUNCHPAD_REVOKE_URL = "https://launchpad.37signals.com/authorization/revoke"

# Refresh threshold: if expires_at is within this many seconds, refresh
# proactively before issuing the next API call. Avoids reactive 401
# retry storms.
REFRESH_THRESHOLD_SECONDS = 60

# User-Agent: Basecamp asks integrations to identify themselves.
USER_AGENT = "TimeTracker by SMC (support@shaemarcus.com)"


class BasecampError(Exception):
    """Base class for Basecamp integration errors."""


class BasecampAuthError(BasecampError):
    """Raised on OAuth / authentication failures."""


class BasecampNotConfiguredError(BasecampError):
    """Raised when BASECAMP_CLIENT_ID / CLIENT_SECRET are not set."""


class BasecampAPIError(BasecampError):
    """Raised on non-2xx responses from the Basecamp API."""


def _encryption() -> EncryptionService:
    return EncryptionService()


def _is_configured() -> bool:
    return bool(settings.BASECAMP_CLIENT_ID and settings.BASECAMP_CLIENT_SECRET)


class BasecampService:
    """Tenant-scoped wrapper around Basecamp 4 OAuth + projects API."""

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    @staticmethod
    def is_configured() -> bool:
        """Return True iff client_id + client_secret are present."""
        return _is_configured()

    @staticmethod
    def get_authorization_url(state: str) -> str:
        """Build the Launchpad OAuth authorization URL."""
        if not _is_configured():
            raise BasecampNotConfiguredError(
                "Basecamp integration not configured"
            )
        params = {
            "type": "web_server",
            "client_id": settings.BASECAMP_CLIENT_ID,
            "redirect_uri": settings.BASECAMP_REDIRECT_URI,
            "state": state,
        }
        return f"{LAUNCHPAD_AUTHORIZATION_URL}?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(code: str) -> dict:
        """Exchange an OAuth ``code`` for access + refresh tokens.

        Returns a dict with keys: ``access_token``, ``refresh_token``,
        ``expires_at`` (timezone-aware UTC ``datetime``), ``account_id``,
        ``account_name``. Raises ``BasecampAuthError`` on any failure.
        """
        if not _is_configured():
            raise BasecampNotConfiguredError(
                "Basecamp integration not configured"
            )

        token_params = {
            "type": "web_server",
            "client_id": settings.BASECAMP_CLIENT_ID,
            "client_secret": settings.BASECAMP_CLIENT_SECRET,
            "redirect_uri": settings.BASECAMP_REDIRECT_URI,
            "code": code,
        }

        try:
            with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
                token_resp = client.post(LAUNCHPAD_TOKEN_URL, params=token_params)
                if token_resp.status_code != 200:
                    raise BasecampAuthError(
                        f"Token exchange failed: HTTP {token_resp.status_code}"
                    )
                token_data = token_resp.json()

                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in")
                if not (access_token and refresh_token and expires_in):
                    raise BasecampAuthError(
                        "Token response missing access_token / refresh_token / expires_in"
                    )

                # Identify which Basecamp account this token belongs to.
                auth_resp = client.get(
                    LAUNCHPAD_AUTHORIZATION_INFO_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "User-Agent": USER_AGENT,
                    },
                )
                if auth_resp.status_code != 200:
                    raise BasecampAuthError(
                        f"authorization.json returned HTTP {auth_resp.status_code}"
                    )
                auth_data = auth_resp.json()

        except httpx.HTTPError as exc:
            raise BasecampAuthError(f"OAuth HTTP error: {exc}") from exc

        # Pick the first BC3 account; v1 supports a single account per
        # company. Operators with multiple BC3 accounts will need v2.
        accounts = [
            a for a in auth_data.get("accounts", [])
            if a.get("product") == "bc3"
        ]
        if not accounts:
            raise BasecampAuthError(
                "Authenticated user has no Basecamp 4 accounts"
            )
        account = accounts[0]

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            "account_id": str(account["id"]),
            "account_name": account.get("name"),
        }

    @staticmethod
    async def refresh_access_token(
        credentials: BasecampCredentials,
        db: AsyncSession,
    ) -> str:
        """Refresh ``credentials.access_token`` in-place.

        Updates the encrypted token + ``expires_at`` and returns the new
        plaintext access token. Raises ``BasecampAuthError`` on failure.
        """
        if not _is_configured():
            raise BasecampNotConfiguredError(
                "Basecamp integration not configured"
            )

        enc = _encryption()
        try:
            refresh_token = enc.decrypt(credentials.refresh_token_encrypted)
        except Exception as exc:
            raise BasecampAuthError(
                f"Failed to decrypt refresh token: {exc}"
            ) from exc

        params = {
            "type": "refresh",
            "refresh_token": refresh_token,
            "client_id": settings.BASECAMP_CLIENT_ID,
            "client_secret": settings.BASECAMP_CLIENT_SECRET,
            "redirect_uri": settings.BASECAMP_REDIRECT_URI,
        }

        try:
            async with httpx.AsyncClient(
                timeout=30.0, headers={"User-Agent": USER_AGENT}
            ) as client:
                resp = await client.post(LAUNCHPAD_TOKEN_URL, params=params)
        except httpx.HTTPError as exc:
            raise BasecampAuthError(f"Refresh HTTP error: {exc}") from exc

        if resp.status_code != 200:
            raise BasecampAuthError(
                f"Refresh failed: HTTP {resp.status_code}"
            )
        data = resp.json()
        new_access = data.get("access_token")
        expires_in = data.get("expires_in")
        if not (new_access and expires_in):
            raise BasecampAuthError(
                "Refresh response missing access_token / expires_in"
            )

        credentials.access_token_encrypted = enc.encrypt(new_access)
        credentials.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(expires_in)
        )
        # Some refresh responses rotate the refresh token; persist if so.
        new_refresh = data.get("refresh_token")
        if new_refresh:
            credentials.refresh_token_encrypted = enc.encrypt(new_refresh)
        await db.flush()

        return new_access

    @staticmethod
    async def _get_valid_access_token(
        credentials: BasecampCredentials,
        db: AsyncSession,
    ) -> str:
        """Return a plaintext access token, refreshing if near expiry."""
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(seconds=REFRESH_THRESHOLD_SECONDS)
        # ``expires_at`` is timezone-aware (TIMESTAMPTZ); compare directly.
        if credentials.expires_at <= threshold:
            return await BasecampService.refresh_access_token(credentials, db)
        return _encryption().decrypt(credentials.access_token_encrypted)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    @staticmethod
    async def list_projects(
        credentials: BasecampCredentials,
        db: AsyncSession,
    ) -> list[dict]:
        """List all visible Basecamp projects for the connected account.

        Returns dicts with keys: ``id``, ``name``, ``description``,
        ``status``, ``created_at``. Auto-refreshes access token if it is
        within ``REFRESH_THRESHOLD_SECONDS`` of expiry.
        """
        token = await BasecampService._get_valid_access_token(credentials, db)
        url = f"https://3.basecampapi.com/{credentials.account_id}/projects.json"

        projects: list[dict] = []
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": USER_AGENT,
                },
            ) as client:
                next_url: Optional[str] = url
                while next_url:
                    resp = await client.get(next_url)
                    if resp.status_code != 200:
                        raise BasecampAPIError(
                            f"projects.json returned HTTP {resp.status_code}"
                        )
                    for p in resp.json():
                        projects.append(
                            {
                                "id": str(p.get("id")),
                                "name": p.get("name") or "",
                                "description": p.get("description") or "",
                                "status": p.get("status") or "active",
                                "created_at": p.get("created_at"),
                            }
                        )
                    # Basecamp paginates via Link: <...>; rel="next"
                    next_url = _parse_next_link(resp.headers.get("Link"))
        except httpx.HTTPError as exc:
            raise BasecampAPIError(f"projects.json HTTP error: {exc}") from exc

        return projects

    @staticmethod
    async def sync_projects_to_company(
        credentials: BasecampCredentials,
        company_id: int,
        db: AsyncSession,
        dry_run: bool = False,
    ) -> dict:
        """Pull Basecamp projects and mirror them as internal Project rows.

        Idempotent: re-running after a successful sync produces
        ``created=0``; ``updated`` reflects only projects whose
        name/description actually changed.
        """
        report: dict[str, Any] = {
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "errors": [],
            "dry_run": dry_run,
        }

        # Resolve target team: pick the lowest-id team for this company.
        # Project rows require a non-null team_id.
        team_row = await db.execute(
            select(Team).where(Team.company_id == company_id).order_by(Team.id).limit(1)
        )
        team = team_row.scalar_one_or_none()
        if team is None:
            report["errors"].append(
                f"Company {company_id} has no team to host imported projects"
            )
            return report
        team_id = team.id

        try:
            bc_projects = await BasecampService.list_projects(credentials, db)
        except BasecampError as exc:
            report["errors"].append(str(exc))
            return report

        for bc in bc_projects:
            try:
                bc_id = bc["id"]
                bc_name = bc["name"]
                bc_desc = bc.get("description") or None

                mapping_row = await db.execute(
                    select(BasecampProjectMapping).where(
                        BasecampProjectMapping.company_id == company_id,
                        BasecampProjectMapping.basecamp_account_id
                        == credentials.account_id,
                        BasecampProjectMapping.basecamp_project_id == bc_id,
                    )
                )
                mapping = mapping_row.scalar_one_or_none()

                if mapping is None:
                    if dry_run:
                        report["created"] += 1
                        continue
                    project = Project(
                        team_id=team_id,
                        name=bc_name,
                        description=bc_desc,
                    )
                    db.add(project)
                    await db.flush()
                    db.add(
                        BasecampProjectMapping(
                            company_id=company_id,
                            basecamp_account_id=credentials.account_id,
                            basecamp_project_id=bc_id,
                            internal_project_id=project.id,
                            last_synced_at=datetime.now(timezone.utc),
                        )
                    )
                    report["created"] += 1
                else:
                    proj_row = await db.execute(
                        select(Project).where(Project.id == mapping.internal_project_id)
                    )
                    project = proj_row.scalar_one_or_none()
                    if project is None:
                        # Internal project was deleted out from under us;
                        # recreate.
                        if dry_run:
                            report["created"] += 1
                            continue
                        project = Project(
                            team_id=team_id, name=bc_name, description=bc_desc
                        )
                        db.add(project)
                        await db.flush()
                        mapping.internal_project_id = project.id
                        mapping.last_synced_at = datetime.now(timezone.utc)
                        report["created"] += 1
                        continue

                    changed = (project.name != bc_name) or (
                        (project.description or None) != bc_desc
                    )
                    if changed:
                        if not dry_run:
                            project.name = bc_name
                            project.description = bc_desc
                            mapping.last_synced_at = datetime.now(timezone.utc)
                        report["updated"] += 1
                    else:
                        if not dry_run:
                            mapping.last_synced_at = datetime.now(timezone.utc)
                        report["unchanged"] += 1
            except Exception as exc:  # noqa: BLE001 — record + continue
                logger.exception("basecamp.sync.project_failed")
                report["errors"].append(
                    f"Project {bc.get('id')}: {exc}"
                )

        if not dry_run:
            credentials.last_sync_at = datetime.now(timezone.utc)
            await db.flush()

        return report

    # ------------------------------------------------------------------
    # Disconnect helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def revoke_token(access_token: str) -> bool:
        """Best-effort revoke at Launchpad. Returns True on 200/204."""
        if not _is_configured():
            return False
        try:
            async with httpx.AsyncClient(
                timeout=10.0, headers={"User-Agent": USER_AGENT}
            ) as client:
                resp = await client.post(
                    LAUNCHPAD_REVOKE_URL,
                    params={"token": access_token},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            return resp.status_code in (200, 204)
        except httpx.HTTPError as exc:
            logger.warning("basecamp.revoke.failed: %s", exc)
            return False


def _parse_next_link(link_header: Optional[str]) -> Optional[str]:
    """Parse a HTTP ``Link`` header and return the URL with rel=next, if any."""
    if not link_header:
        return None
    for part in link_header.split(","):
        segs = part.strip().split(";")
        if len(segs) < 2:
            continue
        url = segs[0].strip()
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]
        for s in segs[1:]:
            if s.strip().lower() in ('rel="next"', "rel=next"):
                return url
    return None
