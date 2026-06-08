from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import apply_company_filter
from app.models import Project, ProjectTeam, Task, TimeEntry, User
from app.services.audit_logger import AuditAction, AuditLogger


@dataclass
class ProjectDeleteResult:
    deleted_tasks: int
    deleted_entries: int
    deleted_project_teams: int


@dataclass
class ProjectMergePreview:
    tasks_to_move: int
    entries_to_move: int
    task_name_conflicts: list[str]
    target_existing_tasks: int
    source_will_be_archived: bool


@dataclass
class ProjectMergeResult:
    moved_tasks: int
    moved_entries: int
    renamed_tasks: list[str]
    archived_source: bool


@dataclass
class ProjectSimilarityMatch:
    id: int
    name: str
    team_id: int
    team_name: str
    is_archived: bool
    match_type: Literal["exact", "substring", "fuzzy"]
    match_score: float


def normalize_for_comparison(name: str) -> str:
    """Lowercase, trim, and remove non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def _levenshtein_with_cutoff(left: str, right: str, cutoff: int) -> int:
    """Compute Levenshtein distance with early-exit once cutoff is exceeded."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if abs(len(left) - len(right)) > cutoff:
        return cutoff + 1

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        row_min = i
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (0 if left_char == right_char else 1)
            value = min(insert_cost, delete_cost, replace_cost)
            current.append(value)
            if value < row_min:
                row_min = value

        if row_min > cutoff:
            return cutoff + 1
        previous = current

    return previous[-1]


async def find_similar_projects(
    db: AsyncSession,
    company_id: int | str,
    name: str,
    exclude_id: int | None = None,
    include_archived: bool = False,
) -> list[ProjectSimilarityMatch]:
    """Return projects in the same company whose names are similar to ``name``."""
    normalized_input = normalize_for_comparison(name)
    if not normalized_input:
        return []

    # Keep company scoping aligned with existing project routes.
    from app.models import Team

    query = select(Project, Team.name).join(Team, Project.team_id == Team.id)
    query = apply_company_filter(query, Team.company_id, company_id)

    if exclude_id is not None:
        query = query.where(Project.id != exclude_id)
    if not include_archived:
        query = query.where(Project.is_archived.is_(False))

    rows = (await db.execute(query)).all()

    matches: list[ProjectSimilarityMatch] = []
    for project, team_name in rows:
        normalized_project = normalize_for_comparison(project.name)
        if not normalized_project:
            continue

        match_type: Literal["exact", "substring", "fuzzy"] | None = None
        match_score = 0.0

        if normalized_project == normalized_input:
            match_type = "exact"
            match_score = 1.0
        elif (
            normalized_project in normalized_input
            or normalized_input in normalized_project
        ):
            shorter = min(len(normalized_project), len(normalized_input))
            longer = max(len(normalized_project), len(normalized_input))
            overlap_ratio = shorter / longer if longer else 0
            match_type = "substring"
            match_score = round(0.8 + min(0.1, overlap_ratio * 0.1), 2)
        else:
            distance = _levenshtein_with_cutoff(normalized_project, normalized_input, cutoff=2)
            if distance <= 2:
                match_type = "fuzzy"
                match_score = 0.7 if distance == 1 else 0.6

        if match_type is None:
            continue

        matches.append(
            ProjectSimilarityMatch(
                id=project.id,
                name=project.name,
                team_id=project.team_id,
                team_name=team_name or "Unknown",
                is_archived=project.is_archived,
                match_type=match_type,
                match_score=match_score,
            )
        )

    matches.sort(key=lambda row: (-row.match_score, row.name.lower(), row.id))
    return matches[:10]


async def delete_project_with_cascade(
    *,
    db: AsyncSession,
    project: Project,
    acting_user: User,
) -> ProjectDeleteResult:
    """Hard-delete a project and all dependent rows in one transaction."""
    try:
        deleted_tasks = (
            await db.execute(
                select(func.count(Task.id)).where(Task.project_id == project.id)
            )
        ).scalar() or 0
        deleted_entries = (
            await db.execute(
                select(func.count(TimeEntry.id)).where(TimeEntry.project_id == project.id)
            )
        ).scalar() or 0
        deleted_project_teams = (
            await db.execute(
                select(func.count(ProjectTeam.id)).where(ProjectTeam.project_id == project.id)
            )
        ).scalar() or 0

        # Log before deleting so a trace remains after the project row is gone.
        await AuditLogger.log(
            db=db,
            action=AuditAction.DELETE,
            resource_type="project",
            resource_id=project.id,
            user_id=acting_user.id,
            user_email=acting_user.email,
            old_values={
                "id": project.id,
                "name": project.name,
                "team_id": project.team_id,
                "deleted_tasks": deleted_tasks,
                "deleted_entries": deleted_entries,
                "deleted_project_teams": deleted_project_teams,
            },
            new_values=None,
            details=f"Hard-deleted project '{project.name}' with cascaded dependencies",
        )

        await db.execute(delete(TimeEntry).where(TimeEntry.project_id == project.id))
        await db.execute(delete(Task).where(Task.project_id == project.id))
        await db.execute(delete(ProjectTeam).where(ProjectTeam.project_id == project.id))
        await db.delete(project)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return ProjectDeleteResult(
        deleted_tasks=deleted_tasks,
        deleted_entries=deleted_entries,
        deleted_project_teams=deleted_project_teams,
    )


