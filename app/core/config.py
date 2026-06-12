"""
全局配置 — 基于 pydantic-settings 的环境变量管理

所有配置项都可以通过环境变量或 .env 文件覆盖。
命名规则：大写下划线，如 MONGODB_URL、REDIS_URL。

使用方式：
    from app.core.config import settings
    print(settings.APP_NAME)

配置分组说明：
  - 基础：APP_NAME、APP_VERSION、DEPLOY_MODE、CORS_ORIGINS
  - 数据库：MONGODB_URL（Beanie/Motor）
  - Redis：REDIS_URL（Celery broker + result backend）
  - Milvus：MILVUS_HOST / PORT / COLLECTION（向量库，支持 RAG）
  - JWT：JWT_SECRET / ALGORITHM / EXPIRE_MINUTES
  - LLM：LLM_BASE_URL / API_KEY（OpenAI 兼容接口）
  - Embedding：EMBEDDING_BASE_URL / MODEL / DIMENSIONS（bge-m3）
  - IoT：IOT_BASE_URL / API_KEY（自研 IoT 平台地址）
  - 保险：INSURANCE_BASE_URL / API_KEY（宠物保险对接）
  - Sentry：SENTRY_DSN（可选，错误监控）
"""
from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 应用基础 ─────────────────────────────────────────────────
    APP_NAME: str = "QMI· 宠物生态智能管理平台"
    APP_VERSION: str = "1.0.0"
    DEPLOY_MODE: str = "dev"          # dev | staging | prod

    # ── CORS ─────────────────────────────────────────────────────
    # 支持逗号分隔字符串或 JSON 数组
    CORS_ORIGINS: list[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # ── MongoDB（Beanie ODM）──────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "cyberlife"

    # ── Redis（Celery + 缓存）────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Milvus 向量库（RAG 检索）─────────────────────────────────
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "pet_knowledge"          # 宠物健康知识库集合名
    MILVUS_COLLECTION_DEVICE_DOC: str = "device_manuals"    # 设备说明文档库
    MILVUS_COLLECTION_OP_RULES: str = "operation_rules"     # 运营规则库

    # ── JWT 认证 ─────────────────────────────────────────────────
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 默认 24 小时

    # ── LLM（OpenAI 兼容 API）────────────────────────────────────
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "qwen-turbo"
    LLM_TIMEOUT: float = 60.0

    # ── Embedding（bge-m3 等）────────────────────────────────────
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024

    # ── IoT 平台（自研 IoT API）──────────────────────────────────
    IOT_BASE_URL: str = "http://iot-platform:8888"
    IOT_API_KEY: str = ""

    # ── 宠物保险对接 ──────────────────────────────────────────────
    INSURANCE_BASE_URL: str = ""
    INSURANCE_API_KEY: str = ""

    # ── Sentry 监控 ──────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Celery ───────────────────────────────────────────────────
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celery broker 复用 Redis"""
        return self.REDIS_URL


# 全局单例
settings = Settings()
