"""
数据库初始化 — MongoDB + Beanie ODM

支持 Demo 模式：当 MongoDB 不可用时，应用仍可正常启动，
MCP 工具、Agent 编排、RAG 检索等核心功能不受影响。
仅 CRUD 业务接口（用户/宠物/设备/工单）需要 MongoDB。
"""
from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.models.tenant import Tenant
from app.models.user import User
from app.models.device import Device
from app.models.pet import Pet
from app.models.data_asset import DataAsset
from app.models.audit_log import AuditLog
from app.models.permission import RolePermission
from app.models.ticket import Ticket, TicketReply

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db_available: bool = False


async def init_db() -> None:
    """初始化 MongoDB 连接和 Beanie ODM（失败时降级为 Demo 模式）"""
    global _client, _db_available

    try:
        # Step 1: 创建异步 MongoDB 客户端
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=3000,  # 3 秒超时，快速失败
            connectTimeoutMS=3000,
        )
        # Step 2: 测试连接（ping 命令）
        await _client.admin.command("ping")
        # Step 3: 初始化 Beanie ODM（自动创建集合和索引）
        await init_beanie(
            database=_client[settings.MONGODB_DB_NAME],
            document_models=[
                Tenant, User, Device, Pet, DataAsset,
                RolePermission, AuditLog, Ticket, TicketReply,
            ],
        )
        _db_available = True
        logger.info("MongoDB 已连接: %s/%s", settings.MONGODB_URL, settings.MONGODB_DB_NAME)
    except Exception as exc:
        # 连接失败时进入 Demo 模式
        _db_available = False
        logger.warning(
            "MongoDB 不可用 (%s)，将以 Demo 模式运行。"
            "业务 CRUD 接口将返回 Demo 数据，Agent / MCP / RAG 功能不受影响。",
            exc,
        )


async def close_db() -> None:
    """断开 MongoDB 连接（应用关闭时调用）"""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB 连接已断开")


def get_database():
    """获取数据库实例（Demo 模式下返回 None）"""
    if not _db_available or _client is None:
        raise RuntimeError("数据库不可用，当前运行在 Demo 模式下，此接口需要 MongoDB")
    return _client[settings.MONGODB_DB_NAME]


def is_db_available() -> bool:
    """检查数据库是否可用（用于判断是否进入 Demo 模式）"""
    return _db_available
