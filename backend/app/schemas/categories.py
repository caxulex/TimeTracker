"""Pydantic schemas for categories endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#6B7280", min_length=4, max_length=20)
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, min_length=4, max_length=20)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    color: str
    description: Optional[str]
    task_count: int
    created_at: datetime
    created_by_name: Optional[str] = None
    updated_at: datetime


class CategoryDeleteResponse(BaseModel):
    id: int
    task_count: int
    message: str
