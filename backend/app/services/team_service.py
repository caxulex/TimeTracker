"""Team lifecycle service (soft-delete + restore)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import apply_company_filter
from app.models import Project, Team
from app.services.audit_logger import AuditLogger


async def soft_delete_team(
    team_id: int,
    company_id: Optional[int] | str,
    acting_user_id: int,
    acting_user_email: str,
    reason: Optional[str],
    db: AsyncSession,
) -> tuple[bool, Optional[str]]:
    """Soft-delete a team scoped to company.

    Returns ``(success, error_code)`` where ``error_code`` is one of:
    ``not_found``, ``already_deleted``, ``has_active_projects``.
    """
    team_query = select(Team).where(Team.id == team_id)
    team_query = apply_company_filter(team_query, Team.company_id, company_id)
    team_result = await db.execute(team_query.with_for_update())
    team = team_result.scalar_one_or_none()
    if team is None:
        return False, "not_found"

    if team.deleted_at is not None:
        return False, "already_deleted"

    active_projects_count = await db.scalar(
        select(func.count(Project.id)).where(
            Project.team_id == team_id,
            Project.is_archived == False,
        )
    )
    if active_projects_count and active_projects_count > 0:
        return False, "has_active_projects"

    deleted_at = datetime.now(timezone.utc)
    team.deleted_at = deleted_at
    team.deleted_by_user_id = acting_user_id
    team.delete_reason = reason

    await AuditLogger.log(
        db=db,
        action="team.soft_deleted",
        resource_type="team",
        resource_id=team.id,
        user_id=acting_user_id,
        user_email=acting_user_email,
        new_values={
            "deleted_at": deleted_at.isoformat(),
            "delete_reason": reason,
            "active_projects_count_at_delete": 0,
        },
        details=f"Soft-deleted team '{team.name}'",
    )

    await db.commit()
    return True, None


async def restore_team(
    team_id: int,
    company_id: Optional[int] | str,
    acting_user_id: int,
    acting_user_email: str,
    db: AsyncSession,
) -> tuple[bool, Optional[str]]:
    """Restore a soft-deleted team.

    Returns ``(success, error_code)`` where ``error_code`` is one of:
    ``not_found``, ``not_deleted``.
    """
    team_query = select(Team).where(Team.id == team_id)
    team_query = apply_company_filter(team_query, Team.company_id, company_id)
    team_result = await db.execute(team_query.with_for_update())
    team = team_result.scalar_one_or_none()
    if team is None:
        return False, "not_found"

    if team.deleted_at is None:
        return False, "not_deleted"

    team.deleted_at = None
    team.deleted_by_user_id = None
    team.delete_reason = None

    await AuditLogger.log(
        db=db,
        action="team.restored",
        resource_type="team",
        resource_id=team.id,
        user_id=acting_user_id,
        user_email=acting_user_email,
        details=f"Restored team '{team.name}'",
    )

    await db.commit()
    return True, None
