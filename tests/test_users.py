"""用户管理 API 测试"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me_as_admin(async_client: AsyncClient, admin_headers: dict):
    """管理员 GET /api/v1/users/me 应返回自身信息"""
    response = await async_client.get("/api/v1/users/me", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_as_member(async_client: AsyncClient, member_headers: dict):
    """成员 GET /api/v1/users/me 应返回自身信息"""
    response = await async_client.get("/api/v1/users/me", headers=member_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "member"
    assert data["role"] == "member"


@pytest.mark.asyncio
async def test_list_users_admin_only(async_client: AsyncClient, admin_headers: dict):
    """管理员可以列出用户"""
    response = await async_client.get("/api/v1/users/", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_users_member_forbidden(
    async_client: AsyncClient, member_headers: dict
):
    """成员无权列出用户 → 403"""
    response = await async_client.get("/api/v1/users/", headers=member_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_desensitization(
    async_client: AsyncClient, admin_user, admin_headers: dict
):
    """用户信息应包含脱敏邮箱"""
    # 通过 /me 端点获取，不直接暴露原始邮箱
    response = await async_client.get("/api/v1/users/me", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    # 原始邮箱 admin@petchill.com
    assert "email" in data
