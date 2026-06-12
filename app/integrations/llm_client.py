"""
LLM 客户端 — OpenAI 兼容 API（httpx 异步）

参考 dialog（3）的 LLM 抽象层：
- 支持多模型切换（通过 TOML endpoint 配置）
- SSE 流式响应
- 统一错误处理
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

from app.core.ai_config import ai_config

logger = logging.getLogger(__name__)

class LLMClient:
    """OpenAI 兼容 API 客户端（延迟读取配置，确保 .env 变更后生效）"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ):
        # 延迟导入 settings，确保读到最新的 .env 配置
        from app.core.config import settings as _settings

        self.base_url = (base_url or _settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or _settings.LLM_API_KEY
        self.timeout = timeout or _settings.LLM_TIMEOUT
        key_preview = self.api_key[:10] + "..." if self.api_key and len(self.api_key) > 10 else "(未配置)"
        logger.info("LLM 客户端初始化: base_url=%s model=%s api_key=%s",
                     self.base_url or "(未配置)", _settings.LLM_MODEL, key_preview)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url if self.base_url else None,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """同步聊天补全"""
        client = await self._get_client()
        payload = {
            "model": model or ai_config.model_name,
            "messages": messages,
            "temperature": temperature or ai_config.temperature,
            "max_tokens": max_tokens or ai_config.max_tokens,
            "stream": stream,
        }
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """SSE 流式聊天补全（参考 dialog 的 OpenAI 路由实现）"""
        client = await self._get_client()
        payload = {
            "model": model or ai_config.model_name,
            "messages": messages,
            "temperature": temperature or ai_config.temperature,
            "max_tokens": max_tokens or ai_config.max_tokens,
            "stream": True,
        }
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """文本向量化（为 RAG 预留）"""
        client = await self._get_client()
        payload = {
            "model": model or ai_config.embedding_model,
            "input": texts,
        }
        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# 全局客户端实例（按需创建）
_global_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """获取全局 LLM 客户端（如果没有配置则返回 None）"""
    global _global_client
    if _global_client is None:
        _global_client = LLMClient()
    return _global_client
