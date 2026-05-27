from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task


async def resolve_description(
    description: Optional[str],
    task_id: Optional[int],
    db: AsyncSession,
) -> Optional[str]:
    """Fill empty descriptions from task name when a task is selected.

    Rule:
    - If description is None/whitespace-only and task_id is set, try task.name.
    - If task lookup fails, keep the submitted description unchanged.
    - Otherwise, return the submitted description unchanged.
    """
    if task_id is None:
        return description

    if description is None or description.strip() == "":
        task_name_result = await db.execute(select(Task.name).where(Task.id == task_id))
        task_name = task_name_result.scalar_one_or_none()
        if task_name is not None:
            return task_name

    return description
