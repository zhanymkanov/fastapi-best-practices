"""
Reranker — 重排序模块

RAG 检索两步法：
  1. Retrieval（粗召回）：Milvus 向量检索，top_k = 20-50
  2. Reranking（精排）  ：Cross-Encoder 重排序，取 top_n = 5

Cross-Encoder 对比 Bi-Encoder：
  - Bi-Encoder（bge-m3）：独立编码 query 和 doc，速度快，适合粗召回
  - Cross-Encoder（bge-reranker）：query+doc 拼接输入，精度更高，适合精排

使用的模型：BAAI/bge-reranker-v2-m3
如果模型未安装，自动降级为基于关键词的简单重排序。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
_reranker = None


def _init_reranker():
    """懒加载 bge-reranker Cross-Encoder 模型"""
    global _reranker
    if _reranker is not None:
        return True
    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANKER_MODEL)
        logger.info("已加载 Reranker 模型: %s", RERANKER_MODEL)
        return True
    except ImportError:
        logger.warning("sentence-transformers 未安装，使用关键词重排序降级策略")
        return False
    except Exception as exc:
        logger.warning("Reranker 模型加载失败（%s），降级为关键词策略", exc)
        return False


async def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    对候选结果进行重排序，返回最相关的 top_n 条。

    Args:
        query:      用户查询文本
        candidates: 粗召回结果列表，每条必须有 content 字段
        top_n:      重排后保留条数

    Returns:
        重排后的结果，按相关度降序排列，每条增加 rerank_score 字段
    """
    if not candidates:
        return []
    if len(candidates) <= top_n:
        return candidates

    if _init_reranker() and _reranker is not None:
        try:
            import asyncio
            pairs = [(query, c["content"]) for c in candidates]
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                lambda: _reranker.predict(pairs).tolist()
            )
            for c, s in zip(candidates, scores):
                c["rerank_score"] = float(s)
            ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
            return ranked[:top_n]
        except Exception as exc:
            logger.exception("Cross-Encoder 重排序失败: %s，降级为关键词策略", exc)

    # 降级：关键词匹配计数重排
    return _keyword_rerank(query, candidates, top_n)


def _keyword_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    """
    关键词匹配重排序（Cross-Encoder 不可用时的降级策略）

    逻辑：计算候选文本包含查询关键词的比例，比例越高排名越前。
    """
    keywords = [w.strip() for w in query if len(w.strip()) > 1]
    if not keywords:
        return candidates[:top_n]

    for c in candidates:
        content = c.get("content", "").lower()
        hit = sum(1 for kw in keywords if kw.lower() in content)
        c["rerank_score"] = hit / len(keywords) + c.get("score", 0) * 0.5

    ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)
    return ranked[:top_n]
