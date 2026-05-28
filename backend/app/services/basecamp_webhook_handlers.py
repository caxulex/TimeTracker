"""Basecamp webhook event handlers.

Routes normalized event kinds to the existing Basecamp sync upsert paths.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BasecampCredentials
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.basecamp_service import BasecampService

logger = logging.getLogger(__name__)

_TODO_EVENT_KINDS = {
    "todo_created",
    "todo_updated",
    "todo_completed",
    "todo_uncompleted",
    "todo_archived",
    "todo_trashed",
    "todo_unarchived",
    "todo_restored",
    "kanban_step_created",
    "kanban_step_updated",
    "kanban_step_completed",
    "kanban_step_uncompleted",
    "kanban_step_archived",
    "kanban_step_trashed",
    "kanban_step_unarchived",
    "kanban_step_restored",
}

_TODOLIST_CASCADE_KINDS = {
    "todolist_archived",
    "todolist_trashed",
    "todolist_unarchived",
    "todolist_restored",
}


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_bucket_id(recording: dict[str, Any]) -> str:
    bucket = recording.get("bucket")
    if isinstance(bucket, dict):
        return _as_str(bucket.get("id"))
    if recording.get("bucket_id") is not None:
        return _as_str(recording.get("bucket_id"))
    parent = recording.get("parent")
    if isinstance(parent, dict):
        parent_bucket = parent.get("bucket")
        if isinstance(parent_bucket, dict):
            return _as_str(parent_bucket.get("id"))
    return ""


def _extract_todo_id(recording: dict[str, Any]) -> str:
    if recording.get("id") is not None:
        return _as_str(recording.get("id"))
    parent = recording.get("parent")
    if isinstance(parent, dict) and parent.get("id") is not None:
        return _as_str(parent.get("id"))
    return ""


def _extract_todolist_id(recording: dict[str, Any]) -> str:
    parent = recording.get("parent")
    if isinstance(parent, dict) and parent.get("id") is not None:
        return _as_str(parent.get("id"))
    if recording.get("id") is not None:
        return _as_str(recording.get("id"))
    return ""


class BasecampWebhookHandlers:
    @classmethod
    async def handle_event(
        cls,
        *,
        event: dict[str, Any],
        credentials: BasecampCredentials,
        db: AsyncSession,
    ) -> None:
        kind = _as_str(event.get("kind")).lower()
        recording = event.get("recording") or {}
        if not isinstance(recording, dict):
            recording = {}

        bucket_id = _extract_bucket_id(recording)

        if kind in _TODO_EVENT_KINDS:
            todo_id = _extract_todo_id(recording)
            todolist_id = _extract_todolist_id(recording)
            if bucket_id and todo_id:
                await BasecampService.sync_single_todo_for_company(
                    credentials=credentials,
                    company_id=credentials.company_id,
                    db=db,
                    bucket_id=bucket_id,
                    todo_id=todo_id,
                    todolist_id=todolist_id or None,
                )
                return

        if kind in _TODOLIST_CASCADE_KINDS:
            todolist_id = _extract_todolist_id(recording)
            if bucket_id and todolist_id:
                await BasecampService.resync_todolist_for_company(
                    credentials=credentials,
                    company_id=credentials.company_id,
                    db=db,
                    bucket_id=bucket_id,
                    todolist_id=todolist_id,
                )
                return

        # Default fallback for unknown kinds: log + attempt safe refetch.
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="basecamp.webhook.unhandled_kind",
            user_id=None,
            user_email="basecamp-webhook@system",
            details=(
                f"Unhandled Basecamp webhook kind={kind or 'unknown'} "
                f"event_id={_as_str(event.get('id')) or 'unknown'}"
            ),
            new_values={
                "kind": kind,
                "event_id": _as_str(event.get("id")),
                "bucket_id": bucket_id,
            },
        )

        todo_id = _extract_todo_id(recording)
        todolist_id = _extract_todolist_id(recording)
        if bucket_id and todo_id:
            try:
                await BasecampService.sync_single_todo_for_company(
                    credentials=credentials,
                    company_id=credentials.company_id,
                    db=db,
                    bucket_id=bucket_id,
                    todo_id=todo_id,
                    todolist_id=todolist_id or None,
                )
            except Exception:
                logger.exception(
                    "basecamp.webhook.fallback_refetch_failed kind=%s event_id=%s",
                    kind,
                    _as_str(event.get("id")),
                )
