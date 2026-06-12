from __future__ import annotations

from app.core.security import hash_password, mask_sensitive
from app.models.user import User


class UserService:

    @classmethod
    async def list_users(cls) -> list[User]:
        return await User.find_all().to_list()

    @classmethod
    async def get_user(cls, user_id: str) -> User | None:
        return await User.get(user_id)

    @classmethod
    async def create_user(cls, data: dict) -> User:
        if "password" in data:
            data["hashed_password"] = hash_password(data.pop("password"))
        user = User(**data)
        return await user.insert()

    @classmethod
    async def update_user(cls, user_id: str, data: dict) -> User | None:
        user = await User.get(user_id)
        if not user:
            return None
        if "password" in data:
            data["hashed_password"] = hash_password(data.pop("password"))
        await user.set(data)
        return user

    @classmethod
    async def delete_user(cls, user_id: str) -> None:
        user = await User.get(user_id)
        if user:
            await user.delete()

    @classmethod
    async def get_safe_user(cls, user_id: str) -> dict | None:
        user = await User.get(user_id)
        if not user:
            return None
        data = user.model_dump()
        data["email"] = mask_sensitive(data["email"])
        return data
