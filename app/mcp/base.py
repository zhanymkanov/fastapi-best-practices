"""
MCP 工具基础层 — Model Context Protocol 工具规范

核心类：
  MCPToolMeta  — 描述工具名称、功能说明和参数 Schema（给 LLM 看）
  BaseMCPTool  — 所有 MCP 工具的抽象基类，子类实现 execute() 即可

快速新增工具示例：
    class GetDeviceStatusTool(BaseMCPTool):
        meta = MCPToolMeta(
            name="get_device_status",
            description="查询 IoT 设备实时状态（在线/离线/温度/湿度）",
            parameters={
                "type": "object",
                "properties": {
                    "device_code": {"type": "string", "description": "设备编码"}
                },
                "required": ["device_code"],
            },
            category="device",
        )

        async def execute(self, params: dict) -> dict:
            code = params["device_code"]
            # 调用 IoT 客户端查询实时状态
            return {"device_code": code, "online": True, "temperature": 38.5}
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class MCPToolMeta:
    """工具元数据 — 用于 LLM function calling 的工具描述"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        category: str = "general",
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema 格式
        self.category = category

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 OpenAI function calling tools 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class BaseMCPTool(ABC):
    """
    MCP 工具抽象基类。

    子类必须：
      1. 定义类属性 meta: MCPToolMeta
      2. 实现异步方法 execute(params: dict) -> dict
    """

    meta: MCPToolMeta

    # ── 便捷属性（代理到 meta）────────────────────────────────────
    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def description(self) -> str:
        return self.meta.description

    @property
    def category(self) -> str:
        return self.meta.category

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        工具核心逻辑。

        Args:
            params: 调用参数，与 meta.parameters 定义一致

        Returns:
            执行结果字典。失败时应包含 {"error": "描述信息"} 字段。
        """
        ...

    async def safe_execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        带异常兜底的执行入口。

        Agent 层调用此方法而非直接调用 execute()，
        确保单个工具失败不会中断整个编排链路。
        """
        try:
            return await self.execute(params)
        except Exception as exc:
            logger.exception("MCP工具 [%s] 执行异常: %s", self.meta.name, exc)
            return {
                "success": False,
                "error": str(exc),
                "tool": self.meta.name,
            }

    def to_function_spec(self) -> dict[str, Any]:
        """返回 OpenAI function calling 格式（供 Registry 批量收集使用）"""
        return self.meta.to_openai_schema()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.meta.name} category={self.meta.category}>"
