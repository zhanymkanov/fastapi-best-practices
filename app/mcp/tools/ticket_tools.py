"""
客服工单工具 — MCP 工具封装

业务场景：
  - 创建工单（用户提交问题）
  - 查询工单状态
  - 工单列表查询
  - 工单关闭/升级
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.mcp.base import BaseMCPTool, MCPToolMeta

logger = logging.getLogger(__name__)


class CreateTicketTool(BaseMCPTool):
    """创建客服工单"""

    meta = MCPToolMeta(
        name="create_ticket",
        description="用户提交客服工单，描述问题并选择问题类型（设备故障/健康咨询/账单/其他）。",
        parameters={
            "type": "object",
            "properties": {
                "user_id":     {"type": "string", "description": "用户 ID"},
                "title":       {"type": "string", "description": "工单标题"},
                "description": {"type": "string", "description": "问题详细描述"},
                "category":    {
                    "type": "string",
                    "description": "工单类型",
                    "enum": ["device_fault", "health_consult", "billing", "ota_issue", "other"],
                },
                "priority":    {
                    "type": "string",
                    "description": "优先级",
                    "enum": ["low", "normal", "high", "urgent"],
                    "default": "normal",
                },
            },
            "required": ["user_id", "title", "description"],
        },
        category="ticket",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        ticket_id = f"TK-{str(uuid.uuid4())[:8].upper()}"
        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expected_response_hours": 4,
            "message": f"工单 {ticket_id} 已创建，我们将在 4 小时内响应。",
            "_mock": True,
        }


class GetTicketStatusTool(BaseMCPTool):
    """查询工单状态"""

    meta = MCPToolMeta(
        name="get_ticket_status",
        description="根据工单 ID 查询当前工单状态和处理进展。",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单 ID，如 TK-XXXXXXXX"},
            },
            "required": ["ticket_id"],
        },
        category="ticket",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        ticket_id = params["ticket_id"]
        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": "processing",
            "assignee": "客服小王",
            "last_reply": "已收到您的问题，正在排查设备状态，预计 2 小时内回复。",
            "last_updated": "2026-06-12T10:30:00Z",
            "_mock": True,
        }


class ListTicketsTool(BaseMCPTool):
    """列出用户的工单列表"""

    meta = MCPToolMeta(
        name="list_tickets",
        description="获取指定用户的工单列表，支持按状态过滤。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "用户 ID"},
                "status":  {
                    "type": "string",
                    "description": "工单状态过滤",
                    "enum": ["open", "processing", "resolved", "closed", "all"],
                    "default": "all",
                },
                "limit": {"type": "integer", "description": "最多返回数量，默认 5"},
            },
            "required": ["user_id"],
        },
        category="ticket",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        user_id = params["user_id"]
        limit = params.get("limit", 5)
        mock_tickets = [
            {"ticket_id": "TK-A1B2C3D4", "title": "设备无法连接 App", "status": "processing"},
            {"ticket_id": "TK-E5F6G7H8", "title": "宠物疫苗记录查询", "status": "resolved"},
        ]
        return {
            "success": True,
            "user_id": user_id,
            "tickets": mock_tickets[:limit],
            "total": len(mock_tickets),
            "_mock": True,
        }


class CloseTicketTool(BaseMCPTool):
    """关闭工单"""

    meta = MCPToolMeta(
        name="close_ticket",
        description="关闭指定工单（用户确认问题已解决）。",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单 ID"},
                "feedback": {"type": "string", "description": "用户反馈/评价（可选）"},
                "rating": {"type": "integer", "description": "满意度评分 1-5（可选）"},
            },
            "required": ["ticket_id"],
        },
        category="ticket",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "ticket_id": params["ticket_id"],
            "status": "closed",
            "message": "工单已关闭，感谢您的反馈！",
            "_mock": True,
        }


class EscalateTicketTool(BaseMCPTool):
    """工单升级（标记紧急/需要人工处理）"""

    meta = MCPToolMeta(
        name="escalate_ticket",
        description="将工单升级为紧急处理，通知高级客服介入，适用于复杂问题或用户投诉。",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单 ID"},
                "reason": {"type": "string", "description": "升级原因"},
            },
            "required": ["ticket_id", "reason"],
        },
        category="ticket",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "ticket_id": params["ticket_id"],
            "status": "escalated",
            "message": "工单已升级，高级客服将在 1 小时内与您联系。",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
            "_mock": True,
        }
