"""
客服工单 API — 完整的 CRUD + 状态流转（MongoDB 持久化）

端点：
  POST   /api/v1/tickets              — 创建工单
  GET    /api/v1/tickets              — 查询工单列表（分页/状态过滤/类别过滤）
  GET    /api/v1/tickets/{ticket_id}  — 查询工单详情（含回复历史）
  PATCH  /api/v1/tickets/{ticket_id}  — 更新工单状态/优先级/指派
  POST   /api/v1/tickets/{ticket_id}/reply    — 添加工单回复
  POST   /api/v1/tickets/{ticket_id}/escalate — 工单升级

工单状态流转：
  open → processing → pending_customer → resolved → closed
           ↓ (紧急)
           escalated → resolved → closed

认证：需要 JWT Bearer Token。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from beanie.odm.operators.update.general import Set
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.models.ticket import (
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketReply,
    TicketStatus,
)
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["客服工单"])


# ── 请求/响应 Schema ───────────────────────────────────────────────────────────

class TicketCreateRequest(BaseModel):
    category: TicketCategory = TicketCategory.OTHER
    title: str = Field(..., min_length=2, max_length=200, description="工单标题")
    description: str = Field(..., min_length=10, max_length=5000, description="问题详细描述")
    priority: TicketPriority = TicketPriority.MEDIUM
    device_code: Optional[str] = Field(default=None, description="关联设备编码")
    pet_id: Optional[str] = Field(default=None, description="关联宠物 ID")
    attachments: list[str] = Field(default_factory=list, description="附件 URL 列表")


class TicketUpdateRequest(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[str] = None
    internal_note: Optional[str] = None


class TicketReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    is_internal: bool = Field(default=False, description="是否为内部备注（用户不可见）")
    attachments: list[str] = Field(default_factory=list)


class TicketEscalateRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="升级原因")
    target_team: Optional[str] = Field(default=None, description="目标处理团队")


class TicketOut(BaseModel):
    ticket_id: str
    category: str
    title: str
    description: str
    status: str
    priority: str
    user_name: str
    created_at: str
    updated_at: str
    reply_count: int = 0


class TicketDetailOut(BaseModel):
    ticket_id: str
    category: str
    title: str
    description: str
    status: str
    priority: str
    user_name: str
    assigned_to: Optional[str] = None
    device_code: Optional[str] = None
    pet_id: Optional[str] = None
    escalated_reason: Optional[str] = None
    created_at: str
    updated_at: str
    replies: list[dict[str, Any]] = Field(default_factory=list)


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def _generate_ticket_id() -> str:
    """生成工单编号：TK-YYYYMMDD-XXXXXXXX"""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    uid = str(uuid.uuid4())[:8].upper()
    return f"TK-{date_part}-{uid}"


def _ticket_to_out(ticket: Ticket, reply_count: int = 0) -> TicketOut:
    """将 Ticket 文档转换为输出格式"""
    return TicketOut(
        ticket_id=ticket.ticket_id,
        category=ticket.category.value if hasattr(ticket.category, 'value') else ticket.category,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
        priority=ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
        user_name=ticket.user_name,
        created_at=ticket.created_at.isoformat() if isinstance(ticket.created_at, datetime) else str(ticket.created_at),
        updated_at=ticket.updated_at.isoformat() if isinstance(ticket.updated_at, datetime) else str(ticket.updated_at),
        reply_count=reply_count,
    )


# ── 路由处理器 ────────────────────────────────────────────────────────────────

@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED, summary="创建工单")
async def create_ticket(
    req: TicketCreateRequest,
    current_user: User = Depends(get_current_user),
) -> TicketOut:
    """
    用户提交客服工单。

    工单创建流程：
    1. 生成唯一工单编号（TK-YYYYMMDD-XXXXXXXX）
    2. 记录创建者信息
    3. 持久化到 MongoDB
    4. （生产环境）自动触发分类 Agent 并推送通知给处理团队
    """
    ticket = Ticket(
        ticket_id=_generate_ticket_id(),
        tenant_id=getattr(current_user, "tenant_id", "default"),
        user_id=str(getattr(current_user, "id", "anonymous")),
        user_name=getattr(current_user, "username", "匿名用户"),
        category=req.category,
        title=req.title,
        description=req.description,
        priority=req.priority,
        status=TicketStatus.OPEN,
        device_code=req.device_code,
        pet_id=req.pet_id,
        attachments=req.attachments,
    )
    await ticket.insert()
    logger.info("工单创建成功: %s (用户: %s)", ticket.ticket_id, ticket.user_name)
    return _ticket_to_out(ticket)


@router.get("", summary="查询工单列表")
async def list_tickets(
    status_filter: Optional[str] = Query(default=None, alias="status", description="工单状态过滤"),
    category: Optional[str] = Query(default=None, description="工单类别过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    查询工单列表，支持分页和状态/类别过滤。
    按更新时间倒序排列（最新的在前）。
    """
    tenant_id = getattr(current_user, "tenant_id", "default")

    # 构建查询条件
    query = Ticket.find(Ticket.tenant_id == tenant_id)
    if status_filter:
        query = query.find(Ticket.status == status_filter)
    if category:
        query = query.find(Ticket.category == category)

    total = await query.count()
    tickets = await query.sort("-updated_at").skip((page - 1) * page_size).limit(page_size).to_list()

    # 批量获取回复数
    ticket_ids = [t.ticket_id for t in tickets]
    reply_counts: dict[str, int] = {}
    if ticket_ids:
        pipeline = [
            {"$match": {"ticket_id": {"$in": ticket_ids}}},
            {"$group": {"_id": "$ticket_id", "count": {"$sum": 1}}},
        ]
        try:
            agg_result = await TicketReply.aggregate(pipeline).to_list()
            for item in agg_result:
                reply_counts[item["_id"]] = item["count"]
        except Exception:
            pass

    items = [_ticket_to_out(t, reply_counts.get(t.ticket_id, 0)) for t in tickets]
    return {
        "tickets": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{ticket_id}", summary="查询工单详情")
async def get_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    查询指定工单的完整信息，包括回复历史。
    回复按时间正序排列，内部备注仅客服可见。
    """
    ticket = await Ticket.find_one(Ticket.ticket_id == ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")

    # 查询回复
    replies = await TicketReply.find(
        TicketReply.ticket_id == ticket_id
    ).sort("+created_at").to_list()

    # 普通用户看不到内部备注
    user_role = getattr(current_user, "role", "member")
    if user_role not in ("admin", "super_admin", "operator"):
        replies = [r for r in replies if not r.is_internal]

    return {
        "ticket_id": ticket.ticket_id,
        "category": ticket.category.value if hasattr(ticket.category, 'value') else ticket.category,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
        "priority": ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
        "user_name": ticket.user_name,
        "assigned_to": ticket.assigned_to,
        "device_code": ticket.device_code,
        "pet_id": ticket.pet_id,
        "escalated_reason": ticket.escalated_reason,
        "internal_note": ticket.internal_note if user_role in ("admin", "super_admin", "operator") else None,
        "created_at": ticket.created_at.isoformat() if isinstance(ticket.created_at, datetime) else ticket.created_at,
        "updated_at": ticket.updated_at.isoformat() if isinstance(ticket.updated_at, datetime) else ticket.updated_at,
        "replies": [
            {
                "reply_id": str(r.id),
                "content": r.content,
                "is_internal": r.is_internal,
                "created_by_name": r.created_by_name,
                "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else r.created_at,
                "attachments": r.attachments,
            }
            for r in replies
        ],
    }


@router.patch("/{ticket_id}", summary="更新工单状态")
async def update_ticket(
    ticket_id: str,
    req: TicketUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    更新工单状态、优先级或指派客服。（客服/管理员操作）

    状态流转自动记录时间戳：
    - resolved → 记录 resolved_at
    - closed → 记录 closed_at
    """
    ticket = await Ticket.find_one(Ticket.ticket_id == ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")

    update_fields: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

    if req.status is not None:
        update_fields["status"] = req.status
        if req.status == TicketStatus.RESOLVED:
            update_fields["resolved_at"] = datetime.now(timezone.utc)
        elif req.status == TicketStatus.CLOSED:
            update_fields["closed_at"] = datetime.now(timezone.utc)

    if req.priority is not None:
        update_fields["priority"] = req.priority
    if req.assigned_to is not None:
        update_fields["assigned_to"] = req.assigned_to
    if req.internal_note is not None:
        update_fields["internal_note"] = req.internal_note

    await ticket.update(Set(update_fields))
    logger.info("工单 %s 已更新: %s", ticket_id, list(update_fields.keys()))

    return {
        "ticket_id": ticket_id,
        "message": "工单已更新",
        "updated_fields": [k for k in update_fields if k != "updated_at"],
    }


@router.post("/{ticket_id}/reply", status_code=status.HTTP_201_CREATED, summary="添加工单回复")
async def reply_ticket(
    ticket_id: str,
    req: TicketReplyRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    向工单添加回复（用户或客服均可操作）。

    - 用户回复后，工单状态自动从 pending_customer 切换为 processing
    - 客服内部备注（is_internal=True）对用户不可见
    """
    ticket = await Ticket.find_one(Ticket.ticket_id == ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")

    user_role = getattr(current_user, "role", "member")
    reply = TicketReply(
        ticket_id=ticket_id,
        content=req.content,
        is_internal=req.is_internal,
        created_by=str(getattr(current_user, "id", "anonymous")),
        created_by_name=getattr(current_user, "username", "匿名用户"),
        attachments=req.attachments,
    )
    await reply.insert()

    # 用户回复后自动切换状态
    if ticket.status == TicketStatus.PENDING_CUSTOMER and not req.is_internal:
        await ticket.update(Set({
            "status": TicketStatus.PROCESSING,
            "updated_at": datetime.now(timezone.utc),
        }))

    logger.info("工单 %s 新增回复: %s", ticket_id, reply.id)
    return {
        "ticket_id": ticket_id,
        "reply_id": str(reply.id),
        "message": "回复已添加",
    }


@router.post("/{ticket_id}/escalate", summary="工单升级")
async def escalate_ticket(
    ticket_id: str,
    req: TicketEscalateRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    将工单升级为紧急优先级，转交给指定处理团队。

    升级后：
    - 状态变为 escalated
    - 优先级变为 urgent
    - 记录升级原因和时间
    """
    ticket = await Ticket.find_one(Ticket.ticket_id == ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")

    await ticket.update(Set({
        "status": TicketStatus.ESCALATED,
        "priority": TicketPriority.URGENT,
        "escalated_reason": req.reason,
        "escalated_at": datetime.now(timezone.utc),
        "assigned_to": req.target_team or ticket.assigned_to,
        "updated_at": datetime.now(timezone.utc),
    }))

    logger.info("工单 %s 已升级: %s → %s", ticket_id, req.reason, req.target_team or "未指定团队")
    return {
        "ticket_id": ticket_id,
        "message": "工单已升级为紧急",
        "reason": req.reason,
        "target_team": req.target_team or ticket.assigned_to,
    }
