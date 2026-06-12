"""
数据采集服务 — AI 数据收集 MVP 核心

参考 dialog（3）load_csv.py 的模式：
1. 文件内容 MD5 → 去重检查
2. 格式校验
3. 存储（预留 MinIO 集成）
4. 异步处理任务投递

去重策略：
- 同一租户内，相同 MD5 的文件视为重复
- 跨租户不做去重（每个租户数据隔离）
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import BinaryIO, Optional

from app.models.data_asset import AssetStatus, AssetType, DataAsset

# 支持的文件类型
ALLOWED_MIME_TYPES = {
    "image": {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "image/bmp", "image/tiff",
    },
    "audio": {
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/aac",
        "audio/flac", "audio/mp4",
    },
    "video": {
        "video/mp4", "video/webm", "video/ogg", "video/avi",
        "video/quicktime",
    },
    "text": {
        "text/plain", "text/csv", "text/markdown",
        "application/json", "application/xml", "application/pdf",
    },
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
UPLOAD_DIR = "uploads"  # 本地存储目录（后续切 MinIO）


def _get_asset_type(content_type: str) -> AssetType:
    """根据 MIME type 推断资产类型"""
    for atype, mimes in ALLOWED_MIME_TYPES.items():
        if content_type in mimes:
            return AssetType(atype)
    return AssetType.OTHER


def _compute_md5(content: bytes) -> str:
    """计算文件内容 MD5（参考 dialog 的 load_csv.py 去重模式）"""
    return hashlib.md5(content).hexdigest()


def _ensure_upload_dir(tenant_id: str) -> str:
    """确保租户上传目录存在"""
    path = os.path.join(UPLOAD_DIR, tenant_id)
    os.makedirs(path, exist_ok=True)
    return path


class IngestionService:
    """数据采集服务"""

    @classmethod
    async def find_by_md5(cls, tenant_id: str, md5_hash: str) -> Optional[DataAsset]:
        """按 MD5 查找是否已存在（去重检查）"""
        return await DataAsset.find_one({
            "tenant_id": tenant_id,
            "md5_hash": md5_hash,
            "status": {"$ne": AssetStatus.DELETED},
        })

    @classmethod
    async def ingest(
        cls,
        tenant_id: str,
        user_id: str,
        file: BinaryIO,
        filename: str,
        content_type: str,
        tags: list[str] | None = None,
        pet_id: str | None = None,
        source: str = "upload",
        source_device_id: str = "",
    ) -> DataAsset:
        """文件采集入口 — 上传 → 校验 → 去重 → 存储"""

        # 1. 读取文件内容
        content = file.read()

        # 2. 格式校验
        asset_type = _get_asset_type(content_type)
        if asset_type == AssetType.OTHER:
            raise ValueError(f"不支持的文件类型: {content_type}")

        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件过大: {len(content)} bytes (最大 {MAX_FILE_SIZE})")

        # 3. MD5 去重（核心：参考 dialog load_csv.py 的 hashlib 模式）
        md5_hash = _compute_md5(content)
        existing = await cls.find_by_md5(tenant_id, md5_hash)
        if existing:
            raise ValueError(f"文件已存在 (asset_id={existing.id}), MD5: {md5_hash[:8]}...")

        # 4. 本地存储
        upload_dir = _ensure_upload_dir(tenant_id)
        # 安全文件名
        safe_filename = f"{md5_hash}{os.path.splitext(filename)[1]}"
        storage_path = os.path.join(upload_dir, safe_filename)
        with open(storage_path, "wb") as f:
            f.write(content)

        # 5. 写入 MongoDB 元数据
        asset = DataAsset(
            tenant_id=tenant_id,
            uploaded_by=user_id,
            filename=filename,
            content_type=content_type,
            asset_type=asset_type,
            file_size=len(content),
            md5_hash=md5_hash,
            storage_path=storage_path,
            tags=tags or [],
            source=source,
            source_device_id=source_device_id,
            pet_id=pet_id,
            status=AssetStatus.PENDING,
        )
        await asset.insert()

        # 6. 异步处理（投递 Celery 任务：生成缩略图 / 计算向量）
        cls._dispatch_processing(asset.id, tenant_id)

        return asset

    @classmethod
    def _dispatch_processing(cls, asset_id: str, tenant_id: str) -> None:
        """投递异步处理任务"""
        try:
            from app.tasks.ingestion_task import process_asset
            process_asset.delay(str(asset_id), tenant_id)
        except ImportError:
            pass  # Celery 未配置时静默跳过

    @classmethod
    async def find_all(
        cls,
        tenant_id: str,
        asset_type: str | None = None,
        status: str | None = None,
        pet_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DataAsset], int]:
        """分页查询数据资产"""
        query: dict = {
            "tenant_id": tenant_id,
            "status": {"$ne": AssetStatus.DELETED},
        }
        if asset_type:
            query["asset_type"] = asset_type
        if status:
            query["status"] = status
        if pet_id:
            query["pet_id"] = pet_id

        total = await DataAsset.find(query).count()
        items = await DataAsset.find(query).skip((page - 1) * page_size).limit(page_size).to_list()
        return items, total

    @classmethod
    async def get(cls, asset_id: str, tenant_id: str) -> Optional[DataAsset]:
        """获取单个资产"""
        return await DataAsset.find_one({
            "_id": asset_id,
            "tenant_id": tenant_id,
            "status": {"$ne": AssetStatus.DELETED},
        })

    @classmethod
    async def soft_delete(cls, asset_id: str, tenant_id: str) -> bool:
        """软删除资产"""
        asset = await cls.get(asset_id, tenant_id)
        if not asset:
            return False
        await asset.update({
            "$set": {
                "status": AssetStatus.DELETED,
                "updated_at": datetime.now(timezone.utc),
            }
        })
        return True

    @classmethod
    async def update_tags(cls, asset_id: str, tenant_id: str, tags: list[str]) -> Optional[DataAsset]:
        """更新标签"""
        asset = await cls.get(asset_id, tenant_id)
        if not asset:
            return None
        await asset.update({"$set": {"tags": tags, "updated_at": datetime.now(timezone.utc)}})
        return await cls.get(asset_id, tenant_id)

    @classmethod
    async def get_status_summary(cls, tenant_id: str) -> dict:
        """获取状态统计"""
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "status": {"$ne": "deleted"}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        rows = await DataAsset.aggregate(pipeline).to_list()
        summary = {"pending": 0, "processing": 0, "ready": 0, "failed": 0, "total": 0}
        for row in rows:
            status = row["_id"]
            if status in summary:
                summary[status] = row["count"]
            summary["total"] += row["count"]
        return summary
