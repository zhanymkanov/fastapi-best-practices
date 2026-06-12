"""
DeviceAgent — IoT 设备运维 Agent

职责：
  - 查询设备状态、传感器数据
  - 诊断设备故障
  - 触发 OTA 升级
  - 返回设备运维报告
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
你是QMI平台的 IoT 设备运维专家，负责帮助用户了解设备状态、排查故障和执行升级。

职责：
1. 结合设备状态数据，给出清晰的设备运行状况报告
2. 如果设备离线或存在故障，提供排查步骤（检查网络、重启设备、联系售后等）
3. 在推荐 OTA 升级时，说明新版本的主要改动和升级预计耗时
4. 回答要简洁，技术细节用通俗语言解释

回答风格：专业、准确、有操作指导性。
"""


class DeviceAgent(BaseAgent):
    """IoT 设备运维 Agent"""

    name = "device_agent"
    domain = "device"

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
        device_code = kwargs.get("device_code") or kwargs.get("context", {}).get("device_code")

        # 1. 设备状态查询（仅在有 device_code 且返回真实数据时使用）
        if device_code:
            status_result = await self._call_tool("get_device_status", {"device_code": device_code})
            if not status_result.get("_mock"):
                tool_calls.append({"tool": "get_device_status", "params": {"device_code": device_code}, "result": status_result})

            ota_result = await self._call_tool("check_ota_version", {"device_code": device_code})
            if not ota_result.get("_mock"):
                tool_calls.append({"tool": "check_ota_version", "params": {"device_code": device_code}, "result": ota_result})

        # 2. 如果消息包含设备列表关键词，查询设备列表
        keywords_list = ["设备列表", "所有设备", "我的设备", "管理设备"]
        if any(kw in user_message for kw in keywords_list):
            list_result = await self._call_tool("list_devices", {"tenant_id": tenant_id, "page": 1, "page_size": 10})
            if not list_result.get("_mock"):
                tool_calls.append({"tool": "list_devices", "params": {}, "result": list_result})

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
            "intent": "device",
        }
