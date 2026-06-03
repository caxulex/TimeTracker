"""Project-team association service.

Keeps project primary ownership (``projects.team_id``) while allowing
additional team associations for visibility and time/task workflows.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import apply_company_filter
from app.models import Project, ProjectTeam, Team, TeamMember, User
from app.services.audit_logger import AuditLogger


def build_project_visibility_filter(user_id: int):
    """Return a SQLAlchemy predicate for project visibility by team membership.

    A user can access a project if they belong to:
    - the project's primary team (``projects.team_id``), or
    - any associated team in ``project_teams``.
    """
    user_teams_subquery = select(TeamMember.team_id).where(TeamMember.user_id == user_id)
    visible_via_primary = Project.team_id.in_(user_teams_subquery)
    associated_subquery = select(ProjectTeam.project_id).where(
        ProjectTeam.team_id.in_(user_teams_subquery)
    )
    visible_via_associated = Project.id.in_(associated_subquery)
    return or_(visible_via_primary, visible_via_associated)


async def add_team_to_project(
    project_id: int,
    team_id: int,
    acting_user_id: int,
    acting_user_email: str,
    company_id: Optional[int] | str,
    db: AsyncSession,
) -> tuple[bool, Optional[str]]:
    """Associate a team with a project.

    Returns ``(success, error_code)`` where error_code can be:
    ``project_not_found``, ``team_not_found``, ``already_associated``,
    ``not_team_member``, ``different_company``.
    """
    project_query = (
        select(Project, Team.company_id)
        .join(Team, Project.team_id == Team.id)
        .where(Project.id == project_id)
        .with_for_update()
    )
    project_query = apply_company_filter(project_query, Team.company_id, company_id)
    project_row = (await db.execute(project_query)).first()
    if not project_row:
        return False, "project_not_found"
    project, project_company_id = project_row

    team_query = (
        select(Team)
        .where(Team.id == team_id, Team.deleted_at.is_(None))
        .with_for_update()
    )
    team_query = apply_company_filter(team_query, Team.company_id, company_id)
    team = (await db.execute(team_query)).scalar_one_or_none()
    if not team:
        return False, "team_not_found"

    if project_company_id != team.company_id:
        return False, "different_company"

    member_check = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == acting_user_id,
        )
    )
    if member_check.scalar_one_or_none() is None:
        return False, "not_team_member"

    existing = await db.execute(
        select(ProjectTeam.id).where(
            ProjectTeam.project_id == project_id,
            ProjectTeam.team_id == team_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False, "already_associated"

    association = ProjectTeam(
        project_id=project_id,
        team_id=team_id,
        added_by_user_id=acting_user_id,
    )
    db.add(association)
    await db.flush()

    await AuditLogger.log(
        db=db,
        action="project_team.added",
        resource_type="project_team",
        resource_id=association.id,
        user_id=acting_user_id,
        user_email=acting_user_email,
        new_values={
            "project_id": project.id,
            "team_id": team.id,
            "project_name": project.name,
            "team_name": team.name,
        },
        details="Associated a team with project visibility",
    )
    await db.commit()
    return True, None


async def remove_team_from_project(
    project_id: int,
    team_id: int,
    acting_user_id: int,
    acting_user_email: str,
    company_id: Optional[int] | str,
    db: AsyncSession,
) -> tuple[bool, Optional[str]]:
    """Remove a team's association with a project.

    Returns ``(success, error_code)`` where error_code can be:
    ``not_found``, ``not_team_member``, ``primary_team``.
    """
    project_query = (
        select(Project)
        .join(Team, Project.team_id == Team.id)
        .where(Project.id == project_id)
        .with_for_update()
    )
    project_query = apply_company_filter(project_query, Team.company_id, company_id)
    project = (await db.execute(project_query)).scalar_one_or_none()
    if not project:
        return False, "not_found"

    if project.team_id == team_id:
        return False, "primary_team"

    team_query = select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))
    team_query = apply_company_filter(team_query, Team.company_id, company_id)
    team = (await db.execute(team_query)).scalar_one_or_none()
    if not team:
        return False, "not_found"

    actor_query = select(User).where(User.id == acting_user_id)
    actor = (await db.execute(actor_query)).scalar_one_or_none()
    is_admin = bool(actor and actor.role in ["super_admin", "admin", "company_admin"])
    if not is_admin:
        member_check = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == acting_user_id,
            )
        )
        if member_check.scalar_one_or_none() is None:
            return False, "not_team_member"

    association_query = (
        select(ProjectTeam)
        .where(ProjectTeam.project_id == project_id, ProjectTeam.team_id == team_id)
        .with_for_update()
    )
    association = (await db.execute(association_query)).scalar_one_or_none()
    if not association:
        return False, "not_found"

    await db.delete(association)

    await AuditLogger.log(
        db=db,
        action="project_team.removed",
        resource_type="project_team",
        resource_id=association.id,
        user_id=acting_user_id,
        user_email=acting_user_email,
        old_values={
            "project_id": project.id,
            "team_id": team.id,
            "project_name": project.name,
            "team_name": team.name,
        },
        details="Removed a team from project visibility",
    )
    await db.commit()
    return True, None


async def list_project_teams(
    project_id: int,
    company_id: Optional[int] | str,
    db: AsyncSession,
) -> list[dict]:
    """List all teams associated with a project, with primary team first."""
    project_query = (
        select(Project, Team.name)
        .join(Team, Project.team_id == Team.id)
        .where(Project.id == project_id)
    )
    project_query = apply_company_filter(project_query, Team.company_id, company_id)
    project_row = (await db.execute(project_query)).first()
    if not project_row:
        return []

    project, primary_team_name = project_row

    association_rows = (
        await db.execute(
            select(ProjectTeam, Team.name, User.name)
            .join(Team, Team.id == ProjectTeam.team_id)
            .outerjoin(User, User.id == ProjectTeam.added_by_user_id)
            .where(ProjectTeam.project_id == project_id)
            .order_by(ProjectTeam.added_at.asc())
        )
    ).all()

    details_by_team_id: dict[int, dict] = {}
    for assoc, team_name, added_by_name in association_rows:
        details_by_team_id[assoc.team_id] = {
            "team_id": assoc.team_id,
            "team_name": team_name,
            "is_primary": assoc.team_id == project.team_id,
            "added_by_name": added_by_name,
            "added_at": assoc.added_at,
        }

    primary_row = details_by_team_id.get(project.team_id)
    if primary_row is None:
        primary_row = {
            "team_id": project.team_id,
            "team_name": primary_team_name,
            "is_primary": True,
            "added_by_name": None,
            "added_at": project.created_at,
        }
    else:
        primary_row["is_primary"] = True

    rows = [primary_row]
    for team_id, data in details_by_team_id.items():
        if team_id != project.team_id:
            rows.append(data)
    return rows
