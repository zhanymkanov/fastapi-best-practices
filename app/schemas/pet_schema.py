from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ── Pet CRUD Schemas ──────────────────────────────────────────────

class PetCreate(BaseModel):
    """创建宠物档案"""
    name: str = Field(..., min_length=1, max_length=50)
    species: str = "other"
    breed: str = ""
    gender: str = "unknown"
    birth_date: Optional[datetime] = None
    weight_kg: Optional[float] = Field(None, ge=0)
    avatar_url: str = ""
    tags: list[str] = []
    chip_id: Optional[str] = None
    medical_notes: str = ""


class PetUpdate(BaseModel):
    """更新宠物档案（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    species: Optional[str] = None
    breed: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None
    weight_kg: Optional[float] = Field(None, ge=0)
    avatar_url: Optional[str] = None
    tags: Optional[list[str]] = None
    chip_id: Optional[str] = None
    medical_notes: Optional[str] = None


class PetResponse(BaseModel):
    """宠物档案响应（公开字段）"""
    id: str = Field(alias="_id")
    tenant_id: str
    owner_id: str
    name: str
    species: str
    breed: str
    gender: str
    birth_date: Optional[datetime] = None
    weight_kg: Optional[float] = None
    avatar_url: str
    tags: list[str]
    chip_id: Optional[str] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class PetListResponse(BaseModel):
    """宠物列表响应"""
    items: list[PetResponse]
    total: int
    page: int = 1
    page_size: int = 20
