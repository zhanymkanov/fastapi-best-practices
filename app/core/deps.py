from fastapi import Depends, HTTPException, status # 导入 Depends, HTTPException, status 模块
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer # 导入 HTTPAuthorizationCredentials, HTTPBearer 模块

from app.core.security import verify_access_token # 导入 verify_access_token 模块
from app.models.permission import RolePermission
from app.models.user import User # 导入 User 模型

security_scheme = HTTPBearer() # 创建 HTTPBearer 安全方案

DEFAULT_ROLE_PERMISSIONS = {
    "admin": {"*"},
    "super_admin": {"*"},
    "operator": {
        "tenant:read",
        "user:read",
        "pet:read",
        "pet:write",
        "device:read",
        "asset:read",
        "asset:write",
    },
    "member": {
        "user:read:self",
        "pet:read",
        "pet:write",
        "device:read",
        "asset:read",
        "asset:write",
    },
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> User:
    token = credentials.credentials # 获取 token
    try:
        payload = verify_access_token(token) # 验证 token
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌"
        )

    user = await User.get(payload["sub"]) # 获取用户
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用"
        )
    return user # 返回用户


class RBACChecker: # 角色访问控制检查器
    def __init__(self, required_roles: list[str]): # 初始化角色访问控制检查器
        self.required_roles = required_roles

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User: # 调用角色访问控制检查器
        if current_user.role not in self.required_roles: # 如果用户角色不在需要的角色列表中
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="权限不足"
            )
        return current_user


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if await has_permission(current_user, self.required_permission):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足",
        )


async def has_permission(user: User, permission: str) -> bool:
    default_permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, set())
    if "*" in default_permissions or permission in default_permissions:
        return True

    role_permission = await RolePermission.find_one({
        "tenant_id": user.tenant_id,
        "role": user.role,
    })
    if not role_permission:
        role_permission = await RolePermission.find_one({
            "tenant_id": None,
            "role": user.role,
        })
    if not role_permission:
        return False

    permissions = set(role_permission.permissions)
    return "*" in permissions or permission in permissions


def require_permission(permission: str) -> PermissionChecker:
    return PermissionChecker(permission)
