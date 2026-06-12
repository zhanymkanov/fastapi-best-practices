from datetime import datetime, timezone

from beanie import Document
from pydantic import EmailStr


class User(Document):
    tenant_id: str
    username: str
    email: EmailStr
    hashed_password: str
    role: str = "member"
    is_active: bool = True
    created_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "users"
