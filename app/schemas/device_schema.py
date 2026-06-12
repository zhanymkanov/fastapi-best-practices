from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    device_code: str = Field(..., min_length=1, max_length=128)
    device_type: str = Field(..., min_length=1, max_length=64)
    pet_id: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None


class DeviceUpdate(BaseModel):
    tenant_id: Optional[str] = Field(default=None, min_length=1)
    device_code: Optional[str] = Field(default=None, min_length=1, max_length=128)
    device_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    pet_id: Optional[str] = None
    is_online: Optional[bool] = None
    last_seen: Optional[datetime] = None


class DeviceResponse(BaseModel):
    id: str = Field(alias="_id")
    tenant_id: str
    pet_id: Optional[str] = None
    device_code: str
    device_type: str
    is_online: bool
    last_seen: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
