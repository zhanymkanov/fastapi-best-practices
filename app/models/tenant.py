from datetime import datetime, timezone

from beanie import Document


class Tenant(Document):
    name: str
    code: str
    is_active: bool = True
    created_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "tenants"
