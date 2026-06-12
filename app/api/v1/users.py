from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserResponse, UserUpdate
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(current_user: User = Depends(require_permission("user:read"))):
    return await UserService.list_users()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_permission("user:write")),
):
    user = await UserService.create_user(data.model_dump())
    await AuditService.log(
        actor=current_user,
        action="user.create",
        resource_type="user",
        resource_id=str(user.id),
        tenant_id=user.tenant_id,
        detail={"role": user.role},
    )
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_permission("user:read")),
):
    user = await UserService.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: User = Depends(require_permission("user:write")),
):
    user = await UserService.update_user(user_id, data.model_dump(exclude_none=True))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await AuditService.log(
        actor=current_user,
        action="user.update",
        resource_type="user",
        resource_id=user_id,
        tenant_id=user.tenant_id,
        detail={"fields": list(data.model_dump(exclude_none=True).keys())},
    )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_permission("user:write")),
):
    await UserService.delete_user(user_id)
    await AuditService.log(
        actor=current_user,
        action="user.delete",
        resource_type="user",
        resource_id=user_id,
    )
