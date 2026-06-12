"""
仪表盘 API — 平台数据概览与统计

端点：
  GET /api/v1/dashboard/overview     — 平台核心指标概览
  GET /api/v1/dashboard/tenant-stats — 租户维度统计（管理员）

数据来源：
  - MongoDB 各业务集合实时聚合查询
  - 未连接数据库时返回 0 值（不阻塞启动）
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.core.deps import RBACChecker, get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


async def _safe_count(collection_name: str, query: dict | None = None) -> int:
    """安全计数查询，出错时返回 0"""
    try:
        from app.core.database import get_database
        db = get_database()
        coll = db[collection_name]
        return await coll.count_documents(query or {})
    except Exception as exc:
        logger.debug("仪表盘查询 %s 失败: %s", collection_name, exc)
        return 0


@router.get("/overview", summary="平台核心指标概览")
async def dashboard_overview(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    返回平台核心运营指标。

    指标说明：
    - total_tenants：     租户总数
    - total_users：       注册用户总数
    - total_pets：        宠物档案总数
    - online_devices：    在线 IoT 设备数
    - open_tickets：      待处理工单数
    - total_assets：      数据资产总数
    """
    tenant_id = getattr(current_user, "tenant_id", "default")
    user_role = getattr(current_user, "role", "member")

    # 管理员看全平台，普通用户只看自己租户
    tenant_filter = {} if user_role in ("admin", "super_admin") else {"tenant_id": tenant_id}

    # 并行查询各集合（独立计数，出错不影响其他指标）
    total_tenants = await _safe_count("tenants", {})
    total_users = await _safe_count("users", tenant_filter)
    total_pets = await _safe_count("pets", {**tenant_filter, "is_deleted": False})
    online_devices = await _safe_count("devices", {**tenant_filter, "is_online": True})
    total_devices = await _safe_count("devices", tenant_filter)
    open_tickets = await _safe_count("tickets", {**tenant_filter, "status": {"$in": ["open", "processing", "pending_customer", "escalated"]}})
    total_tickets = await _safe_count("tickets", tenant_filter)
    total_assets = await _safe_count("data_assets", tenant_filter)

    return {
        "total_tenants": total_tenants,
        "total_users": total_users,
        "total_pets": total_pets,
        "total_devices": total_devices,
        "online_devices": online_devices,
        "offline_devices": total_devices - online_devices,
        "open_tickets": open_tickets,
        "total_tickets": total_tickets,
        "total_assets": total_assets,
        "device_online_rate": f"{(online_devices / total_devices * 100):.1f}%" if total_devices > 0 else "N/A",
        "ticket_resolution_rate": f"{((total_tickets - open_tickets) / total_tickets * 100):.1f}%" if total_tickets > 0 else "N/A",
    }


@router.get("/tenant-stats", summary="租户维度统计")
async def tenant_stats(
    current_user: User = Depends(RBACChecker(["admin", "super_admin"])),
) -> dict[str, Any]:
    """
    按租户维度统计各业务数据（仅管理员可见）。

    返回每个租户的用户数、宠物数、设备数、工单数。
    """
    try:
        from app.core.database import get_database
        db = get_database()

        # 租户维度聚合
        pipeline = [
            {"$group": {
                "_id": "$tenant_id",
                "users": {"$sum": 1},
            }},
        ]
        # 并行查询各集合的租户分布
        tenant_ids: set[str] = set()

        # 用户按租户统计
        users_by_tenant: dict[str, int] = {}
        try:
            async for doc in db["users"].aggregate([
                {"$group": {"_id": "$tenant_id", "count": {"$sum": 1}}}
            ]):
                tid = doc["_id"]
                users_by_tenant[tid] = doc["count"]
                tenant_ids.add(tid)
        except Exception:
            pass

        # 宠物按租户统计
        pets_by_tenant: dict[str, int] = {}
        try:
            async for doc in db["pets"].aggregate([
                {"$match": {"is_deleted": False}},
                {"$group": {"_id": "$tenant_id", "count": {"$sum": 1}}}
            ]):
                pets_by_tenant[doc["_id"]] = doc["count"]
                tenant_ids.add(doc["_id"])
        except Exception:
            pass

        # 设备按租户统计
        devices_by_tenant: dict[str, int] = {}
        try:
            async for doc in db["devices"].aggregate([
                {"$group": {"_id": "$tenant_id", "count": {"$sum": 1}}}
            ]):
                devices_by_tenant[doc["_id"]] = doc["count"]
                tenant_ids.add(doc["_id"])
        except Exception:
            pass

        # 工单按租户统计
        tickets_by_tenant: dict[str, int] = {}
        try:
            async for doc in db["tickets"].aggregate([
                {"$group": {"_id": "$tenant_id", "count": {"$sum": 1}}}
            ]):
                tickets_by_tenant[doc["_id"]] = doc["count"]
                tenant_ids.add(doc["_id"])
        except Exception:
            pass

        items = []
        for tid in sorted(tenant_ids):
            items.append({
                "tenant_id": tid,
                "users": users_by_tenant.get(tid, 0),
                "pets": pets_by_tenant.get(tid, 0),
                "devices": devices_by_tenant.get(tid, 0),
                "tickets": tickets_by_tenant.get(tid, 0),
            })

        return {"items": items, "total": len(items)}

    except Exception as exc:
        logger.exception("租户统计查询失败: %s", exc)
        return {"items": [], "total": 0, "error": "数据库查询失败"}