async def get_merge_preview(
    *,
    db: AsyncSession,
    source_project: Project,
    target_project: Project,
) -> ProjectMergePreview:
    source_task_names = {
        name
        for (name,) in (
            await db.execute(select(Task.name).where(Task.project_id == source_project.id))
        ).all()
    }
    target_task_names = {
        name
        for (name,) in (
            await db.execute(select(Task.name).where(Task.project_id == target_project.id))
        ).all()
    }

    task_count = (
        await db.execute(select(func.count(Task.id)).where(Task.project_id == source_project.id))
    ).scalar() or 0
    entry_count = (
        await db.execute(
            select(func.count(TimeEntry.id)).where(TimeEntry.project_id == source_project.id)
        )
    ).scalar() or 0

    return ProjectMergePreview(
        tasks_to_move=task_count,
        entries_to_move=entry_count,
        task_name_conflicts=sorted(source_task_names.intersection(target_task_names)),
        target_existing_tasks=len(target_task_names),
        source_will_be_archived=True,
    )


async def merge_projects(
    *,
    db: AsyncSession,
    source_project: Project,
    target_project: Project,
    acting_user: User,
    fail_after_task_move_for_test: bool = False,
) -> ProjectMergeResult:
    """Merge source project into target project in one atomic transaction."""
    renamed_tasks: list[str] = []

    try:
        target_task_names = {
            name
            for (name,) in (
                await db.execute(select(Task.name).where(Task.project_id == target_project.id))
            ).all()
        }

        source_tasks = (
            await db.execute(select(Task).where(Task.project_id == source_project.id))
        ).scalars().all()

        moved_tasks = 0
        for task in source_tasks:
            original_name = task.name
            if original_name in target_task_names:
                candidate = f"{original_name} (from {source_project.name})"
                suffix = 2
                while candidate in target_task_names:
                    candidate = f"{original_name} (from {source_project.name}) {suffix}"
                    suffix += 1
                task.name = candidate
                renamed_tasks.append(candidate)
                target_task_names.add(candidate)
            else:
                target_task_names.add(original_name)

            task.project_id = target_project.id
            moved_tasks += 1

        if fail_after_task_move_for_test:
            raise RuntimeError("Simulated merge failure for transaction rollback test")

        moved_entries_result = await db.execute(
            update(TimeEntry)
            .where(TimeEntry.project_id == source_project.id)
            .values(project_id=target_project.id)
        )
        moved_entries = moved_entries_result.rowcount or 0

        source_team_ids = {
            team_id
            for (team_id,) in (
                await db.execute(
                    select(ProjectTeam.team_id).where(ProjectTeam.project_id == source_project.id)
                )
            ).all()
        }
        target_team_ids = {
            team_id
            for (team_id,) in (
                await db.execute(
                    select(ProjectTeam.team_id).where(ProjectTeam.project_id == target_project.id)
                )
            ).all()
        }
        for team_id in source_team_ids.difference(target_team_ids):
            db.add(
                ProjectTeam(
                    project_id=target_project.id,
                    team_id=team_id,
                    added_by_user_id=acting_user.id,
                )
            )

        await db.execute(delete(ProjectTeam).where(ProjectTeam.project_id == source_project.id))
        source_project.is_archived = True

        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="project",
            resource_id=source_project.id,
            user_id=acting_user.id,
            user_email=acting_user.email,
            old_values={"is_archived": False, "team_id": source_project.team_id},
            new_values={
                "is_archived": True,
                "merged_into_project_id": target_project.id,
                "moved_tasks": moved_tasks,
                "moved_entries": moved_entries,
                "renamed_tasks": renamed_tasks,
            },
            details=f"Merged project '{source_project.name}' into '{target_project.name}'",
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return ProjectMergeResult(
        moved_tasks=moved_tasks,
        moved_entries=moved_entries,
        renamed_tasks=renamed_tasks,
        archived_source=True,
    )
