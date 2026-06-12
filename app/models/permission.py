from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from beanie import Document


class RolePermission(Document):
    tenant_id: Optional[str] = None
    role: str
    permissions: list[str] = []
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "role_permissions"
        indexes = [
            "tenant_id",
            "role",
            [("tenant_id", 1), ("role", 1)],
        ]
