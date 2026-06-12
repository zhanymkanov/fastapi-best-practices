"""
RAG Chain — 完整的检索增强生成流程

执行步骤：
  1. 混合检索（Milvus 向量 + 关键词 BM25 融合）
  2. Reranker 精排（Cross-Encoder，取 top 5）
  3. 构建 Prompt（知识库上下文 + 用户问题）
  4. 调用 LLM 生成回答
  5. 返回回答 + 来源引用

典型调用场景：
  - 宠物健康咨询问答
  - 设备故障智能诊断
  - OTA 升级指引
  - 会员权益政策查询
"""
from __future__ import annotations

import logging
from typing import Any

from app.rag.embedder import embed_query
from app.rag.retriever import retriever
from app.rag.reranker import rerank

logger = logging.getLogger(__name__)

# 系统 Prompt（明确 AI 的角色和回答规范）
SYSTEM_PROMPT = """
你是QMI宠物生态平台的智能助理，精通宠物健康护理、设备使用和会员服务。

回答规范：
1. 优先基于提供的知识库内容作答，不要编造事实
2. 涉及宠物健康的问题，必须提醒"以下建议仅供参考，如情况严重请立即就医"
3. 知识库中没有相关内容时，如实告知并给出通用建议
4. 回答简洁专业，中文作答，避免无关内容
""".strip()


async def rag_query(
    question: str,
    category: str | None = None,
    top_k: int = 20,
    top_n: int = 5,
    extra_context: str | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """
    执行完整的 RAG 检索问答流程。

    Args:
        question:      用户问题
        category:      知识库分类过滤（health/device/ota/member/None=全库）
        top_k:         粗召回数量（Milvus 返回条数）
        top_n:         精排后保留条数（传给 LLM 的上下文条数）
        extra_context: 额外的业务上下文（如宠物档案、设备信息）
        stream:        是否流式输出（暂未实现，预留接口）

    Returns:
        {
          "answer":  "AI 生成的回答",
          "sources": ["来源1", "来源2"],
          "chunks":  [...],   # 检索到的原始片段
          "backend": "rag" | "llm_only"
        }
    """
    # ── Step 1: 混合检索（向量 + 关键词）──────────────────────────────────────
    try:
        candidates = await retriever.hybrid_search(
            query=question,
            top_k=top_k,  # 粗召回数量
            category=category,
        )
    except Exception as exc:
        logger.exception("RAG 检索失败，降级为纯 LLM: %s", exc)
        candidates = []  # 检索失败降级为空

    # ── Step 2: 精排序（Cross-Encoder 重排）───────────────────────────────────
    if candidates:
        try:
            candidates = await rerank(question, candidates, top_n=top_n)  # 取 top_n 条
        except Exception as exc:
            logger.exception("Reranker 失败，使用粗召回结果: %s", exc)
            candidates = candidates[:top_n]  # 降级：取前 top_n 条

    # ── Step 3: 构建提示上下文──────────────────────────────────────────────────
    context_parts = [c["content"] for c in candidates if c.get("content")]
    sources = list({c.get("source", "") for c in candidates if c.get("source")})
    sep = "\n\n---\n\n"
    context = sep.join(context_parts) if context_parts else "（暂无相关知识库内容）"

    # 如果有额外业务信息（宠物档案、设备状态等），加入上下文
    if extra_context:
        context = "【业务信息】" + "\n" + extra_context + "\n\n【知识库参考】" + "\n" + context

    # ── Step 4: 构建 Prompt & 调用 LLM ──────────────────────────────────────
    user_prompt = (
        "【知识库内容】"
        + "\n"
        + context
        + "\n\n"
        + "【用户问题】"
        + "\n"
        + question
        + "\n\n"
        + "请根据上述知识库内容回答用户问题，若知识库内容与问题相关性低，请如实说明并给出通用建议。"
    )

    backend = "rag" if candidates else "llm_only"  # 标记是否用了 RAG

    try:
        # Step 5: 调用 LLM 生成回答
        from app.integrations.llm_client import get_llm
        llm = get_llm()
        resp = await llm.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        answer = resp["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.exception("LLM 调用失败: %s", exc)
        # 降级方案：直接返回最相关的知识库片段
        if candidates:
            answer = "根据知识库检索结果：" + "\n\n" + candidates[0]["content"]
        else:
            answer = "抱歉，AI 服务暂时不可用，请稍后重试或联系人工客服。"

    return {
        "answer": answer,
        "sources": sources,  # 知识库来源
        "chunks": candidates,  # 检索到的原始片段
        "backend": backend,  # 使用的后端（rag 或 llm_only）
        "chunk_count": len(candidates),  # 检索条数
    }
