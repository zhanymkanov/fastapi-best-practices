"""数据资产 Schema"""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class DataAssetResponse(BaseModel):
    """数据资产响应"""
    id: str = Field(alias="_id")
    tenant_id: str
    uploaded_by: str
    filename: str
    content_type: str
    asset_type: str
    file_size: int
    md5_hash: str
    storage_path: str
    thumbnail_path: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_ms: Optional[int] = None
    tags: list[str]
    source: str
    source_device_id: str
    pet_id: Optional[str] = None
    status: str
    error_message: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class DataAssetListResponse(BaseModel):
    """数据资产列表"""
    items: list[DataAssetResponse]
    total: int
    page: int = 1
    page_size: int = 20


class AssetTagUpdate(BaseModel):
    """更新标签"""
    tags: list[str] = Field(..., min_length=1)


class AssetStatusSummary(BaseModel):
    """状态统计"""
    pending: int = 0
    processing: int = 0
    ready: int = 0
    failed: int = 0
    total: int = 0
