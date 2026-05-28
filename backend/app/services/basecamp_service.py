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

import asyncio
import logging
import random
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BasecampCredentials,
    BasecampProjectMapping,
    BasecampTaskMapping,
    Project,
    Task,
    Team,
)
from app.services.audit_logger import AuditAction, AuditLogger
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

# System sync actor convention for unattended jobs:
# keep ``user_id`` NULL to indicate non-human actor and set an explicit
# synthetic email so audit trails remain searchable.
BASECAMP_SYNC_SYSTEM_EMAIL = "basecamp-sync@system"


class BasecampError(Exception):
    """Base class for Basecamp integration errors."""


class BasecampAuthError(BasecampError):
    """Raised on OAuth / authentication failures."""


class BasecampNotConfiguredError(BasecampError):
    """Raised when BASECAMP_CLIENT_ID / CLIENT_SECRET are not set."""


class BasecampAPIError(BasecampError):
    """Raised on non-2xx responses from the Basecamp API."""


# ---------------------------------------------------------------------------
# HTTP retry / backoff
# ---------------------------------------------------------------------------
#
# Basecamp's v3 API rate-limits aggressively (per-account, sliding window).
# Without retry, the 4-hourly autosync sees 2-7 HTTP 429 responses per run,
# each causing a single to-do list to be skipped until the next cron tick
# (a 2-5% per-run data gap visible as briefly-stale Basecamp data).
#
# These constants tune the per-call retry policy applied centrally by
# ``_http_request_with_retry``. They are intentionally module-level so the
# test suite can monkey-patch them (e.g. to drive ``asyncio.sleep`` to 0).

# Maximum retry attempts after the initial request (so up to 4 HTTP calls
# total per logical request).
HTTP_429_MAX_RETRIES = 3

# Cap any single Retry-After-driven wait (Basecamp occasionally returns
# very large values during sustained throttling; >30s blocks the cron more
# than the data gap it prevents).
HTTP_429_MAX_SINGLE_WAIT_SECONDS = 30.0

# Total cumulative wait budget across all retries for a single logical
# request. Prevents a pathological hang if Basecamp keeps emitting
# very-long Retry-After values back-to-back.
HTTP_429_MAX_TOTAL_WAIT_SECONDS = 60.0


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse an HTTP ``Retry-After`` header per RFC 7231 section 7.1.3.

    Accepts either delta-seconds (integer) or an HTTP-date. Returns the
    number of seconds to wait as a non-negative float, or ``None`` if the
    header is missing/blank/unparseable. Negative deltas and past dates
    clamp to ``0``.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    # delta-seconds form (most common from Basecamp).
    try:
        seconds = float(value)
        return max(0.0, seconds)
    except ValueError:
        pass
    # HTTP-date form.
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = (when - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, delta)


