"""
保险平台客户端 — 对接宠物保险理赔平台

提供保单查询、理赔提交等能力。
当前为 Demo 模式（未配置保险平台时返回模拟数据），
生产环境通过 settings.INSURANCE_BASE_URL + INSURANCE_API_KEY 接入真实保险平台。
"""
from __future__ import annotations

import logging

from httpx import AsyncClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class InsuranceClient:
    """宠物保险平台 HTTP 客户端"""

    def __init__(self) -> None:
        self.base_url: str = settings.INSURANCE_BASE_URL
        self.api_key: str = settings.INSURANCE_API_KEY
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

    async def submit_claim(self, pet_id: str, claim_data: dict) -> dict:
        """提交宠物保险理赔申请"""
        if not self.base_url:
            logger.debug("保险平台未配置，返回 Demo 数据")
            return {
                "claim_id": f"CLM-{pet_id}-001",
                "status": "pending",
                "message": "理赔申请已提交（Demo 模式）",
                "_mock": True,
            }
        client = await self._get_client()
        response = await client.post(
            f"/pets/{pet_id}/claims",
            json=claim_data,
        )
        response.raise_for_status()
        return response.json()

    async def get_policy(self, pet_id: str) -> dict:
        """查询宠物保单信息"""
        if not self.base_url:
            logger.debug("保险平台未配置，返回 Demo 数据")
            return {
                "pet_id": pet_id,
                "policy_id": f"POL-{pet_id}-001",
                "coverage": "基础医疗保障 + 意外险",
                "status": "active",
                "valid_until": "2026-12-31",
                "_mock": True,
            }
        client = await self._get_client()
        response = await client.get(f"/pets/{pet_id}/policy")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
