"""
HealthAgent — 宠物健康分析 Agent

职责：
  - 接收健康相关问题（"我的狗狗最近咳嗽是怎么回事？"）
  - 调用 MCP 健康工具（get_pet_health_summary、analyze_pet_symptoms）
  - 结合 RAG 检索宠物知识库
  - 返回专业化的健康建议
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
你是QMI平台的宠物健康顾问，拥有丰富的兽医学和动物行为学知识。

职责：
1. 根据宠物健康数据和用户描述的症状，给出专业且易懂的健康建议
2. 如有严重症状（持续呕吐/腹泻超过24h、呼吸困难、神志不清等），必须建议立即就医
3. 建议要分点列出，清晰易懂，不使用过于专业的术语
4. 始终在回答末尾加注：本建议由 AI 生成，仅供参考，不能替代执业兽医诊断

回答风格：温和、专业、有责任心。
"""


class HealthAgent(BaseAgent):
    """宠物健康分析 Agent"""

    name = "health_agent"
    domain = "health"

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
        pet_id = kwargs.get("pet_id") or kwargs.get("context", {}).get("pet_id")

        # 1. 有 pet_id 时才调用工具（Demo 模式下跳过，避免 mock 数据干扰 LLM）
        if pet_id:
            result = await self._call_tool("get_pet_health_summary", {"pet_id": str(pet_id)})
            # 只有真实数据才传给 LLM
            if not result.get("_mock"):
                tool_calls.append({"tool": "get_pet_health_summary", "params": {"pet_id": pet_id}, "result": result})

            symptom_result = await self._call_tool(
                "analyze_pet_symptoms",
                {"symptoms": user_message, "pet_id": str(pet_id)},
            )
            if not symptom_result.get("_mock"):
                tool_calls.append({"tool": "analyze_pet_symptoms", "params": {"symptoms": user_message}, "result": symptom_result})

        # 2. 调用 LLM（有真实工具结果时整合，否则直接凭知识回答）
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
            "intent": "health",
        }
