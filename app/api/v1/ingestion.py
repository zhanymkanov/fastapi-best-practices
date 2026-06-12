"""
数据采集 API — 文件上传 / 查询 / 管理
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.data_schema import (
    AssetStatusSummary,
    AssetTagUpdate,
    DataAssetListResponse,
    DataAssetResponse,
)
from app.services.audit_service import AuditService
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.get("/", response_model=DataAssetListResponse)
async def list_assets(
    asset_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    pet_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """分页查询数据资产"""
    items, total = await IngestionService.find_all(
        tenant_id=current_user.tenant_id,
        asset_type=asset_type,
        status=status,
        pet_id=pet_id,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile,
    tags: str = "",                    # 逗号分隔标签
    pet_id: Optional[str] = None,
    source: str = "upload",
    current_user: User = Depends(get_current_user),
):
    """上传文件采集数据（图片/音频/视频）"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    content_type = file.content_type or "application/octet-stream"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    try:
        asset = await IngestionService.ingest(
            tenant_id=current_user.tenant_id,
            user_id=str(current_user.id),
            file=file.file,
            filename=file.filename,
            content_type=content_type,
            tags=tag_list,
            pet_id=pet_id,
            source=source,
        )
        await AuditService.log(
            actor=current_user,
            action="asset.upload",
            resource_type="data_asset",
            resource_id=str(asset.id),
            detail={"filename": asset.filename, "asset_type": asset.asset_type.value},
        )
        return {
            "id": str(asset.id),
            "filename": asset.filename,
            "md5_hash": asset.md5_hash,
            "status": asset.status.value,
            "message": "文件已上传，正在后台处理",
        }
    except ValueError as e:
        # 文件重复 / 格式不支持
        if "已存在" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary", response_model=AssetStatusSummary)
async def asset_summary(current_user: User = Depends(get_current_user)):
    """获取资产状态统计"""
    summary = await IngestionService.get_status_summary(current_user.tenant_id)
    return summary


@router.get("/{asset_id}", response_model=DataAssetResponse)
async def get_asset(asset_id: str, current_user: User = Depends(get_current_user)):
    """获取资产详情"""
    asset = await IngestionService.get(asset_id, current_user.tenant_id)
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    return asset


@router.put("/{asset_id}/tags", response_model=DataAssetResponse)
async def update_asset_tags(
    asset_id: str,
    data: AssetTagUpdate,
    current_user: User = Depends(get_current_user),
):
    """更新资产标签"""
    asset = await IngestionService.update_tags(
        asset_id, current_user.tenant_id, data.tags
    )
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    await AuditService.log(
        actor=current_user,
        action="asset.tags.update",
        resource_type="data_asset",
        resource_id=asset_id,
        detail={"tags": data.tags},
    )
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(asset_id: str, current_user: User = Depends(get_current_user)):
    """软删除资产"""
    ok = await IngestionService.soft_delete(asset_id, current_user.tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    await AuditService.log(
        actor=current_user,
        action="asset.delete",
        resource_type="data_asset",
        resource_id=asset_id,
    )
