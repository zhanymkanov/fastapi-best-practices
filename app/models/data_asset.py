"""
数据资产 Document — AI 数据收集平台核心模型

参考 dialog（3）的 contents 表设计：
- 内容去重：MD5 hash of file content
- 元数据：格式 / 大小 / 维度 / 采集来源
- 可关联宠物档案
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document


class AssetType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    OTHER = "other"


class AssetStatus(str, Enum):
    PENDING = "pending"          # 刚上传，等待处理
    PROCESSING = "processing"    # 正在处理（生成缩略图/嵌入向量）
    READY = "ready"              # 可用
    FAILED = "failed"            # 处理失败
    DELETED = "deleted"          # 已删除


class DataAsset(Document):
    tenant_id: str
    uploaded_by: str                     # 上传者 user_id
    # 文件信息
    filename: str
    content_type: str                    # MIME type
    asset_type: AssetType = AssetType.IMAGE
    file_size: int                       # 字节
    # 去重
    md5_hash: str                        # 文件内容 MD5（主去重键）
    # 存储
    storage_path: str = ""               # MinIO / 本地文件路径
    thumbnail_path: str = ""             # 缩略图路径
    # 元数据
    width: Optional[int] = None          # 图片/视频宽度
    height: Optional[int] = None         # 图片/视频高度
    duration_ms: Optional[int] = None    # 音频/视频时长
    tags: list[str] = []
    source: str = "upload"               # 采集来源：upload / device / api / crawl
    source_device_id: str = ""           # 关联 IoT 设备
    # 关联
    pet_id: Optional[str] = None         # 关联宠物档案
    # 向量（为后续 RAG 检索预留）
    embedding: list[float] = []          # 图片/文本的向量嵌入
    embedding_model: str = ""            # 用的什么模型
    # 状态
    status: AssetStatus = AssetStatus.PENDING
    error_message: str = ""
    processing_at: Optional[datetime] = None
    # 时间戳
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "data_assets"
        indexes = [
            "tenant_id",
            "uploaded_by",
            [("tenant_id", 1), ("md5_hash", 1)],    # 去重查询
            [("tenant_id", 1), ("asset_type", 1)],   # 按类型过滤
            [("tenant_id", 1), ("pet_id", 1)],        # 按宠物关联
            [("tenant_id", 1), ("status", 1)],        # 状态过滤
            "source_device_id",
        ]
