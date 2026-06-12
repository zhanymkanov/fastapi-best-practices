"""
每日运营报告任务 — 定时汇总平台运营数据

典型用途：
- 每日凌晨自动生成平台运营日报
- 统计新增用户/宠物/设备/工单
- 发送报告到指定通知渠道

调度方式（通过 Celery Beat）：
    CELERY_BEAT_SCHEDULE = {
        "daily-report": {
            "task": "app.tasks.daily_report.generate_daily_report",
            "schedule": crontab(hour=2, minute=0),  # 每天凌晨 2 点
        },
    }
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.daily_report.generate_daily_report",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def generate_daily_report(self, tenant_id: str | None = None) -> dict:
    """生成每日运营报告"""
    import asyncio

    async def _generate():
        from app.core.database import get_database
        db = get_database()

        # 统计范围：过去 24 小时
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        tenant_filter = {"tenant_id": tenant_id} if tenant_id else {}

        # 各项指标计数
        new_users = await db["users"].count_documents({
            **tenant_filter,
            "created_at": {"$gte": yesterday},
        })
        new_pets = await db["pets"].count_documents({
            **tenant_filter,
            "created_at": {"$gte": yesterday},
        })
        new_devices = await db["devices"].count_documents({
            **tenant_filter,
            "created_at": {"$gte": yesterday},
        })
        new_tickets = await db["tickets"].count_documents({
            **tenant_filter,
            "created_at": {"$gte": yesterday},
        })
        resolved_tickets = await db["tickets"].count_documents({
            **tenant_filter,
            "status": "resolved",
            "updated_at": {"$gte": yesterday},
        })

        report = {
            "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "tenant_id": tenant_id or "all",
            "metrics": {
                "new_users": new_users,
                "new_pets": new_pets,
                "new_devices": new_devices,
                "new_tickets": new_tickets,
                "resolved_tickets": resolved_tickets,
                "ticket_resolution_rate": f"{(resolved_tickets / new_tickets * 100):.1f}%"
                if new_tickets > 0 else "N/A",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("每日报告生成完成: tenant=%s, 新增用户=%d, 新增工单=%d",
                     tenant_id or "all", new_users, new_tickets)

        # 生产环境：发送到通知渠道（邮件/企业微信/钉钉）
        # await _send_report_notification(report)

        return {"status": "ok", "report": report}

    return asyncio.get_event_loop().run_until_complete(_generate())
