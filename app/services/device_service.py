from __future__ import annotations

from app.models.device import Device


class DeviceService:

    @classmethod
    async def list_devices(cls, tenant_id: str | None = None) -> list[Device]:
        if tenant_id:
            return await Device.find({"tenant_id": tenant_id}).to_list()
        return await Device.find_all().to_list()

    @classmethod
    async def get_device(cls, device_id: str) -> Device | None:
        return await Device.get(device_id)

    @classmethod
    async def create_device(cls, data: dict) -> Device:
        device = Device(**data)
        return await device.insert()

    @classmethod
    async def update_device(cls, device_id: str, data: dict) -> Device | None:
        device = await Device.get(device_id)
        if not device:
            return None
        await device.set({k: v for k, v in data.items() if v is not None})
        return device

    @classmethod
    async def delete_device(cls, device_id: str) -> None:
        device = await Device.get(device_id)
        if device:
            await device.delete()
