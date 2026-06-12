from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_permission
from app.models.user import User
from app.schemas.device_schema import DeviceCreate, DeviceResponse, DeviceUpdate
from app.services.audit_service import AuditService
from app.services.device_service import DeviceService

router = APIRouter()


@router.get("/", response_model=list[DeviceResponse])
async def list_devices(current_user: User = Depends(require_permission("device:read"))):
    return await DeviceService.list_devices(tenant_id=current_user.tenant_id)


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    data: DeviceCreate,
    current_user: User = Depends(require_permission("device:write")),
):
    device = await DeviceService.create_device(data.model_dump())
    await AuditService.log(
        actor=current_user,
        action="device.create",
        resource_type="device",
        resource_id=str(device.id),
        tenant_id=device.tenant_id,
        detail={"device_code": device.device_code},
    )
    return device


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    current_user: User = Depends(require_permission("device:read")),
):
    device = await DeviceService.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    data: DeviceUpdate,
    current_user: User = Depends(require_permission("device:write")),
):
    existing = await DeviceService.get_device(device_id)
    if not existing or existing.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="设备不存在")
    device = await DeviceService.update_device(device_id, data.model_dump(exclude_none=True))
    await AuditService.log(
        actor=current_user,
        action="device.update",
        resource_type="device",
        resource_id=device_id,
        tenant_id=device.tenant_id,
        detail={"fields": list(data.model_dump(exclude_none=True).keys())},
    )
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: User = Depends(require_permission("device:write")),
):
    device = await DeviceService.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="设备不存在")
    await DeviceService.delete_device(device_id)
    await AuditService.log(
        actor=current_user,
        action="device.delete",
        resource_type="device",
        resource_id=device_id,
        tenant_id=device.tenant_id,
    )
