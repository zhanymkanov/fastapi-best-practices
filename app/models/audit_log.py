from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from beanie import Document


class AuditLog(Document):
    tenant_id: Optional[str] = None
    actor_id: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    detail: dict[str, Any] = {}
    created_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "audit_logs"
        indexes = [
            "tenant_id",
            "actor_id",
            "action",
            [("resource_type", 1), ("resource_id", 1)],
            "created_at",
        ]
