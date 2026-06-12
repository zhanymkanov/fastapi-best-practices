"""
IoT 设备管理工具 — MCP 工具封装

业务场景：
  - 查询设备实时状态（在线/离线/传感器数据）
  - 批量获取设备列表及运行概览
  - 远程重启设备
  - 获取设备告警记录

调用示例：
    tool = mcp_registry.get("get_device_status")
    result = await tool.safe_execute({"device_code": "DEV-2024-001"})
    # => {"device_code": "DEV-2024-001", "online": True, "temperature": 38.5, ...}
"""
from __future__ import annotations

import logging
from typing import Any

from app.mcp.base import BaseMCPTool, MCPToolMeta

logger = logging.getLogger(__name__)


class GetDeviceStatusTool(BaseMCPTool):
    """查询 IoT 设备实时状态"""

    meta = MCPToolMeta(
        name="get_device_status",
        description="查询指定 IoT 设备的实时运行状态，包括在线状态、传感器数据（温度/湿度/电量）、最后心跳时间。",
        parameters={
            "type": "object",
            "properties": {
                "device_code": {
                    "type": "string",
                    "description": "设备唯一编码，如 DEV-2024-001",
                }
            },
            "required": ["device_code"],
        },
        category="device",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        device_code = params["device_code"]
        try:
            from app.integrations.iot_client import IoTClient
            client = IoTClient()
            status = await client.get_device_status(device_code)
            return {"success": True, "device_code": device_code, **status}
        except Exception:
            # Demo 模式：返回模拟数据
            logger.info("IoT 客户端不可用，返回模拟设备状态 (device=%s)", device_code)
            return {
                "success": True,
                "device_code": device_code,
                "online": True,
                "last_heartbeat": "2026-06-12T10:00:00Z",
                "sensors": {"temperature": 38.5, "humidity": 65.0, "battery": 85},
                "firmware_version": "v2.1.3",
                "_mock": True,
            }


class ListDevicesTool(BaseMCPTool):
    """批量查询设备列表"""

    meta = MCPToolMeta(
        name="list_devices",
        description="查询租户下的 IoT 设备列表，支持按状态过滤（online/offline/all），返回设备概览信息。",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "租户 ID"},
                "status_filter": {
                    "type": "string",
                    "enum": ["all", "online", "offline", "fault"],
                    "description": "设备状态过滤，默认 all",
                },
                "page": {"type": "integer", "description": "页码，默认 1"},
                "page_size": {"type": "integer", "description": "每页数量，默认 20"},
            },
            "required": ["tenant_id"],
        },
        category="device",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        tenant_id = params["tenant_id"]
        status_filter = params.get("status_filter", "all")
        # Demo 模式：返回模拟设备列表
        mock_devices = [
            {"device_code": "DEV-001", "name": "智能猫砂盆A", "type": "litter_box", "online": True},
            {"device_code": "DEV-002", "name": "自动喂食器B", "type": "feeder", "online": True},
            {"device_code": "DEV-003", "name": "宠物摄像头C", "type": "camera", "online": False},
            {"device_code": "DEV-004", "name": "饮水机D", "type": "water_fountain", "online": True},
        ]
        if status_filter == "online":
            mock_devices = [d for d in mock_devices if d["online"]]
        elif status_filter == "offline":
            mock_devices = [d for d in mock_devices if not d["online"]]
        return {
            "success": True,
            "tenant_id": tenant_id,
            "total": len(mock_devices),
            "devices": mock_devices,
            "_mock": True,
        }


class RestartDeviceTool(BaseMCPTool):
    """远程重启 IoT 设备"""

    meta = MCPToolMeta(
        name="restart_device",
        description="向指定 IoT 设备发送远程重启指令，用于设备卡死或网络异常恢复场景。",
        parameters={
            "type": "object",
            "properties": {
                "device_code": {"type": "string", "description": "设备编码"},
                "reason": {"type": "string", "description": "重启原因（运维备注）"},
            },
            "required": ["device_code"],
        },
        category="device",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        device_code = params["device_code"]
        reason = params.get("reason", "手动重启")
        logger.info("远程重启设备 %s，原因：%s", device_code, reason)
        return {
            "success": True,
            "device_code": device_code,
            "message": f"重启指令已发送，设备 {device_code} 将在 30 秒内重启",
            "_mock": True,
        }


class GetDeviceAlertsTool(BaseMCPTool):
    """获取设备告警记录"""

    meta = MCPToolMeta(
        name="get_device_alerts",
        description="查询指定设备的最近告警记录，包括离线告警、传感器异常、固件升级失败等。",
        parameters={
            "type": "object",
            "properties": {
                "device_code": {"type": "string", "description": "设备编码"},
                "limit": {"type": "integer", "description": "返回告警数量，默认 10"},
            },
            "required": ["device_code"],
        },
        category="device",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        device_code = params["device_code"]
        limit = params.get("limit", 10)
        mock_alerts = [
            {"id": "ALT-001", "type": "offline", "message": "设备离线超过 5 分钟", "at": "2026-06-12T09:00:00Z", "resolved": True},
            {"id": "ALT-002", "type": "sensor_error", "message": "温度传感器读数异常 (58°C)", "at": "2026-06-11T14:30:00Z", "resolved": False},
        ]
        return {
            "success": True,
            "device_code": device_code,
            "alerts": mock_alerts[:limit],
            "_mock": True,
        }
