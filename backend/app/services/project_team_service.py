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
    ``different_company``.
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

    existing = await db.execute(
        select(ProjectTeam.id).where(
            ProjectTeam.project_id == project_id,
            ProjectTeam.team_id == team_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return True, None

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
    ``not_found``, ``primary_team``.
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


async def get_projects_for_team(
    team_id: int,
    include_archived: bool = False,
    company_id: Optional[int] | str = None,
    db: AsyncSession | None = None,
) -> list[dict]:
    """Return projects attached to a team through primary or shared membership."""
    if db is None:
        return []

    items_by_project_id: dict[int, dict] = {}

    def _project_payload(project: Project, primary_team_name: Optional[str], association_type: str) -> dict:
        return {
            "id": project.id,
            "name": project.name,
            "color": project.color,
            "is_archived": project.is_archived,
            "primary_team_id": project.team_id,
            "primary_team_name": primary_team_name,
            "association_type": association_type,
        }

    primary_query = (
        select(Project, Team.name)
        .join(Team, Project.team_id == Team.id)
        .where(Project.team_id == team_id)
    )
    associated_query = (
        select(Project, Team.name)
        .join(ProjectTeam, Project.id == ProjectTeam.project_id)
        .join(Team, Project.team_id == Team.id)
        .where(ProjectTeam.team_id == team_id)
    )

    if not include_archived:
        primary_query = primary_query.where(Project.is_archived.is_(False))
        associated_query = associated_query.where(Project.is_archived.is_(False))

    primary_query = apply_company_filter(primary_query, Team.company_id, company_id)
    associated_query = apply_company_filter(associated_query, Team.company_id, company_id)

    primary_rows = (await db.execute(primary_query.order_by(Project.created_at.desc()))).all()
    for project, primary_team_name in primary_rows:
        items_by_project_id[project.id] = _project_payload(
            project,
            primary_team_name,
            "primary",
        )

    associated_rows = (await db.execute(associated_query.order_by(Project.created_at.desc()))).all()
    for project, primary_team_name in associated_rows:
        items_by_project_id.setdefault(
            project.id,
            _project_payload(
                project,
                primary_team_name,
                "additional",
            ),
        )

    return list(items_by_project_id.values())


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