async def _http_request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Issue an HTTP request with 429-aware retry + jittered backoff.

    On HTTP 429 the ``Retry-After`` header (if present and parseable) is
    honoured up to ``HTTP_429_MAX_SINGLE_WAIT_SECONDS``. Otherwise we fall
    back to exponential backoff (2s, 4s, 8s per attempt). A random 0-1s
    jitter is added to every wait to avoid synchronized retries with
    other clients sharing the same Basecamp account.

    Retries up to ``HTTP_429_MAX_RETRIES`` times; if the cumulative wait
    would exceed ``HTTP_429_MAX_TOTAL_WAIT_SECONDS`` we stop early and
    return the most recent 429 response, letting the caller's existing
    non-200 handling raise ``BasecampAPIError`` (the per-list ``try/except``
    in the sync orchestrator then swallows it and continues).

    All non-429 responses (including 5xx) are returned to the caller
    unchanged — only 429 is retried here.
    """
    total_wait = 0.0
    last_response: Optional[httpx.Response] = None
    method_lower = method.lower()
    for attempt in range(HTTP_429_MAX_RETRIES + 1):
        # Dispatch via the method-specific client attribute (``client.get``,
        # ``client.post``) rather than ``client.request`` so existing test
        # mocks that stub ``.get`` / ``.post`` keep working.
        call = getattr(client, method_lower)
        resp = await call(url, **kwargs)
        last_response = resp
        if resp.status_code != 429:
            return resp
        if attempt >= HTTP_429_MAX_RETRIES:
            # Out of retries: return the 429 so the caller raises as before.
            return resp

        retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
        if retry_after is None:
            # Exponential backoff: 2, 4, 8 for attempts 0, 1, 2.
            base_wait = 2.0 * (2 ** attempt)
        else:
            base_wait = retry_after
        wait_s = min(base_wait, HTTP_429_MAX_SINGLE_WAIT_SECONDS)
        wait_s += random.uniform(0, 1)

        if total_wait + wait_s > HTTP_429_MAX_TOTAL_WAIT_SECONDS:
            logger.info(
                "basecamp.http.429.retry_budget_exhausted "
                "attempt=%d total_wait_s=%.2f url=%s",
                attempt + 1,
                total_wait,
                url,
            )
            return resp

        logger.info(
            "basecamp.http.429.retry attempt=%d wait_s=%.2f url=%s",
            attempt + 1,
            wait_s,
            url,
        )
        await asyncio.sleep(wait_s)
        total_wait += wait_s

    # Unreachable: the loop always returns. Kept for type-checker clarity.
    assert last_response is not None
    return last_response


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
                resp = await _http_request_with_retry(
                    client, "POST", LAUNCHPAD_TOKEN_URL, params=params
                )
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
                    resp = await _http_request_with_retry(
                        client, "GET", next_url
                    )
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
        triggered_by_user_id: Optional[int] = None,
        triggered_by_user_email: Optional[str] = None,
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

        # Resolve target team:
        #   - If credentials.target_team_id is set AND points to a team
        #     in this company, use it.
        #   - Otherwise fall back to the legacy behavior: lowest-id team
        #     for the company. Project rows require a non-null team_id.
        team = None
        if credentials.target_team_id is not None:
            target_row = await db.execute(
                select(Team).where(
                    Team.id == credentials.target_team_id,
                    Team.company_id == company_id,
                )
            )
            team = target_row.scalar_one_or_none()
            if team is None:
                # Configured team was deleted or reassigned; fall back.
                logger.warning(
                    "basecamp.sync.target_team_missing company_id=%s "
                    "target_team_id=%s — falling back to lowest-id team",
                    company_id, credentials.target_team_id,
                )

        if team is None:
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
            project_tx = await db.begin_nested()
            try:
                bc_id = str(bc.get("id") or "").strip()
                if not bc_id:
                    raise ValueError("Basecamp project payload is missing id")
                bc_name = (bc.get("name") or "").strip()
                bc_desc = bc.get("description") or None
                actor_user_id, actor_user_email, sync_mode = (
                    BasecampService._resolve_sync_actor(
                        triggered_by_user_id,
                        triggered_by_user_email,
                    )
                )

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
                        await project_tx.commit()
                        continue
                    # Defensive second exists-check before insert keeps intent explicit.
                    existing_row = await db.execute(
                        select(BasecampProjectMapping).where(
                            BasecampProjectMapping.company_id == company_id,
                            BasecampProjectMapping.basecamp_account_id
                            == credentials.account_id,
                            BasecampProjectMapping.basecamp_project_id == bc_id,
                        )
                    )
                    mapping = existing_row.scalar_one_or_none()
                    if mapping is None:
                        project = Project(
                            team_id=team_id,
                            name=bc_name,
                            description=bc_desc,
                        )
                        db.add(project)
                        await db.flush()
                        mapping = BasecampProjectMapping(
                            company_id=company_id,
                            basecamp_account_id=credentials.account_id,
                            basecamp_project_id=bc_id,
                            internal_project_id=project.id,
                            last_synced_at=datetime.now(timezone.utc),
                        )
                        db.add(mapping)
                        await db.flush()
                        await AuditLogger.log(
                            db=db,
                            action=AuditAction.CREATE,
                            resource_type="project",
                            resource_id=project.id,
                            user_id=actor_user_id,
                            user_email=actor_user_email,
                            new_values={
                                "name": project.name,
                                "description": project.description,
                                "team_id": project.team_id,
                                "basecamp_project_id": bc_id,
                            },
                            details=(
                                f"Created from Basecamp project {bc_id} "
                                f"via {sync_mode}"
                            ),
                        )
                        await AuditLogger.log(
                            db=db,
                            action=AuditAction.CREATE,
                            resource_type="basecamp_project_mapping",
                            resource_id=mapping.id,
                            user_id=actor_user_id,
                            user_email=actor_user_email,
                            new_values={
                                "company_id": company_id,
                                "basecamp_account_id": credentials.account_id,
                                "basecamp_project_id": bc_id,
                                "internal_project_id": project.id,
                            },
                            details=(
                                f"Created Basecamp project mapping for project {bc_id} "
                                f"via {sync_mode}"
                            ),
                        )
                        report["created"] += 1
                        await project_tx.commit()
                        continue
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
                        await AuditLogger.log(
                            db=db,
                            action=AuditAction.CREATE,
                            resource_type="project",
                            resource_id=project.id,
                            user_id=actor_user_id,
                            user_email=actor_user_email,
                            new_values={
                                "name": project.name,
                                "description": project.description,
                                "team_id": project.team_id,
                                "basecamp_project_id": bc_id,
                            },
                            details=(
                                f"Recreated missing project from Basecamp "
                                f"project {bc_id} via {sync_mode}"
                            ),
                        )
                        mapping.internal_project_id = project.id
                        mapping.last_synced_at = datetime.now(timezone.utc)
                        report["created"] += 1
                        await project_tx.commit()
                        continue

                    changed = (project.name != bc_name) or (
                        (project.description or None) != bc_desc
                    )
                    if changed:
                        if not dry_run:
                            old_values: dict[str, Any] = {
                                "basecamp_project_id": bc_id,
                            }
                            new_values: dict[str, Any] = {
                                "basecamp_project_id": bc_id,
                            }
                            if project.name != bc_name:
                                old_values["name"] = project.name
                                new_values["name"] = bc_name
                            if (project.description or None) != bc_desc:
                                old_values["description"] = (
                                    project.description or None
                                )
                                new_values["description"] = bc_desc
                            project.name = bc_name
                            project.description = bc_desc
                            mapping.last_synced_at = datetime.now(timezone.utc)
                            await AuditLogger.log(
                                db=db,
                                action=AuditAction.UPDATE,
                                resource_type="project",
                                resource_id=project.id,
                                user_id=actor_user_id,
                                user_email=actor_user_email,
                                old_values=old_values,
                                new_values=new_values,
                                details=(
                                    f"Updated from Basecamp project {bc_id} "
                                    f"via {sync_mode}"
                                ),
                            )
                        report["updated"] += 1
                    else:
                        if not dry_run:
                            mapping.last_synced_at = datetime.now(timezone.utc)
                        report["unchanged"] += 1
                await project_tx.commit()
            except IntegrityError as exc:
                await project_tx.rollback()
                logger.exception("basecamp.sync.project_failed")
                report["errors"].append(
                    f"Project {bc.get('id')}: {exc}"
                )
            except Exception as exc:  # noqa: BLE001 — record + continue
                await project_tx.rollback()
                logger.exception("basecamp.sync.project_failed")
                report["errors"].append(
                    f"Project {bc.get('id')}: {exc}"
                )

        if not dry_run:
            credentials.last_sync_at = datetime.now(timezone.utc)
            await db.flush()

        return report

    # ------------------------------------------------------------------
    # To-do mirroring (v3.0)
    # ------------------------------------------------------------------

    @staticmethod
    async def _list_todolists(
        token: str,
        account_id: str,
        basecamp_project_id: str,
    ) -> list[dict]:
        """Fetch every active to-do list under a Basecamp project.

        Basecamp 3 does not expose ``/buckets/{id}/todolists.json``
        directly: that endpoint returns 404. Instead each project
        carries a ``dock`` array of feature pointers; the ``todoset``
        entry's id identifies the project's todoset, whose response
        publishes a ``todolists_url`` we can paginate. See
        https://github.com/basecamp/bc3-api/blob/master/sections/todolists.md.

        Projects whose to-dos tool is disabled (no ``todoset`` dock
        entry or ``enabled: false``) are skipped quietly — that is a
        valid Basecamp configuration, not an error.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # Step 1: fetch the project to find the todoset dock entry.
            project_url = (
                f"https://3.basecampapi.com/{account_id}/projects/"
                f"{basecamp_project_id}.json"
            )
            proj_resp = await _http_request_with_retry(
                client, "GET", project_url
            )
            if proj_resp.status_code != 200:
                raise BasecampAPIError(
                    f"projects/{basecamp_project_id}.json returned HTTP "
                    f"{proj_resp.status_code}"
                )
            project = proj_resp.json()
            dock = project.get("dock") or []
            todoset_entry = next(
                (d for d in dock if d.get("name") == "todoset"), None
            )
            if todoset_entry is None:
                logger.debug(
                    "basecamp.todos.no_todoset_entry project=%s",
                    basecamp_project_id,
                )
                return []
            if not todoset_entry.get("enabled", True):
                logger.debug(
                    "basecamp.todos.todoset_disabled project=%s",
                    basecamp_project_id,
                )
                return []
            todoset_id = todoset_entry.get("id")
            if todoset_id is None:
                logger.debug(
                    "basecamp.todos.todoset_missing_id project=%s",
                    basecamp_project_id,
                )
                return []

            # Step 2: fetch the todoset to obtain its ``todolists_url``.
            todoset_url = (
                f"https://3.basecampapi.com/{account_id}/buckets/"
                f"{basecamp_project_id}/todosets/{todoset_id}.json"
            )
            ts_resp = await _http_request_with_retry(
                client, "GET", todoset_url
            )
            if ts_resp.status_code != 200:
                raise BasecampAPIError(
                    f"todosets/{todoset_id}.json returned HTTP "
                    f"{ts_resp.status_code}"
                )
            todoset = ts_resp.json()
            todolists_url = todoset.get("todolists_url")
            if not todolists_url:
                raise BasecampAPIError(
                    f"todoset {todoset_id} response missing todolists_url"
                )

            # Step 3: paginate the published todolists_url. Filter to
            # ``status=active`` so archived/trashed lists don't
            # resurrect their tasks.
            sep = "&" if "?" in todolists_url else "?"
            next_url: Optional[str] = f"{todolists_url}{sep}status=active"
            out: list[dict] = []
            while next_url:
                resp = await _http_request_with_retry(
                    client, "GET", next_url
                )
                if resp.status_code != 200:
                    raise BasecampAPIError(
                        f"todolists returned HTTP {resp.status_code}"
                    )
                for lst in resp.json():
                    out.append(
                        {
                            "id": str(lst.get("id")),
                            "title": lst.get("title") or lst.get("name") or "",
                        }
                    )
                next_url = _parse_next_link(resp.headers.get("Link"))
        return out

    @staticmethod
    async def _list_todos_in_list(
        token: str,
        account_id: str,
        basecamp_project_id: str,
        todolist_id: str,
    ) -> list[dict]:
        """Fetch every to-do (active + completed) under a to-do list.

        Basecamp paginates by Link header and returns ``completed=False``
        items by default; request ``completed=true`` separately to
        capture completed to-dos as well so they sync as DONE in
        TimeTracker.
        """
        base = (
            f"https://3.basecampapi.com/{account_id}/buckets/"
            f"{basecamp_project_id}/todolists/{todolist_id}/todos.json"
        )
        results: list[dict] = []
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
        ) as client:
            for query in ("", "?completed=true"):
                next_url: Optional[str] = base + query
                while next_url:
                    resp = await _http_request_with_retry(
                        client, "GET", next_url
                    )
                    if resp.status_code != 200:
                        raise BasecampAPIError(
                            f"todos.json returned HTTP {resp.status_code}"
                        )
                    for t in resp.json():
                        # Note: Basecamp omits ``position`` on completed
                        # to-dos, so this field is None for ~90% of
                        # mirrored rows (all DONE-status; diagnosed
                        # 2026-05-13: 100% of TODO rows have position,
                        # 0% of DONE rows do). Any disambiguation that
                        # uses position must fall back to
                        # ``due_on`` / ``created_at`` in that case.
                        results.append(
                            {
                                "id": str(t.get("id")),
                                "content": t.get("content") or "",
                                "description": t.get("description") or "",
                                "completed": bool(t.get("completed", False)),
                                "due_on": t.get("due_on"),
                                "created_at": t.get("created_at"),
                                "position": t.get("position"),
                                "updated_at": t.get("updated_at"),
                            }
                        )
                    next_url = _parse_next_link(resp.headers.get("Link"))
        return results

    @staticmethod
    async def _get_todo_detail(
        token: str,
        account_id: str,
        bucket_id: str,
        todo_id: str,
    ) -> dict:
        """Fetch a single Basecamp to-do detail including ``steps``."""
        url = (
            f"https://3.basecampapi.com/{account_id}/buckets/"
            f"{bucket_id}/todos/{todo_id}.json"
        )
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
        ) as client:
            resp = await _http_request_with_retry(client, "GET", url)
        if resp.status_code != 200:
            raise BasecampAPIError(
                f"todos/{todo_id}.json returned HTTP {resp.status_code}"
            )
        payload = resp.json()
        if not isinstance(payload, dict):
            raise BasecampAPIError(f"todos/{todo_id}.json returned non-object body")
        return payload

    @staticmethod
    async def _get_todolist_detail(
        token: str,
        account_id: str,
        bucket_id: str,
        todolist_id: str,
    ) -> dict:
        """Fetch a single Basecamp to-do list detail payload."""
        url = (
            f"https://3.basecampapi.com/{account_id}/buckets/"
            f"{bucket_id}/todolists/{todolist_id}.json"
        )
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
        ) as client:
            resp = await _http_request_with_retry(client, "GET", url)
        if resp.status_code != 200:
            raise BasecampAPIError(
                f"todolists/{todolist_id}.json returned HTTP {resp.status_code}"
            )
        payload = resp.json()
        if not isinstance(payload, dict):
            raise BasecampAPIError(
                f"todolists/{todolist_id}.json returned non-object body"
            )
        return payload

    @staticmethod
    async def _find_project_mapping(
        *,
        db: AsyncSession,
        company_id: int,
        account_id: str,
        basecamp_project_id: str,
    ) -> Optional[BasecampProjectMapping]:
        row = await db.execute(
            select(BasecampProjectMapping).where(
                BasecampProjectMapping.company_id == company_id,
                BasecampProjectMapping.basecamp_account_id == account_id,
                BasecampProjectMapping.basecamp_project_id == basecamp_project_id,
            )
        )
        return row.scalar_one_or_none()

    @staticmethod
    async def _find_task_mapping(
        *,
        db: AsyncSession,
        company_id: int,
        account_id: str,
        basecamp_resource_id: str,
        basecamp_type: str = "Todo",
    ) -> Optional[BasecampTaskMapping]:
        row = await db.execute(
            select(BasecampTaskMapping).where(
                BasecampTaskMapping.company_id == company_id,
                BasecampTaskMapping.basecamp_account_id == account_id,
                BasecampTaskMapping.basecamp_type == basecamp_type,
                BasecampTaskMapping.basecamp_todo_id == basecamp_resource_id,
            )
        )
        return row.scalar_one_or_none()

    @staticmethod
    async def sync_single_todo_for_company(
        *,
        credentials: BasecampCredentials,
        company_id: int,
        db: AsyncSession,
        bucket_id: str,
        todo_id: str,
        todolist_id: Optional[str] = None,
    ) -> dict:
        """Refetch + upsert a single Basecamp to-do and its inline steps."""
        report: dict[str, Any] = {
            "todos_created": 0,
            "todos_updated": 0,
            "todos_unchanged": 0,
            "todo_errors": [],
            "dry_run": False,
        }

        proj_mapping = await BasecampService._find_project_mapping(
            db=db,
            company_id=company_id,
            account_id=credentials.account_id,
            basecamp_project_id=bucket_id,
        )
        if proj_mapping is None:
            report["todo_errors"].append(
                f"project {bucket_id}: no local basecamp_project_mapping"
            )
            return report

        token = await BasecampService._get_valid_access_token(credentials, db)
        detail = await BasecampService._get_todo_detail(
            token,
            credentials.account_id,
            bucket_id,
            todo_id,
        )
        effective_todolist_id = (
            todolist_id
            or str(
                (detail.get("parent") or {}).get("id")
                if isinstance(detail.get("parent"), dict)
                else ""
            )
        )

        list_title = ""
        if effective_todolist_id:
            try:
                todolist = await BasecampService._get_todolist_detail(
                    token,
                    credentials.account_id,
                    bucket_id,
                    effective_todolist_id,
                )
                list_title = (
                    todolist.get("title")
                    or todolist.get("name")
                    or ""
                )
            except BasecampError:
                list_title = ""

        todo_tx = await db.begin_nested()
        try:
            parent_task, parent_mapping = await BasecampService._upsert_todo(
                db=db,
                company_id=company_id,
                account_id=credentials.account_id,
                basecamp_project_id=bucket_id,
                todolist_id=effective_todolist_id or "0",
                list_title=list_title,
                internal_project_id=proj_mapping.internal_project_id,
                todo=detail,
                dry_run=False,
                report=report,
                triggered_by_user_id=None,
                triggered_by_user_email=None,
                basecamp_type="Todo",
                parent_task_id=None,
            )

            parent_todo_title = (
                detail.get("content")
                or detail.get("title")
                or detail.get("name")
                or f"Basecamp item {todo_id}"
            )

            detail_steps = detail.get("steps") or []
            for step in detail_steps:
                await BasecampService._upsert_step(
                    db=db,
                    company_id=company_id,
                    account_id=credentials.account_id,
                    basecamp_project_id=bucket_id,
                    todolist_id=effective_todolist_id or "0",
                    list_title=list_title,
                    internal_project_id=proj_mapping.internal_project_id,
                    parent_task=parent_task,
                    parent_basecamp_todo_id=todo_id,
                    parent_todo_title=parent_todo_title,
                    step=step,
                    dry_run=False,
                    report=report,
                    triggered_by_user_id=None,
                    triggered_by_user_email=None,
                )

            await BasecampService._reconcile_missing_steps(
                db=db,
                company_id=company_id,
                account_id=credentials.account_id,
                parent_task=parent_task,
                current_steps=detail_steps,
                dry_run=False,
                report=report,
            )

            parent_status = str(detail.get("status") or "").lower()
            if parent_status in {"archived", "trashed"}:
                await BasecampService._archive_child_steps_for_parent(
                    db=db,
                    company_id=company_id,
                    account_id=credentials.account_id,
                    parent_task=parent_task,
                    dry_run=False,
                    report=report,
                )

            parent_mapping.basecamp_updated_at = _parse_basecamp_datetime(
                detail.get("updated_at")
            )
            parent_mapping.last_synced_at = datetime.now(timezone.utc)
            await todo_tx.commit()
        except Exception:
            await todo_tx.rollback()
            raise

        await db.flush()
        return report

    @staticmethod
    async def resync_todolist_for_company(
        *,
        credentials: BasecampCredentials,
        company_id: int,
        db: AsyncSession,
        bucket_id: str,
        todolist_id: str,
    ) -> dict:
        """Refetch a Basecamp to-do list and upsert each child to-do."""
        report: dict[str, Any] = {
            "todos_created": 0,
            "todos_updated": 0,
            "todos_unchanged": 0,
            "todo_errors": [],
            "dry_run": False,
        }

        proj_mapping = await BasecampService._find_project_mapping(
            db=db,
            company_id=company_id,
            account_id=credentials.account_id,
            basecamp_project_id=bucket_id,
        )
        if proj_mapping is None:
            report["todo_errors"].append(
                f"project {bucket_id}: no local basecamp_project_mapping"
            )
            return report

        token = await BasecampService._get_valid_access_token(credentials, db)
        todolist = await BasecampService._get_todolist_detail(
            token,
            credentials.account_id,
            bucket_id,
            todolist_id,
        )
        list_title = todolist.get("title") or todolist.get("name") or ""
        todos = await BasecampService._list_todos_in_list(
            token,
            credentials.account_id,
            bucket_id,
            todolist_id,
        )

        for td in todos:
            single = await BasecampService.sync_single_todo_for_company(
                credentials=credentials,
                company_id=company_id,
                db=db,
                bucket_id=bucket_id,
                todo_id=str(td.get("id")),
                todolist_id=todolist_id,
            )
            report["todos_created"] += int(single.get("todos_created", 0))
            report["todos_updated"] += int(single.get("todos_updated", 0))
            report["todos_unchanged"] += int(single.get("todos_unchanged", 0))
            report["todo_errors"].extend(single.get("todo_errors", []))

        # Preserve list title fetch side-effect for observability and future
        # debugging even when todos are empty.
        if not list_title and not todos:
            logger.debug(
                "basecamp.webhook.todolist_empty bucket_id=%s todolist_id=%s",
                bucket_id,
                todolist_id,
            )

        await db.flush()
        return report

    @staticmethod
    async def sync_todos_for_company(
        credentials: BasecampCredentials,
        company_id: int,
        db: AsyncSession,
        dry_run: bool = False,
        triggered_by_user_id: Optional[int] = None,
        triggered_by_user_email: Optional[str] = None,
    ) -> dict:
        """Mirror Basecamp to-dos as TimeTracker ``Task`` rows.

        For every ``basecamp_project_mappings`` row owned by the
        company, fetch the to-do lists + to-dos under that Basecamp
        project and upsert a ``Task`` per to-do. Idempotent: re-running
        on unchanged data produces ``todos_created=0`` and
        ``todos_updated=0``.

        Error boundaries:
          * Per-project: a failure fetching to-do lists is recorded in
            ``todo_errors`` and the next project still runs.
          * Per-list: a failure fetching to-dos is recorded and the
            next list still runs.
          * Per-to-do: a per-row exception is recorded and the next
            to-do still runs.

        Task name format::

            "[List title] To-do content"

        Status mapping (verified against the actual ``Task.status``
        values in the TimeTracker codebase — comment in
        ``app/models/__init__.py`` documents them as TODO /
        IN_PROGRESS / DONE):
          * Basecamp ``completed=True``  -> TimeTracker ``status="DONE"``
          * Basecamp ``completed=False`` -> TimeTracker ``status="TODO"``
        """
        report: dict[str, Any] = {
            "todos_created": 0,
            "todos_updated": 0,
            "todos_unchanged": 0,
            "todo_errors": [],
            "dry_run": dry_run,
        }

        mapping_rows = await db.execute(
            select(BasecampProjectMapping).where(
                BasecampProjectMapping.company_id == company_id,
                BasecampProjectMapping.basecamp_account_id
                == credentials.account_id,
            )
        )
        project_mappings = mapping_rows.scalars().all()
        if not project_mappings:
            return report

        try:
            token = await BasecampService._get_valid_access_token(
                credentials, db
            )
        except BasecampError as exc:
            report["todo_errors"].append(str(exc))
            return report

        actor_user_id, actor_user_email, sync_mode = (
            BasecampService._resolve_sync_actor(
                triggered_by_user_id,
                triggered_by_user_email,
            )
        )

        for proj_mapping in project_mappings:
            bc_project_id = proj_mapping.basecamp_project_id
            internal_project_id = proj_mapping.internal_project_id

            try:
                todolists = await BasecampService._list_todolists(
                    token, credentials.account_id, bc_project_id
                )
            except BasecampError as exc:
                report["todo_errors"].append(
                    f"project {bc_project_id} todolists: {exc}"
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.exception("basecamp.todos.todolists_failed")
                report["todo_errors"].append(
                    f"project {bc_project_id} todolists: {exc}"
                )
                continue

            for lst in todolists:
                lst_id = lst["id"]
                lst_title = lst["title"]

                try:
                    todos = await BasecampService._list_todos_in_list(
                        token,
                        credentials.account_id,
                        bc_project_id,
                        lst_id,
                    )
                except BasecampError as exc:
                    report["todo_errors"].append(
                        f"list {lst_id}: {exc}"
                    )
                    continue
                except Exception as exc:  # noqa: BLE001
                    logger.exception("basecamp.todos.list_failed")
                    report["todo_errors"].append(
                        f"list {lst_id}: {exc}"
                    )
                    continue

                for td in todos:
                    todo_tx = await db.begin_nested()
                    try:
                        todo_id = str(td.get("id"))
                        mapping = await BasecampService._find_task_mapping(
                            db=db,
                            company_id=company_id,
                            account_id=credentials.account_id,
                            basecamp_resource_id=todo_id,
                            basecamp_type="Todo",
                        )

                        list_updated_at = _parse_basecamp_datetime(td.get("updated_at"))
                        if (
                            mapping is not None
                            and mapping.basecamp_updated_at is not None
                            and list_updated_at is not None
                            and list_updated_at <= mapping.basecamp_updated_at
                        ):
                            report["todos_unchanged"] += 1
                            await todo_tx.commit()
                            continue

                        detail = await BasecampService._get_todo_detail(
                            token,
                            credentials.account_id,
                            bc_project_id,
                            todo_id,
                        )

                        parent_task, parent_mapping = await BasecampService._upsert_todo(
                            db=db,
                            company_id=company_id,
                            account_id=credentials.account_id,
                            basecamp_project_id=bc_project_id,
                            todolist_id=lst_id,
                            list_title=lst_title,
                            internal_project_id=internal_project_id,
                            todo=detail,
                            dry_run=dry_run,
                            report=report,
                            triggered_by_user_id=triggered_by_user_id,
                            triggered_by_user_email=triggered_by_user_email,
                            basecamp_type="Todo",
                            parent_task_id=None,
                        )
                        parent_todo_title = (
                            detail.get("content")
                            or detail.get("title")
                            or detail.get("name")
                            or f"Basecamp item {todo_id}"
                        )

                        detail_steps = detail.get("steps") or []
                        for step in detail_steps:
                            await BasecampService._upsert_step(
                                db=db,
                                company_id=company_id,
                                account_id=credentials.account_id,
                                basecamp_project_id=bc_project_id,
                                todolist_id=lst_id,
                                list_title=lst_title,
                                internal_project_id=internal_project_id,
                                parent_task=parent_task,
                                parent_basecamp_todo_id=todo_id,
                                parent_todo_title=parent_todo_title,
                                step=step,
                                dry_run=dry_run,
                                report=report,
                                triggered_by_user_id=triggered_by_user_id,
                                triggered_by_user_email=triggered_by_user_email,
                            )

                        await BasecampService._reconcile_missing_steps(
                            db=db,
                            company_id=company_id,
                            account_id=credentials.account_id,
                            parent_task=parent_task,
                            current_steps=detail_steps,
                            dry_run=dry_run,
                            report=report,
                        )

                        parent_status = str(detail.get("status") or "").lower()
                        if parent_status in {"archived", "trashed"}:
                            await BasecampService._archive_child_steps_for_parent(
                                db=db,
                                company_id=company_id,
                                account_id=credentials.account_id,
                                parent_task=parent_task,
                                dry_run=dry_run,
                                report=report,
                            )

                        if not dry_run:
                            detail_updated_at = _parse_basecamp_datetime(
                                detail.get("updated_at")
                            )
                            parent_mapping.basecamp_updated_at = detail_updated_at
                            parent_mapping.last_synced_at = datetime.now(timezone.utc)
                        await todo_tx.commit()
                    except BasecampError as exc:
                        await todo_tx.rollback()
                        logger.exception("basecamp.todos.todo_detail_failed")
                        report["todo_errors"].append(
                            f"todo {td.get('id')}: {exc}"
                        )
                        if not dry_run:
                            await AuditLogger.log(
                                db=db,
                                action=AuditAction.UPDATE,
                                resource_type="basecamp.sync.errored",
                                user_id=actor_user_id,
                                user_email=actor_user_email,
                                details=(
                                    f"Failed syncing Basecamp todo {td.get('id')} "
                                    f"in project {bc_project_id} via {sync_mode}: {exc}"
                                ),
                            )
                    except Exception as exc:  # noqa: BLE001
                        await todo_tx.rollback()
                        logger.exception("basecamp.todos.todo_failed")
                        report["todo_errors"].append(
                            f"todo {td.get('id')}: {exc}"
                        )

        if not dry_run:
            await db.flush()

        return report

    @staticmethod
    async def _upsert_todo(
        *,
        db: AsyncSession,
        company_id: int,
        account_id: str,
        basecamp_project_id: str,
        todolist_id: str,
        list_title: str,
        internal_project_id: int,
        todo: dict,
        dry_run: bool,
        report: dict,
        triggered_by_user_id: Optional[int],
        triggered_by_user_email: Optional[str],
        basecamp_type: str = "Todo",
        parent_task_id: Optional[int] = None,
    ) -> tuple[Task, BasecampTaskMapping]:
        """Create or update a single Task + its BasecampTaskMapping row."""
        todo_id = str(todo["id"])
        todo_content = (
            todo.get("content")
            or todo.get("title")
            or todo.get("name")
            or f"Basecamp item {todo_id}"
        )
        target_name = f"[{list_title}] {todo_content}" if list_title else todo_content
        # Preserve any richer Basecamp description body in
        # tasks.description; fall back to the to-do content so the
        # description always carries useful context.
        bc_description = todo.get("description")
        target_description = (
            bc_description if bc_description else todo_content
        )
        basecamp_status = str(todo.get("status") or "").lower()
        if basecamp_status in {"archived", "trashed"}:
            target_status = "ARCHIVED"
        else:
            target_status = "DONE" if bool(todo.get("completed", False)) else "TODO"

        # Parse the disambiguation metadata once. ``due_on`` is a
        # date string ("YYYY-MM-DD"); ``created_at`` is ISO 8601
        # (Basecamp emits a trailing "Z" that ``fromisoformat`` only
        # handles natively from Python 3.11+; replace to be safe).
        target_due_on = _parse_basecamp_date(todo.get("due_on"))
        target_created_at = _parse_basecamp_datetime(todo.get("created_at"))
        raw_position = todo.get("position")
        target_position = int(raw_position) if raw_position is not None else None
        actor_user_id, actor_user_email, sync_mode = (
            BasecampService._resolve_sync_actor(
                triggered_by_user_id,
                triggered_by_user_email,
            )
        )

        existing_row = await db.execute(
            select(BasecampTaskMapping).where(
                BasecampTaskMapping.company_id == company_id,
                BasecampTaskMapping.basecamp_account_id == account_id,
                BasecampTaskMapping.basecamp_type == basecamp_type,
                BasecampTaskMapping.basecamp_todo_id == todo_id,
            )
        )
        mapping = existing_row.scalar_one_or_none()

        if mapping is None:
            if dry_run:
                report["todos_created"] += 1
                return (
                    Task(
                        project_id=internal_project_id,
                        parent_task_id=parent_task_id,
                        name=target_name,
                        description=target_description,
                        status=target_status,
                    ),
                    BasecampTaskMapping(
                        company_id=company_id,
                        basecamp_account_id=account_id,
                        basecamp_project_id=basecamp_project_id,
                        basecamp_todolist_id=todolist_id,
                        basecamp_type=basecamp_type,
                        basecamp_todo_id=todo_id,
                        basecamp_due_on=target_due_on,
                        basecamp_todo_created_at=target_created_at,
                        basecamp_todo_position=target_position,
                        task_id=0,
                    ),
                )
            task = Task(
                project_id=internal_project_id,
                parent_task_id=parent_task_id,
                name=target_name,
                description=target_description,
                status=target_status,
            )
            db.add(task)
            await db.flush()
            await AuditLogger.log(
                db=db,
                action=AuditAction.CREATE,
                resource_type="task",
                resource_id=task.id,
                user_id=actor_user_id,
                user_email=actor_user_email,
                new_values={
                    "project_id": task.project_id,
                    "name": task.name,
                    "description": task.description,
                    "status": task.status,
                    "basecamp_project_id": basecamp_project_id,
                    "basecamp_todo_id": todo_id,
                },
                details=(
                    f"Created from Basecamp to-do {todo_id} in project "
                    f"{basecamp_project_id} via {sync_mode}"
                ),
            )
            db.add(
                BasecampTaskMapping(
                    company_id=company_id,
                    basecamp_account_id=account_id,
                    basecamp_project_id=basecamp_project_id,
                    basecamp_todolist_id=todolist_id,
                    basecamp_type=basecamp_type,
                    basecamp_todo_id=todo_id,
                    basecamp_due_on=target_due_on,
                    basecamp_todo_created_at=target_created_at,
                    basecamp_todo_position=target_position,
                    task_id=task.id,
                    last_synced_at=datetime.now(timezone.utc),
                )
            )
            await db.flush()
            mapping = await BasecampService._find_task_mapping(
                db=db,
                company_id=company_id,
                account_id=account_id,
                basecamp_resource_id=todo_id,
                basecamp_type=basecamp_type,
            )
            report["todos_created"] += 1
            if mapping is None:
                raise RuntimeError(
                    f"Failed to reload mapping for Basecamp {basecamp_type} {todo_id}"
                )
            return task, mapping

        task_row = await db.execute(
            select(Task).where(Task.id == mapping.task_id)
        )
        task = task_row.scalar_one_or_none()
        if task is None:
            # Linked task was deleted out from under us; recreate.
            if dry_run:
                report["todos_created"] += 1
                return (
                    Task(
                        project_id=internal_project_id,
                        parent_task_id=parent_task_id,
                        name=target_name,
                        description=target_description,
                        status=target_status,
                    ),
                    mapping,
                )
            task = Task(
                project_id=internal_project_id,
                parent_task_id=parent_task_id,
                name=target_name,
                description=target_description,
                status=target_status,
            )
            db.add(task)
            await db.flush()
            await AuditLogger.log(
                db=db,
                action=AuditAction.CREATE,
                resource_type="task",
                resource_id=task.id,
                user_id=actor_user_id,
                user_email=actor_user_email,
                new_values={
                    "project_id": task.project_id,
                    "name": task.name,
                    "description": task.description,
                    "status": task.status,
                    "basecamp_project_id": basecamp_project_id,
                    "basecamp_todo_id": todo_id,
                },
                details=(
                    f"Recreated missing task from Basecamp to-do {todo_id} "
                    f"in project {basecamp_project_id} via {sync_mode}"
                ),
            )
            mapping.task_id = task.id
            mapping.basecamp_todolist_id = todolist_id
            mapping.basecamp_project_id = basecamp_project_id
            mapping.basecamp_type = basecamp_type
            mapping.basecamp_due_on = target_due_on
            mapping.basecamp_todo_created_at = target_created_at
            mapping.basecamp_todo_position = target_position
            mapping.last_synced_at = datetime.now(timezone.utc)
            report["todos_created"] += 1
            return task, mapping

        # Change detection: include the new metadata fields so the
        # existing 6020 mapping rows backfill their NULL columns on
        # the next sync run instead of being marked "unchanged"
        # forever based purely on name/status/description.
        metadata_changed = (
            mapping.basecamp_due_on != target_due_on
            or mapping.basecamp_todo_created_at != target_created_at
            or mapping.basecamp_todo_position != target_position
        )
        changed = (
            task.name != target_name
            or task.status != target_status
            or task.description != target_description
            or metadata_changed
        )
        if changed:
            if not dry_run:
                task.name = target_name
                task.description = target_description
                task.status = target_status
                task.parent_task_id = parent_task_id
                mapping.basecamp_todolist_id = todolist_id
                mapping.basecamp_project_id = basecamp_project_id
                mapping.basecamp_type = basecamp_type
                mapping.basecamp_due_on = target_due_on
                mapping.basecamp_todo_created_at = target_created_at
                mapping.basecamp_todo_position = target_position
                mapping.last_synced_at = datetime.now(timezone.utc)
            report["todos_updated"] += 1
        else:
            if not dry_run:
                task.parent_task_id = parent_task_id
                mapping.last_synced_at = datetime.now(timezone.utc)
            report["todos_unchanged"] += 1
        return task, mapping

    @staticmethod
    async def _upsert_step(
        *,
        db: AsyncSession,
        company_id: int,
        account_id: str,
        basecamp_project_id: str,
        todolist_id: str,
        list_title: str,
        internal_project_id: int,
        parent_task: Task,
        parent_basecamp_todo_id: str,
        parent_todo_title: str,
        step: dict,
        dry_run: bool,
        report: dict,
        triggered_by_user_id: Optional[int],
        triggered_by_user_email: Optional[str],
    ) -> None:
        """Create or update a Basecamp ``Kanban::Step`` child task."""
        step_id_raw = step.get("id")
        if step_id_raw is None:
            logger.debug("basecamp.steps.missing_id parent_todo=%s", parent_basecamp_todo_id)
            return
        step_id = str(step_id_raw)

        parent_data = step.get("parent")
        parent_id = None
        if isinstance(parent_data, dict) and parent_data.get("id") is not None:
            parent_id = str(parent_data.get("id"))
        if parent_id and parent_id != parent_basecamp_todo_id:
            parent_mapping = await BasecampService._find_task_mapping(
                db=db,
                company_id=company_id,
                account_id=account_id,
                basecamp_resource_id=parent_id,
                basecamp_type="Todo",
            )
            if parent_mapping is None:
                logger.debug(
                    "basecamp.steps.unknown_parent_skip step_id=%s parent_id=%s",
                    step_id,
                    parent_id,
                )
            else:
                logger.debug(
                    "basecamp.steps.parent_mismatch_skip step_id=%s expected_parent_id=%s actual_parent_id=%s",
                    step_id,
                    parent_basecamp_todo_id,
                    parent_id,
                )
            return

        step_title = (
            step.get("content")
            or step.get("title")
            or step.get("name")
            or step_id
        )
        step_payload = {
            "id": step_id,
            "content": f"{parent_todo_title} / {step_title}",
            "description": step.get("description"),
            "completed": bool(step.get("completed", False)),
            "due_on": step.get("due_on"),
            "created_at": step.get("created_at"),
            "position": step.get("position"),
            "updated_at": step.get("updated_at"),
        }
        step_task, step_mapping = await BasecampService._upsert_todo(
            db=db,
            company_id=company_id,
            account_id=account_id,
            basecamp_project_id=basecamp_project_id,
            todolist_id=todolist_id,
            list_title=list_title,
            internal_project_id=internal_project_id,
            todo=step_payload,
            dry_run=dry_run,
            report=report,
            triggered_by_user_id=triggered_by_user_id,
            triggered_by_user_email=triggered_by_user_email,
            basecamp_type="Kanban::Step",
            parent_task_id=parent_task.id,
        )

        if not dry_run:
            if str((step.get("status") or "")).lower() in {"archived", "trashed"}:
                step_task.status = "ARCHIVED"
            if parent_task.status == "ARCHIVED":
                step_task.status = "ARCHIVED"
            step_mapping.basecamp_updated_at = _parse_basecamp_datetime(
                step.get("updated_at")
            )

    @staticmethod
    async def _reconcile_missing_steps(
        *,
        db: AsyncSession,
        company_id: int,
        account_id: str,
        parent_task: Task,
        current_steps: list[dict],
        dry_run: bool,
        report: dict,
    ) -> None:
        """Archive child step tasks no longer present in the latest detail payload."""
        current_ids = {
            str(step.get("id")) for step in (current_steps or []) if step.get("id") is not None
        }
        rows = await db.execute(
            select(Task, BasecampTaskMapping)
            .join(BasecampTaskMapping, BasecampTaskMapping.task_id == Task.id)
            .where(
                Task.parent_task_id == parent_task.id,
                BasecampTaskMapping.company_id == company_id,
                BasecampTaskMapping.basecamp_account_id == account_id,
                BasecampTaskMapping.basecamp_type == "Kanban::Step",
            )
        )
        for child_task, child_mapping in rows.all():
            if child_mapping.basecamp_todo_id in current_ids:
                continue
            if child_task.status == "ARCHIVED":
                continue
            if not dry_run:
                child_task.status = "ARCHIVED"
                child_mapping.last_synced_at = datetime.now(timezone.utc)
            report["todos_updated"] += 1

    @staticmethod
    async def _archive_child_steps_for_parent(
        *,
        db: AsyncSession,
        company_id: int,
        account_id: str,
        parent_task: Task,
        dry_run: bool,
        report: dict,
    ) -> None:
        """Cascade archival from a parent to-do to all mapped child steps."""
        rows = await db.execute(
            select(Task, BasecampTaskMapping)
            .join(BasecampTaskMapping, BasecampTaskMapping.task_id == Task.id)
            .where(
                Task.parent_task_id == parent_task.id,
                BasecampTaskMapping.company_id == company_id,
                BasecampTaskMapping.basecamp_account_id == account_id,
                BasecampTaskMapping.basecamp_type == "Kanban::Step",
            )
        )
        for child_task, child_mapping in rows.all():
            if child_task.status == "ARCHIVED":
                continue
            if not dry_run:
                child_task.status = "ARCHIVED"
                child_mapping.last_synced_at = datetime.now(timezone.utc)
            report["todos_updated"] += 1

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
                resp = await _http_request_with_retry(
                    client,
                    "POST",
                    LAUNCHPAD_REVOKE_URL,
                    params={"token": access_token},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            return resp.status_code in (200, 204)
        except httpx.HTTPError as exc:
            logger.warning("basecamp.revoke.failed: %s", exc)
            return False

    @staticmethod
    def _resolve_sync_actor(
        triggered_by_user_id: Optional[int],
        triggered_by_user_email: Optional[str],
    ) -> tuple[Optional[int], str, str]:
        """Resolve audit actor identity for manual vs unattended sync runs."""
        if triggered_by_user_id is not None:
            return (
                triggered_by_user_id,
                triggered_by_user_email or BASECAMP_SYNC_SYSTEM_EMAIL,
                "manual sync",
            )
        return (None, BASECAMP_SYNC_SYSTEM_EMAIL, "daily scheduler")


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


def _parse_basecamp_date(value: Any) -> Optional[date]:
    """Parse Basecamp's ``due_on`` ("YYYY-MM-DD") into a ``date``.

    Returns ``None`` for missing / empty / unparseable values rather
    than propagating an error: the disambiguation metadata is
    best-effort and must not break to-do sync.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        logger.warning("basecamp.todo.due_on.unparseable: %r", value)
        return None


def _parse_basecamp_datetime(value: Any) -> Optional[datetime]:
    """Parse a Basecamp ISO 8601 timestamp (e.g. ``created_at``).

    Basecamp emits timestamps with a trailing ``Z``; Python's
    ``datetime.fromisoformat`` only handles that natively from 3.11+,
    so we replace it to be safe on any supported runtime.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("basecamp.todo.created_at.unparseable: %r", value)
        return None
