from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
