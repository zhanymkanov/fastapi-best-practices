"""
OTA 升级工具 — MCP 工具封装

业务场景：
  - 查询设备可用 OTA 版本
  - 触发 OTA 升级任务
  - 查询 OTA 升级进度
"""
from __future__ import annotations

import logging
from typing import Any

from app.mcp.base import BaseMCPTool, MCPToolMeta

logger = logging.getLogger(__name__)


class CheckOTAVersionTool(BaseMCPTool):
    """查询设备可用的 OTA 固件版本"""

    meta = MCPToolMeta(
        name="check_ota_version",
        description="查询 IoT 设备当前固件版本，以及是否有可用的 OTA 升级版本。",
        parameters={
            "type": "object",
            "properties": {
                "device_code": {"type": "string", "description": "设备编码"},
            },
            "required": ["device_code"],
        },
        category="ota",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        device_code = params["device_code"]
        return {
            "success": True,
            "device_code": device_code,
            "current_version": "v2.3.1",
            "latest_version": "v2.5.0",
            "update_available": True,
            "release_notes": "修复心率传感器偶发断线问题；优化低功耗模式；新增步数统计功能。",
            "firmware_size_mb": 8.4,
            "_mock": True,
        }


class TriggerOTAUpgradeTool(BaseMCPTool):
    """触发设备 OTA 升级"""

    meta = MCPToolMeta(
        name="trigger_ota_upgrade",
        description="向指定 IoT 设备下发 OTA 升级指令，设备将在后台下载并安装新固件。",
        parameters={
            "type": "object",
            "properties": {
                "device_code": {"type": "string", "description": "设备编码"},
                "target_version": {
                    "type": "string",
                    "description": "目标固件版本号，不填则升级到最新版",
                    "default": "latest",
                },
                "schedule_time": {
                    "type": "string",
                    "description": "计划升级时间（ISO 8601），不填则立即升级",
                },
            },
            "required": ["device_code"],
        },
        category="ota",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        device_code = params["device_code"]
        target = params.get("target_version", "latest")
        schedule_time = params.get("schedule_time")
        return {
            "success": True,
            "device_code": device_code,
            "task_id": f"OTA-{device_code}-20260612",
            "target_version": "v2.5.0" if target == "latest" else target,
            "status": "queued",
            "message": "升级任务已创建，设备将在后台自动升级，预计耗时 5-10 分钟。",
            "schedule_time": schedule_time or "立即执行",
            "_mock": True,
        }


class GetOTAProgressTool(BaseMCPTool):
    """查询 OTA 升级进度"""

    meta = MCPToolMeta(
        name="get_ota_progress",
        description="查询 OTA 升级任务的当前进度和状态。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "OTA 任务 ID"},
                "device_code": {
                    "type": "string",
                    "description": "设备编码（task_id 和 device_code 二选一）",
                },
            },
        },
        category="ota",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("task_id", "OTA-MOCK-001")
        device_code = params.get("device_code", "UNKNOWN")
        return {
            "success": True,
            "task_id": task_id,
            "device_code": device_code,
            "status": "downloading",     # queued / downloading / installing / success / failed
            "progress_pct": 62,
            "current_version": "v2.3.1",
            "target_version": "v2.5.0",
            "started_at": "2026-06-12T10:00:00Z",
            "estimated_finish": "2026-06-12T10:08:00Z",
            "_mock": True,
        }
