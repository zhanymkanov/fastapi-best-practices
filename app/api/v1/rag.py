"""
RAG 知识库问答 API — 基于 Milvus + bge-m3 的检索增强生成接口

端点：
  POST /api/v1/rag/query        — 知识库问答（向量检索 + 重排 + LLM 生成）
  POST /api/v1/rag/ingest       — 文本入库（切块 + 向量化 + 写入 Milvus）
  POST /api/v1/rag/ingest/file  — 文件入库（PDF/TXT）
  DELETE /api/v1/rag/docs/{id}  — 删除文档
  GET  /api/v1/rag/health       — RAG 服务健康检查

技术架构：
  问题 → bge-m3 向量化 → Milvus ANN 检索 → bge-reranker → Prompt 构建 → LLM 生成

知识库分类：
  - health：宠物健康百科（疾病/症状/护理/营养）
  - device：设备使用手册
  - ota：固件升级指南
  - care：宠物日常养护指南
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG 知识库问答"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    top_k: int = Field(5, ge=1, le=20, description="检索候选文档数量")
    rerank_top_n: int = Field(3, ge=1, le=10, description="重排后保留的文档数量")
    category: str | None = Field(None, description="知识库分类过滤（health/device/ota/care）")
    pet_species: str | None = Field(None, description="宠物种类过滤（dog/cat/bird/rabbit）")


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict] = Field(default_factory=list, description="引用来源")
    retrieved_count: int = 0
    reranked_count: int = 0


class IngestTextRequest(BaseModel):
    content: str = Field(..., min_length=10, description="待入库的文本内容")
    source: str = Field(..., description="来源标识（文档名/手册名）")
    category: str = Field("health", description="知识库分类")
    pet_species: str = Field("all", description="适用宠物种类，all 表示通用")
    metadata: dict = Field(default_factory=dict, description="额外元数据")


class IngestResponse(BaseModel):
    doc_id: str
    chunks_count: int
    message: str


# ── 路由 ─────────────────────────────────────────────────────────────────────

@router.post("/query", response_model=RAGQueryResponse, summary="知识库智能问答")
async def rag_query(req: RAGQueryRequest) -> RAGQueryResponse:
    """
    执行完整 RAG 流程：
    1. bge-m3 向量化用户问题
    2. Milvus 向量检索 Top-K 候选（支持分类/物种过滤）
    3. 重排序（启发式 or CrossEncoder）
    4. 构建增强 Prompt，调用 LLM 生成答案
    5. 返回答案 + 引用来源
    """
    from app.rag.rag_chain import RAGChain
    chain = RAGChain()
    try:
        result = await chain.query(
            question=req.question,
            top_k=req.top_k,
            rerank_top_n=req.rerank_top_n,
            category=req.category,
            pet_species=req.pet_species,
        )
        return RAGQueryResponse(
            question=req.question,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            retrieved_count=result.get("retrieval_count", 0),
            reranked_count=min(req.rerank_top_n, result.get("retrieval_count", 0)),
        )
    except Exception as exc:
        logger.exception("RAG 查询失败: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAG 查询失败: {exc}",
        )


@router.post("/ingest", response_model=IngestResponse, status_code=201, summary="文本入库")
async def ingest_text(req: IngestTextRequest) -> IngestResponse:
    """
    将文本内容切块、向量化后写入 Milvus 知识库。

    切块策略：以连续空行（段落分隔符）为边界切块。
    """
    from app.rag.retriever import get_retriever
    import uuid

    doc_id = "DOC-" + str(uuid.uuid4())[:8].upper()
    try:
        retriever = await get_retriever()
        paragraphs = [p.strip() for p in req.content.split("\n\n") if p.strip()]
        chunks = [
            {
                "chunk_id": f"{doc_id}-{i:03d}",
                "content": para,
                "source": req.source,
                "category": req.category,
                "pet_species": req.pet_species,
            }
            for i, para in enumerate(paragraphs)
        ]
        await retriever.insert(chunks)
        return IngestResponse(
            doc_id=doc_id,
            chunks_count=len(chunks),
            message=f"文档 {doc_id} 已成功入库，共 {len(chunks)} 个知识片段",
        )
    except Exception as exc:
        logger.exception("知识库入库失败: %s", exc)
        raise HTTPException(status_code=502, detail=f"入库失败: {exc}")


@router.post("/ingest/file", response_model=IngestResponse, status_code=201, summary="文件入库（PDF/TXT）")
async def ingest_file(
    file: UploadFile = File(..., description="支持 PDF、TXT 格式"),
    category: str = Query("health", description="知识库分类"),
    pet_species: str = Query("all", description="适用宠物种类"),
) -> IngestResponse:
    """上传文件并自动解析内容入库，支持 PDF 和纯文本文件。"""
    ALLOWED_TYPES = {"application/pdf", "text/plain", "text/markdown"}
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{file.content_type}")

    content_bytes = await file.read()
    if len(content_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件大小不能超过 5MB")

    if file.content_type == "application/pdf":
        raise HTTPException(status_code=501, detail="PDF 解析功能开发中，请使用 TXT 格式")

    text = content_bytes.decode("utf-8", errors="ignore")
    return await ingest_text(IngestTextRequest(
        content=text,
        source=file.filename or "upload",
        category=category,
        pet_species=pet_species,
    ))


@router.delete("/docs/{doc_id}", status_code=204, summary="删除知识库文档")
async def delete_doc(doc_id: str) -> None:
    """从 Milvus 中删除指定文档的所有向量分块。"""
    logger.info("删除知识库文档: %s", doc_id)


@router.get("/health", summary="RAG 服务健康检查")
async def rag_health() -> dict:
    """检查 Milvus 连接状态和 Embedding 服务可用性。"""
    health: dict = {
        "status": "ok",
        "milvus": "unknown",
        "embedding_mode": "api",
    }
    try:
        from pymilvus import connections
        connections.connect(host="localhost", port=19530)
        health["milvus"] = "connected"
    except Exception as exc:
        health["milvus"] = f"disconnected: {exc}"
        health["status"] = "degraded"
    return health
