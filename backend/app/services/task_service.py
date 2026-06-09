"""Task-related domain helpers."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Task, TaskTeam, Team


async def get_task_teams_map(db: AsyncSession, task_ids: list[int]) -> dict[int, list[dict[str, object]]]:
    """Return a mapping of task_id -> [{id, name, color}] for each task."""
    if not task_ids:
        return {}

    rows = (
        await db.execute(
            select(TaskTeam.task_id, Team.id, Team.name, Team.color)
            .join(Team, Team.id == TaskTeam.team_id)
            .where(TaskTeam.task_id.in_(task_ids), Team.deleted_at.is_(None))
            .order_by(TaskTeam.task_id.asc(), Team.name.asc())
        )
    ).all()

    mapping: dict[int, list[dict[str, object]]] = {task_id: [] for task_id in task_ids}
    for task_id, team_id, team_name, team_color in rows:
        mapping.setdefault(task_id, []).append(
            {
                "id": team_id,
                "name": team_name,
                "color": team_color,
            }
        )
    return mapping


async def apply_teams_to_task(
    db: AsyncSession,
    task_id: int,
    team_ids: list[int],
    user_id: int,
) -> tuple[list[int], list[int]]:
    """Replace a task's team assignments and return (added_ids, removed_ids)."""
    desired_ids = sorted(set(team_ids))

    current_ids = sorted(
        (
            await db.execute(select(TaskTeam.team_id).where(TaskTeam.task_id == task_id))
        ).scalars().all()
    )

    task_company_id = (
        await db.execute(
            select(Team.company_id)
            .join(Project, Project.team_id == Team.id)
            .join(Task, Task.project_id == Project.id)
            .where(Task.id == task_id)
        )
    ).scalar_one_or_none()

    if task_company_id is None:
        raise ValueError("Task not found")

    if desired_ids:
        valid_count = (
            await db.execute(
                select(Team.id)
                .where(
                    Team.id.in_(desired_ids),
                    Team.company_id == task_company_id,
                    Team.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        if len(valid_count) != len(desired_ids):
            raise ValueError("One or more teams are invalid for this task")

    await db.execute(delete(TaskTeam).where(TaskTeam.task_id == task_id))
    for team_id in desired_ids:
        db.add(TaskTeam(task_id=task_id, team_id=team_id, created_by=user_id))

    old_set = set(current_ids)
    new_set = set(desired_ids)
    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    return added, removed
