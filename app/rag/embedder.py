"""
Embedder — 文本向量化模块

模型支持（优先级由高到低）：
  1. 本地 bge-m3 模型（sentence-transformers），离线运行，精度最高
  2. OpenAI 兼容 API（LLM_BASE_URL + LLM_API_KEY），无需本地 GPU
  3. Mock（维度 1024 的随机向量），用于单元测试/CI

bge-m3 说明：
  - 模型名：BAAI/bge-m3
  - 输出维度：1024
  - 支持中英文，适合宠物领域知识库
  - 下载：huggingface-cli download BAAI/bge-m3
"""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# 向量维度：bge-m3 固定输出 1024 维
EMBEDDING_DIM = 1024
EMBEDDING_MODEL = "BAAI/bge-m3"
_embedding_backend: Literal["local", "api", "mock"] = "mock"
_local_model = None


def _init_local_model():
    """懒加载 bge-m3 本地模型（只在第一次调用时初始化）"""
    global _local_model, _embedding_backend
    if _local_model is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(EMBEDDING_MODEL)
        _embedding_backend = "local"
        logger.info("已加载本地 embedding 模型: %s", EMBEDDING_MODEL)
        return True
    except ImportError:
        logger.warning("sentence-transformers 未安装，尝试 API 模式")
        return False
    except Exception as exc:
        logger.warning("本地模型加载失败（%s），降级为 API 模式", exc)
        return False


async def embed_texts(texts: list[str], backend: str = "auto") -> list[list[float]]:
    """
    批量文本向量化。

    Args:
        texts:   待向量化的文本列表
        backend: "auto"（优先本地）| "local" | "api" | "mock"

    Returns:
        向量列表，每个向量 1024 维
    """
    if not texts:
        return []

    effective_backend = backend
    if effective_backend == "auto":
        if _init_local_model():
            effective_backend = "local"
        else:
            effective_backend = "api"

    if effective_backend == "local" and _local_model is not None:
        import asyncio
        loop = asyncio.get_event_loop()
        vecs = await loop.run_in_executor(
            None,
            lambda: _local_model.encode(texts, normalize_embeddings=True).tolist()
        )
        return vecs

    if effective_backend == "api":
        try:
            from app.integrations.llm_client import get_llm
            llm = get_llm()
            return await llm.embed(texts, model="text-embedding-v3")
        except Exception as exc:
            logger.warning("API 向量化失败（%s），降级为 mock", exc)

    # mock 模式：返回随机向量（仅用于开发/测试）
    import random
    return [
        [random.uniform(-0.1, 0.1) for _ in range(EMBEDDING_DIM)]
        for _ in texts
    ]


async def embed_query(query: str) -> list[float]:
    """单条查询向量化（RAG 检索时使用）"""
    vecs = await embed_texts([query])
    return vecs[0]
