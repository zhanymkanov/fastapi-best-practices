from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, TokenResponse
from app.schemas.user_schema import UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    user = await User.find_one({
        "$or": [
            {"username": data.username},
            {"email": data.username},
        ]
    })
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "tenant_id": user.tenant_id},
    )
    return {"access_token": access_token}


@router.get("/me", response_model=UserResponse)
async def get_auth_me(current_user: User = Depends(get_current_user)):
    return current_user
