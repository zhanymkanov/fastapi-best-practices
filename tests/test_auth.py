"""登录鉴权 API 测试"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, admin_user):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, admin_user):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
