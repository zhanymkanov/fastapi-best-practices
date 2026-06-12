"""
Celery 插件 — 异步任务调度集成
"""
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def register_plugin(app: FastAPI) -> None:
    """注册 Celery 健康检查端点"""
    from app.tasks.celery_app import celery_app

    @app.get("/health/celery")
    async def celery_health_check():
        try:
            result = celery_app.control.ping(timeout=2)
            workers = [r for r in result if r.get("ok") == "pong"]
            return {
                "status": "ok" if workers else "no_workers",
                "workers": len(workers),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    logger.info("Celery 健康检查端点已注册")
