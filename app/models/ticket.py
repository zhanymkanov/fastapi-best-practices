"""
客服工单模型 — Beanie ODM Document

工单状态流转：
  open → processing → pending_customer → resolved → closed
           ↓ (紧急)
           escalated → resolved → closed
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document
from pydantic import Field


class TicketStatus(str, Enum):
    OPEN = "open"
    PROCESSING = "processing"
    PENDING_CUSTOMER = "pending_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, Enum):
    DEVICE_FAULT = "device_fault"
    HEALTH_CONSULT = "health_consult"
    ACCOUNT_ISSUE = "account_issue"
    PAYMENT = "payment"
    OTA_ISSUE = "ota_issue"
    OTHER = "other"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketReply(Document):
    """工单回复（内嵌文档）"""
    ticket_id: str
    content: str
    is_internal: bool = False          # 内部备注用户不可见
    created_by: str = "system"         # 回复人 ID
    created_by_name: str = "系统"       # 回复人名称
    attachments: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "ticket_replies"


class Ticket(Document):
    """客服工单"""
    ticket_id: str                                    # 业务编号 TK-YYYYMMDD-XXXXXXXX
    tenant_id: str = "default"
    user_id: str                                      # 创建者
    user_name: str = ""                               # 创建者名称

    category: TicketCategory = TicketCategory.OTHER
    title: str
    description: str
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM

    device_code: Optional[str] = None                 # 关联设备
    pet_id: Optional[str] = None                      # 关联宠物
    assigned_to: Optional[str] = None                 # 指派人
    internal_note: Optional[str] = None               # 内部备注

    escalated_reason: Optional[str] = None            # 升级原因
    escalated_at: Optional[datetime] = None           # 升级时间

    resolved_at: Optional[datetime] = None            # 解决时间
    closed_at: Optional[datetime] = None              # 关闭时间

    attachments: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "tickets"
        indexes = [
            "ticket_id",
            "tenant_id",
            "user_id",
            "status",
            "category",
            [("tenant_id", 1), ("status", 1)],
            [("tenant_id", 1), ("created_at", -1)],
        ]
