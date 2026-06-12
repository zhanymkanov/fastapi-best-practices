"""
BaseAgent — 所有 Agent 的抽象基类

设计思路：
  每个 Agent 围绕一类业务场景（健康 / 设备 / 工单）。
  子 Agent 从 MCPRegistry 获取本域工具，调用工具后把结果
  传给 LLMClient，让 LLM 将工具结果转换为自然语言回答。

A2A（Agent-to-Agent）模式：
  OrchestratorAgent 负责意图识别，决定委托给哪个子 Agent。
  子 Agent 独立完成工具调用 + LLM 生成，结果回传给 Orchestrator。
  Orchestrator 汇总后返回最终回复给用户。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """所有 Agent 的基类"""

    name: str = "base"          # Agent 唯一标识
    domain: str = "general"     # 所属业务域，与 MCP 工具 category 对应

    def __init__(self) -> None:
        self._llm_client = None  # 懒加载

    def _get_llm(self):
        """懒加载 LLM 客户端"""
        if self._llm_client is None:
            from app.integrations.llm_client import get_llm
            self._llm_client = get_llm()
        return self._llm_client

    def _get_tools(self, category: str | None = None) -> list:
        """从注册中心获取本域工具"""
        from app.mcp.registry import mcp_registry
        tools = mcp_registry.list_tools()
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    @abstractmethod
    async def run(
        self,
        user_message: str,
        session_id: str,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        history: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        处理用户消息，返回包含 answer、tool_calls 等字段的字典。

        Args:
            user_message: 用户原始消息
            session_id: 会话 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            history: 历史消息列表 [{"role": "user/assistant", "content": "..."}]

        Returns:
            {
                "answer": "LLM 生成的自然语言回答",
                "tool_calls": [{"tool": "...", "params": {...}, "result": {...}}],
                "agent": "agent_name",
                "intent": "health/device/ticket/general",
            }
        """
        ...

    async def _call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """调用单个 MCP 工具"""
        from app.mcp.registry import mcp_registry
        tool = mcp_registry.get(tool_name)
        if tool is None:
            logger.warning("工具 %s 未注册", tool_name)
            return {"error": f"工具 {tool_name} 不存在"}
        result = await tool.safe_execute(params)
        return result

    async def _llm_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tool_results: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        工具增强生成（Tool-Augmented Generation）：
        把工具调用结果整合进 prompt，让 LLM 生成自然语言回答。
        """
        llm = self._get_llm()
        if llm is None or not llm.base_url:
            # LLM 未配置时返回 Demo 格式
            return self._format_demo_response(tool_results)

        # Step 1: 构建消息列表
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # Step 2: 加入最近的历史消息（最多 3 轮对话）
        if history:
            messages.extend(history[-6:])

        # Step 3: 把工具结果拼接成结构化文本
        tools_summary = ""
        for tr in tool_results:
            tool_name = tr.get("tool", "unknown")
            result_data = tr.get("result", {})
            tools_summary += f"\n【{tool_name} 查询结果】:\n{result_data}\n"

        # Step 4: 构建用户消息（工具结果 + 原始问题）
        enhanced_message = f"{user_message}\n\n{tools_summary}" if tools_summary else user_message
        messages.append({"role": "user", "content": enhanced_message})

        # Step 5: 调用 LLM 生成回答
        try:
            response = await llm.chat(messages=messages)  # 调用 LLM API
            return response["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.exception("LLM 调用失败: %s", exc)
            # LLM 失败时降级返回工具原始数据
            return f"（LLM 调用失败: {exc}）\n\n{self._format_demo_response(tool_results)}"

    @staticmethod
    def _format_demo_response(tool_results: list[dict[str, Any]]) -> str:
        """Demo 模式：把工具结果格式化为可读文本（LLM 未配置时的降级方案）"""
        if not tool_results:
            return "（Demo 模式）无工具调用结果。"
        lines = ["（Demo 模式 — 未配置 LLM，直接返回工具原始数据）\n"]
        for tr in tool_results:
            lines.append(f"工具: {tr.get('tool', '?')}  结果: {tr.get('result', {})}")
        return "\n".join(lines)
