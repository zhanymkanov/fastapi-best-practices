from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    is_active: bool = True


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    code: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    code: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
