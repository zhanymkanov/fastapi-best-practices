"""
API 路由总入口

注意：
  - tickets 和 members 子路由在各自模块中已设置了 prefix（/tickets, /members）
  - agent 和 rag 子路由在各自模块中也设置了 prefix（/agent, /rag）
  - 在此文件中 include_router 时不需要再次指定 prefix
"""
from fastapi import APIRouter

from app.api.v1 import (
    agent,       # A2A 多 Agent 编排接口（prefix: /agent）
    auth,        # 登录鉴权
    dashboard,   # 仪表盘统计
    devices,     # IoT 设备管理
    ingestion,   # 数据资产摄取
    members,     # 会员权益管理（prefix: /members）
    pets,        # 宠物管理
    rag,         # RAG 知识库问答（prefix: /rag）
    tenants,     # 租户管理
    tickets,     # 客服工单（prefix: /tickets）
    users,       # 用户管理
)

api_router = APIRouter()

# ── 核心业务路由（子模块未设置 prefix，在此指定） ─────────────────────────────
api_router.include_router(auth.router,      prefix="/v1/auth",      tags=["认证"])
api_router.include_router(tenants.router,   prefix="/v1/tenants",   tags=["租户管理"])
api_router.include_router(users.router,     prefix="/v1/users",     tags=["用户管理"])
api_router.include_router(pets.router,      prefix="/v1/pets",      tags=["宠物管理"])
api_router.include_router(devices.router,   prefix="/v1/devices",   tags=["设备管理"])
api_router.include_router(dashboard.router, prefix="/v1/dashboard", tags=["仪表盘"])
api_router.include_router(ingestion.router, prefix="/v1/assets",    tags=["数据资产"])

# ── AI / 智能体路由（子模块已包含 prefix） ──────────────────────────────────
api_router.include_router(agent.router,   prefix="/v1")
api_router.include_router(rag.router,     prefix="/v1")
api_router.include_router(tickets.router, prefix="/v1")
api_router.include_router(members.router, prefix="/v1")
