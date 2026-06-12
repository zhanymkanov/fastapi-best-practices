from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# 密码哈希上下文（使用 bcrypt 算法）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: str, extra_claims: dict[str, Any] | None = None
) -> str:
    """生成 JWT Token"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,  # 过期时间
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:  # 合并自定义声明
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    """验证和解码 JWT Token"""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def hash_password(password: str) -> str:
    """对密码进行 Bcrypt 哈希处理"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配哈希值"""
    return pwd_context.verify(plain_password, hashed_password)


def mask_sensitive(data: str, keep_start: int = 3, keep_end: int = 4) -> str:
    """脱敏敏感数据（如芯片 ID），仅显示首尾，中间用 *** 替换"""
    if len(data) <= keep_start + keep_end:  # 数据过短则全部脱敏
        return "*" * len(data)
    return data[:keep_start] + "***" + data[-keep_end:]  # 保留首尾，中间隐藏
