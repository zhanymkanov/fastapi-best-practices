"""
MCP 工具注册中心 — 统一管理所有 MCP 工具

用法：
    from app.mcp.registry import mcp_registry

    # 注册单个工具
    mcp_registry.register(GetDeviceStatusTool())

    # 自动发现 app/mcp/tools/ 下所有工具
    mcp_registry.auto_discover()

    # Agent 调用工具
    tool = mcp_registry.get("get_device_status")
    result = await tool.safe_execute({"device_code": "DEV001"})

    # 获取所有工具的 OpenAI function calling schema
    schemas = mcp_registry.all_specs()
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

from app.mcp.base import BaseMCPTool

logger = logging.getLogger(__name__)


class MCPRegistry:
    """MCP 工具注册中心（全局单例）"""

    def __init__(self) -> None:
        # key: tool name  value: BaseMCPTool 实例
        self._tools: dict[str, BaseMCPTool] = {}

    # ── 注册 ────────────────────────────────────────────────────────
    def register(self, tool: BaseMCPTool) -> None:
        """注册一个 MCP 工具实例"""
        if tool.name in self._tools:
            logger.debug("工具 %s 已注册，跳过重复注册", tool.name)
            return
        self._tools[tool.name] = tool
        logger.info("MCP 工具注册成功: [%s] (%s)", tool.name, tool.category)

    def register_many(self, tools: list[BaseMCPTool]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register(tool)

    # ── 查询 ────────────────────────────────────────────────────────
    def get(self, name: str) -> BaseMCPTool | None:
        """按名称获取工具实例，不存在返回 None"""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[BaseMCPTool]:
        """列出所有工具（可按分类过滤）"""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def tool_names(self, category: str | None = None) -> list[str]:
        """返回工具名称列表"""
        return [t.name for t in self.list_tools(category)]

    def all_specs(self, category: str | None = None) -> list[dict[str, Any]]:
        """
        返回所有工具的 OpenAI function calling schema。
        传给 LLM 的 tools 参数时使用。
        """
        return [t.to_function_spec() for t in self.list_tools(category)]

    def categories(self) -> list[str]:
        """返回所有工具分类（去重）"""
        return list({t.category for t in self._tools.values()})

    def summary(self) -> dict[str, Any]:
        """返回注册概要，便于健康检查"""
        result: dict[str, list[str]] = {}
        for t in self._tools.values():
            result.setdefault(t.category, []).append(t.name)
        return result

    # ── 自动发现 ─────────────────────────────────────────────────────
    def auto_discover(self, package_name: str = "app.mcp.tools") -> None:
        """
        自动扫描指定包下的所有模块，找到 BaseMCPTool 子类并实例化注册。
        只要在 app/mcp/tools/ 下新建工具模块，即可被自动发现，无需手动 import。
        """
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError:
            logger.warning("工具包 %s 不存在，跳过自动发现", package_name)
            return

        package_path = getattr(package, "__path__", [])
        for _, module_name, _ in pkgutil.iter_modules(package_path):
            full_name = f"{package_name}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except Exception:
                logger.exception("导入工具模块 %s 失败", full_name)
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseMCPTool)
                    and attr is not BaseMCPTool
                    and not getattr(attr, "__abstract__", False)
                ):
                    try:
                        self.register(attr())
                    except Exception:
                        logger.exception("实例化工具 %s 失败", attr_name)

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"<MCPRegistry tools={len(self._tools)} categories={self.categories()}>"


# 全局单例
mcp_registry = MCPRegistry()
