"""租户管理 API 测试"""

import pytest 
from httpx import AsyncClient 


@pytest.mark.asyncio 
async def test_create_tenant_admin_only( 
    async_client: AsyncClient, admin_headers: dict 
):
    """管理员创建租户 → 201"""
    payload = {"name": "测试租户", "code": "test-tenant", "is_active": True} 
    response = await async_client.post( 
        "/api/v1/tenants/", json=payload, headers=admin_headers
    )

    assert response.status_code == 201 
    data = response.json()
    assert data["name"] == "测试租户" 
    assert data["code"] == "test-tenant" 
    assert "_id" in data 


@pytest.mark.asyncio 
async def test_create_tenant_member_forbidden(
    async_client: AsyncClient, member_headers: dict
):
    """成员无权创建租户 → 403"""
    payload = {"name": "test", "code": "no-perm"}
    response = await async_client.post(
        "/api/v1/tenants/", json=payload, headers=member_headers
    )

    assert response.status_code == 403


@pytest.mark.asyncio  
async def test_list_tenants(
    async_client: AsyncClient, admin_headers: dict, clean_collections
):
    """管理员列出租户"""
    # 先创建
    payload = {"name": "列出租户测试", "code": "list-test"}
    create_resp = await async_client.post(
        "/api/v1/tenants/", json=payload, headers=admin_headers
    )
    assert create_resp.status_code == 201

    # 再列出
    response = await async_client.get("/api/v1/tenants/", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(t["code"] == "list-test" for t in data)


@pytest.mark.asyncio
async def test_delete_tenant(
    async_client: AsyncClient, admin_headers: dict, clean_collections
):
    """管理员删除租户 → 204"""
    payload = {"name": "待删除", "code": "to-delete"}
    create_resp = await async_client.post(
        "/api/v1/tenants/", json=payload, headers=admin_headers
    )
    tenant_id = create_resp.json()["_id"]

    response = await async_client.delete(
        f"/api/v1/tenants/{tenant_id}", headers=admin_headers
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_dashboard_stub(async_client: AsyncClient, member_headers: dict):
    """看板 overview 端点（任何认证用户可用）"""
    response = await async_client.get(
        "/api/v1/dashboard/overview", headers=member_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "total_tenants" in data
    assert "total_users" in data
