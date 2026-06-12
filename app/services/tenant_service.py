from __future__ import annotations

from app.models.tenant import Tenant


class TenantService:

    @classmethod
    async def list_tenants(cls) -> list[Tenant]:
        return await Tenant.find_all().to_list()

    @classmethod
    async def get_tenant(cls, tenant_id: str) -> Tenant | None:
        return await Tenant.get(tenant_id)

    @classmethod
    async def create_tenant(cls, data: dict) -> Tenant:
        tenant = Tenant(**data)
        return await tenant.insert()

    @classmethod
    async def update_tenant(cls, tenant_id: str, data: dict) -> Tenant | None:
        tenant = await Tenant.get(tenant_id)
        if not tenant:
            return None
        await tenant.set({k: v for k, v in data.items() if v is not None})
        return tenant

    @classmethod
    async def delete_tenant(cls, tenant_id: str) -> None:
        tenant = await Tenant.get(tenant_id)
        if tenant:
            await tenant.delete()
