from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_permission
from app.models.user import User
from app.schemas.tenant_schema import TenantCreate, TenantResponse, TenantUpdate
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantService

router = APIRouter()


@router.get("/", response_model=list[TenantResponse])
async def list_tenants(current_user: User = Depends(require_permission("tenant:read"))):
    return await TenantService.list_tenants()


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    current_user: User = Depends(require_permission("tenant:write")),
):
    tenant = await TenantService.create_tenant(data.model_dump())
    await AuditService.log(
        actor=current_user,
        action="tenant.create",
        resource_type="tenant",
        resource_id=str(tenant.id),
        tenant_id=str(tenant.id),
        detail={"code": tenant.code},
    )
    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(require_permission("tenant:read")),
):
    tenant = await TenantService.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    current_user: User = Depends(require_permission("tenant:write")),
):
    tenant = await TenantService.update_tenant(tenant_id, data.model_dump(exclude_none=True))
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    await AuditService.log(
        actor=current_user,
        action="tenant.update",
        resource_type="tenant",
        resource_id=tenant_id,
        tenant_id=tenant_id,
        detail={"fields": list(data.model_dump(exclude_none=True).keys())},
    )
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    current_user: User = Depends(require_permission("tenant:write")),
):
    await TenantService.delete_tenant(tenant_id)
    await AuditService.log(
        actor=current_user,
        action="tenant.delete",
        resource_type="tenant",
        resource_id=tenant_id,
        tenant_id=tenant_id,
    )
