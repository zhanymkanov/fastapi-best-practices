"""
IoT 平台客户端 — 对接自研 IoT 设备管理平台

提供设备状态查询、远程指令下发等能力。
当前为 Demo 模式（未配置 IoT 平台时返回模拟数据），
生产环境通过 settings.IOT_BASE_URL + IOT_API_KEY 接入真实 IoT 平台。
"""
from __future__ import annotations

import logging

from httpx import AsyncClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class IoTClient:
    """IoT 设备平台 HTTP 客户端"""

    def __init__(self) -> None:
        self.base_url: str = settings.IOT_BASE_URL
        self.api_key: str = settings.IOT_API_KEY
        self._client: AsyncClient | None = None

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = AsyncClient(
                base_url=self.base_url if self.base_url else None,
                headers=headers,
                timeout=30,
            )
        return self._client

    async def send_command(self, device_code: str, command: dict) -> dict:
        """向设备下发指令"""
        if not self.base_url:
            logger.debug("IoT 平台未配置，返回 Demo 数据")
            return {"status": "ok", "device_code": device_code, "_mock": True}
        client = await self._get_client()
        response = await client.post(
            f"/devices/{device_code}/command", json=command
        )
        response.raise_for_status()
        return response.json()

    async def get_device_status(self, device_code: str) -> dict:
        """查询设备实时状态"""
        if not self.base_url:
            logger.debug("IoT 平台未配置，返回 Demo 数据")
            return {"device_code": device_code, "is_online": True, "_mock": True}
        client = await self._get_client()
        response = await client.get(f"/devices/{device_code}/status")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
