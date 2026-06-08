"""Category service helpers for task categories."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Project, Task, TaskCategory, Team, User


async def list_categories(
    db: AsyncSession,
    company_id: int,
    include_deleted: bool = False,
) -> list[Category]:
    query = select(Category).where(Category.company_id == company_id)
    if not include_deleted:
        query = query.where(Category.deleted_at.is_(None))
    query = query.order_by(Category.name.asc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def _ensure_unique_name(
    db: AsyncSession,
    company_id: int,
    name: str,
    exclude_id: Optional[int] = None,
) -> None:
    query = select(Category.id).where(
        Category.company_id == company_id,
        func.lower(Category.name) == name.lower(),
        Category.deleted_at.is_(None),
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)

    existing = (await db.execute(query)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category name already exists",
        )


async def create_category(
    db: AsyncSession,
    company_id: int,
    user_id: int,
    name: str,
    color: str,
    description: Optional[str],
) -> Category:
    await _ensure_unique_name(db, company_id, name)

    category = Category(
        company_id=company_id,
        name=name.strip(),
        color=color,
        description=description,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


async def get_category_for_company(
    db: AsyncSession,
    category_id: int,
    company_id: int,
    include_deleted: bool = True,
) -> Optional[Category]:
    query = select(Category).where(
        Category.id == category_id,
        Category.company_id == company_id,
    )
    if not include_deleted:
        query = query.where(Category.deleted_at.is_(None))
    return (await db.execute(query)).scalar_one_or_none()


async def update_category(
    db: AsyncSession,
    category: Category,
    user_id: int,
    name: Optional[str] = None,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> Category:
    if name is not None and name.strip() != category.name:
        await _ensure_unique_name(
            db,
            category.company_id,
            name.strip(),
            exclude_id=category.id,
        )
        category.name = name.strip()

    if color is not None:
        category.color = color

    if description is not None:
        category.description = description

    category.updated_by = user_id
    category.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(category)
    return category


async def soft_delete_category(
    db: AsyncSession,
    category: Category,
    user_id: int,
) -> int:
    affected_count = (
        await db.execute(
            select(func.count(TaskCategory.task_id)).where(
                TaskCategory.category_id == category.id
            )
        )
    ).scalar_one()

    await db.execute(
        delete(TaskCategory).where(TaskCategory.category_id == category.id)
    )

    category.deleted_at = datetime.now(timezone.utc)
    category.deleted_by = user_id
    category.updated_by = user_id
    category.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return int(affected_count or 0)


async def apply_categories_to_task(
    db: AsyncSession,
    task_id: int,
    category_ids: list[int],
    user_id: int,
) -> None:
    task_row = await db.execute(
        select(Task.id, Team.company_id)
        .join(Project, Project.id == Task.project_id)
        .join(Team, Team.id == Project.team_id)
        .where(Task.id == task_id)
    )
    task_info = task_row.one_or_none()
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    _, task_company_id = task_info

    unique_ids = sorted(set(category_ids))
    if unique_ids:
        categories = (
            await db.execute(
                select(Category.id).where(
                    Category.id.in_(unique_ids),
                    Category.company_id == task_company_id,
                    Category.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        if len(categories) != len(unique_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more category_ids are invalid for this task",
            )

    await db.execute(delete(TaskCategory).where(TaskCategory.task_id == task_id))

    for category_id in unique_ids:
        db.add(
            TaskCategory(
                task_id=task_id,
                category_id=category_id,
                created_by=user_id,
            )
        )

    await db.flush()


async def get_task_categories_map(
    db: AsyncSession,
    task_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    if not task_ids:
        return {}

    rows = (
        await db.execute(
            select(TaskCategory.task_id, Category.id, Category.name, Category.color)
            .join(Category, Category.id == TaskCategory.category_id)
            .where(
                TaskCategory.task_id.in_(task_ids),
                Category.deleted_at.is_(None),
            )
            .order_by(Category.name.asc())
        )
    ).all()

    category_map: dict[int, list[dict[str, Any]]] = {task_id: [] for task_id in task_ids}
    for task_id, category_id, name, color in rows:
        category_map.setdefault(task_id, []).append(
            {"id": category_id, "name": name, "color": color}
        )
    return category_map


async def get_category_task_count(db: AsyncSession, category_id: int) -> int:
    count = (
        await db.execute(
            select(func.count(TaskCategory.task_id)).where(
                TaskCategory.category_id == category_id
            )
        )
    ).scalar_one()
    return int(count or 0)


async def get_category_creator_name(db: AsyncSession, user_id: Optional[int]) -> Optional[str]:
    if user_id is None:
        return None
    return (
        await db.execute(select(User.name).where(User.id == user_id))
    ).scalar_one_or_none()
