"""
软删除清理任务 — 定期清理已标记删除的过期数据

处理逻辑：
1. 查询 is_deleted=True 且超过保留期的记录
2. 物理删除或归档到冷存储
3. 记录清理日志

默认保留期：30 天（可配置）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

logger = logging.getLogger(__name__)

# 软删除保留天数：超过此天数的已删除记录将被物理清除
RETENTION_DAYS = 30


@shared_task(
    name="app.tasks.deletion_cleanup.cleanup_soft_deleted",
    bind=True,
    max_retries=1,
)
def cleanup_soft_deleted(self) -> dict:
    """清理过期软删除数据"""
    import asyncio

    async def _cleanup():
        from app.core.database import get_database
        db = get_database()

        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        result = {"cleaned": {}, "errors": []}

        # 需要清理的集合列表
        collections = {
            "pets": "updated_at",          # 宠物档案
            "data_assets": "updated_at",   # 数据资产
        }

        for coll_name, time_field in collections.items():
            try:
                # 查询过期的软删除记录
                expired_query = {
                    "is_deleted": True,
                    time_field: {"$lt": cutoff},
                }
                count = await db[coll_name].count_documents(expired_query)

                if count > 0:
                    # 物理删除
                    delete_result = await db[coll_name].delete_many(expired_query)
                    logger.info(
                        "清理 %s: 过期 %d 条, 已删除 %d 条",
                        coll_name, count, delete_result.deleted_count,
                    )
                    result["cleaned"][coll_name] = delete_result.deleted_count
                else:
                    result["cleaned"][coll_name] = 0

            except Exception as exc:
                logger.exception("清理 %s 失败: %s", coll_name, exc)
                result["errors"].append({"collection": coll_name, "error": str(exc)})

        total_cleaned = sum(result["cleaned"].values())
        logger.info("软删除清理完成: 共清理 %d 条, 错误 %d 个",
                     total_cleaned, len(result["errors"]))

        return {"status": "ok", "cleaned": total_cleaned, "details": result}

    return asyncio.get_event_loop().run_until_complete(_cleanup())
