"""
Sentry 插件 — 生产环境错误追踪
"""
import logging

from fastapi import FastAPI

from app.core.config import settings

logger = logging.getLogger(__name__)


def register_plugin(app: FastAPI) -> None:
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN 未配置，跳过 Sentry 初始化")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.DEPLOY_MODE.value,
            release=settings.APP_VERSION,
            integrations=[FastApiIntegration()],
            traces_sample_rate=0.1,
        )
        logger.info("Sentry 已初始化 (env=%s)", settings.DEPLOY_MODE.value)
    except ImportError:
        logger.warning("sentry-sdk 未安装，无法启用 Sentry")
    except Exception:
        logger.exception("Sentry 初始化失败")
