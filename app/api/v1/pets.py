from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.pet_schema import PetCreate, PetUpdate, PetResponse, PetListResponse
from app.services.audit_service import AuditService
from app.services.pet_service import PetService

router = APIRouter()


@router.get("/", response_model=PetListResponse)
async def list_pets(
    owner_id: Optional[str] = Query(None),
    species: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """分页查询租户下宠物列表"""
    items, total = await PetService.find_all(
        tenant_id=current_user.tenant_id,
        owner_id=owner_id,                       # 从 JWT 里拿用户 ID
        species=species,
        page=page,
        page_size=page_size,
    )
    safe_items = [await PetService.get_safe_pet(p) for p in items]
    return {"items": safe_items, "total": total, "page": page, "page_size": page_size}


@router.post("/", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
async def create_pet(data: PetCreate, current_user: User = Depends(get_current_user)):
    """创建宠物档案"""
    pet = await PetService.insert(
        tenant_id=current_user.tenant_id,
        owner_id=str(current_user.id),
        data=data.model_dump(),
    )
    await AuditService.log(
        actor=current_user,
        action="pet.create",
        resource_type="pet",
        resource_id=str(pet.id),
        detail={"name": pet.name},
    )
    return await PetService.get_safe_pet(pet)


@router.get("/{pet_id}", response_model=PetResponse)
async def get_pet(pet_id: str, current_user: User = Depends(get_current_user)):
    """获取宠物详情"""
    pet = await PetService.get(pet_id, current_user.tenant_id)
    if not pet:
        raise HTTPException(status_code=404, detail="宠物档案不存在")
    return await PetService.get_safe_pet(pet)


@router.put("/{pet_id}", response_model=PetResponse)
async def update_pet(
    pet_id: str,
    data: PetUpdate,
    current_user: User = Depends(get_current_user),
):
    """更新宠物档案"""
    pet = await PetService.update(
        pet_id, current_user.tenant_id, data.model_dump(exclude_none=True)
    )
    if not pet:
        raise HTTPException(status_code=404, detail="宠物档案不存在")
    await AuditService.log(
        actor=current_user,
        action="pet.update",
        resource_type="pet",
        resource_id=pet_id,
        detail={"fields": list(data.model_dump(exclude_none=True).keys())},
    )
    return await PetService.get_safe_pet(pet)


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(pet_id: str, current_user: User = Depends(get_current_user)):
    """软删除宠物档案"""
    ok = await PetService.soft_delete(pet_id, current_user.tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="宠物档案不存在")
    await AuditService.log(
        actor=current_user,
        action="pet.delete",
        resource_type="pet",
        resource_id=pet_id,
    )
