"""健康检查端点测试"""

import pytest # 导入 pytest 模块
from httpx import AsyncClient # 导入 AsyncClient 模块


@pytest.mark.asyncio # 异步测试
async def test_health_check(async_client: AsyncClient): # 健康检查测试
    """GET /health 应返回 ok"""
    response = await async_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio # 异步测试
async def test_api_v1_requires_auth(async_client: AsyncClient): # 未认证应返回 401
    """/api/v1/* 未认证应返回 401"""
    response = await async_client.get("/api/v1/users/")

    assert response.status_code == 401  # Unauthorized (无 token)
