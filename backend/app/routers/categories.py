"""Categories CRUD router."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.schemas.categories import (
    CategoryCreate,
    CategoryDeleteResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.category_service import (
    create_category,
    get_category_creator_name,
    get_category_for_company,
    get_category_task_count,
    list_categories,
    soft_delete_category,
    update_category,
)

router = APIRouter()

HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_color(color: str) -> str:
    if not HEX_COLOR_PATTERN.fullmatch(color):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Color must be a valid hex value like #3B82F6",
        )
    return color.upper()


def _ensure_company_user(user: User) -> int:
    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Categories require a company-scoped user",
        )
    return user.company_id


async def _to_response(db: AsyncSession, category) -> CategoryResponse:
    task_count = await get_category_task_count(db, category.id)
    created_by_name = await get_category_creator_name(db, category.created_by)
    return CategoryResponse(
        id=category.id,
        name=category.name,
        color=category.color,
        description=category.description,
        task_count=task_count,
        created_at=category.created_at,
        created_by_name=created_by_name,
        updated_at=category.updated_at,
    )


@router.get("", response_model=list[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[CategoryResponse]:
    company_id = _ensure_company_user(current_user)
    categories = await list_categories(db, company_id, include_deleted=False)
    return [await _to_response(db, category) for category in categories]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def post_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CategoryResponse:
    company_id = _ensure_company_user(current_user)

    category = await create_category(
        db=db,
        company_id=company_id,
        user_id=current_user.id,
        name=payload.name.strip(),
        color=_validate_color(payload.color),
        description=payload.description,
    )

    await AuditLogger.log(
        db=db,
        action=AuditAction.CREATE,
        resource_type="category",
        resource_id=category.id,
        user_id=current_user.id,
        user_email=current_user.email,
        new_values={
            "name": category.name,
            "color": category.color,
            "description": category.description,
        },
        details=f"Created category '{category.name}'",
    )
    await db.commit()
    await db.refresh(category)

    return await _to_response(db, category)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CategoryResponse:
    company_id = _ensure_company_user(current_user)
    category = await get_category_for_company(
        db,
        category_id,
        company_id,
        include_deleted=False,
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    return await _to_response(db, category)


@router.put("/{category_id}", response_model=CategoryResponse)
async def put_category(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CategoryResponse:
    company_id = _ensure_company_user(current_user)
    category = await get_category_for_company(
        db,
        category_id,
        company_id,
        include_deleted=False,
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    old_values = {
        "name": category.name,
        "color": category.color,
        "description": category.description,
    }

    updated = await update_category(
        db=db,
        category=category,
        user_id=current_user.id,
        name=payload.name.strip() if payload.name is not None else None,
        color=_validate_color(payload.color) if payload.color is not None else None,
        description=payload.description,
    )

    new_values = {
        "name": updated.name,
        "color": updated.color,
        "description": updated.description,
    }

    if old_values != new_values:
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="category",
            resource_id=updated.id,
            user_id=current_user.id,
            user_email=current_user.email,
            old_values=old_values,
            new_values=new_values,
            details=f"Updated category '{updated.name}'",
        )

    await db.commit()
    await db.refresh(updated)
    return await _to_response(db, updated)


@router.delete("/{category_id}", response_model=CategoryDeleteResponse)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CategoryDeleteResponse:
    company_id = _ensure_company_user(current_user)
    category = await get_category_for_company(
        db,
        category_id,
        company_id,
        include_deleted=False,
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    old_values = {
        "name": category.name,
        "color": category.color,
        "description": category.description,
    }

    affected_task_count = await soft_delete_category(
        db,
        category,
        current_user.id,
    )

    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="category",
        resource_id=category.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values=old_values,
        new_values={
            "deleted": True,
            "affected_task_count": affected_task_count,
        },
        details=(
            f"Soft-deleted category '{category.name}' and removed associations "
            f"from {affected_task_count} tasks"
        ),
    )

    await db.commit()

    return CategoryDeleteResponse(
        id=category.id,
        task_count=affected_task_count,
        message="Category soft-deleted successfully",
    )
