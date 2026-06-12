from __future__ import annotations

import logging
from typing import Any

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditService:
    @classmethod
    async def log(
        cls,
        *,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        tenant_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        try:
            log = AuditLog(
                tenant_id=tenant_id or actor.tenant_id,
                actor_id=str(actor.id),
                actor_role=actor.role,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail or {},
            )
            await log.insert()
        except Exception:
            logger.exception("写入审计日志失败: action=%s resource=%s", action, resource_type)
