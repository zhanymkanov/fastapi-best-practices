from datetime import datetime, timezone
from typing import Optional

from beanie import Document


class Device(Document):
    tenant_id: str
    pet_id: Optional[str] = None
    device_code: str
    device_type: str
    is_online: bool = False
    last_seen: Optional[datetime] = None
    created_at: datetime = datetime.now(timezone.utc)

    class Settings:
        name = "devices"
