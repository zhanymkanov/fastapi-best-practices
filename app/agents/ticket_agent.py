"""
TicketAgent — 客服工单 Agent

职责：
  - 处理用户工单相关请求（创建工单、查询进度、升级工单）
  - 自动识别紧急程度
  - 提供工单状态更新和预计处理时间
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
你是QMI平台的智能客服助手，负责帮助用户创建、查询和跟进服务工单。

职责：
1. 帮助用户快速创建工单，确认关键信息（问题类型、联系方式）
2. 查询工单状态时，给出清晰的进度说明和预计解决时间
3. 对于紧急问题（设备损坏、宠物急救），标记为高优先级并提醒用户
4. 保持礼貌和同理心，让用户感到被关注

回答风格：亲切、耐心、有服务意识。
"""


class TicketAgent(BaseAgent):
    """客服工单 Agent"""

    name = "ticket_agent"
    domain = "ticket"

    async def run(
        self,
        user_message: str,
        session_id: str,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        history: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        tool_calls = []

        # 意图细分：创建 vs 查询
        if any(kw in user_message for kw in ["创建工单", "提交工单", "报修", "反馈", "投诉", "我要"]):
            result = await self._call_tool("create_ticket", {
                "user_id": user_id,
                "title": user_message[:50],
                "content": user_message,
                "category": "general",
                "priority": "high" if any(kw in user_message for kw in ["紧急", "急", "立即", "马上"]) else "normal",
            })
            if not result.get("_mock"):
                tool_calls.append({"tool": "create_ticket", "params": {"title": user_message[:50]}, "result": result})
        else:
            ticket_id = kwargs.get("ticket_id") or kwargs.get("context", {}).get("ticket_id")
            if ticket_id:
                result = await self._call_tool("get_ticket_status", {"ticket_id": ticket_id})
                if not result.get("_mock"):
                    tool_calls.append({"tool": "get_ticket_status", "params": {"ticket_id": ticket_id}, "result": result})
            else:
                result = await self._call_tool("list_tickets", {"user_id": user_id, "page": 1, "page_size": 5})
                if not result.get("_mock"):
                    tool_calls.append({"tool": "list_tickets", "params": {"user_id": user_id}, "result": result})

        answer = await self._llm_with_tools(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_results=tool_calls,
            history=history,
        )
        return {
            "answer": answer,
            "tool_calls": tool_calls,
            "agent": self.name,
            "intent": "ticket",
        }
