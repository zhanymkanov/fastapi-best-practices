"""
Retriever — Milvus 向量检索模块

功能：
  - insert(chunks)    : 插入知识库文档块（向量 + 元数据）
  - search(query)     : 向量相似度检索
  - keyword_search    : 关键词 BM25 模拟检索
  - hybrid_search     : 向量 + 关键词混合检索（提升召回率）

Collection Schema（Milvus）：
  - id         : VARCHAR(64), primary key
  - embedding  : FLOAT_VECTOR(1024)
  - content    : VARCHAR(65535), 原始文本
  - source     : VARCHAR(512),  来源（文件名/URL）
  - category   : VARCHAR(64),   分类（health/device/ota/member）
  - created_at : INT64,         时间戳

生产建议：
  - 创建 IVF_FLAT 或 HNSW 索引，batch 写入
  - 使用分区（Partition）按 category 隔离
  - 查询 top_k 建议 20-50，再经过 Reranker 取前 5-10 条
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION_NAME = "pet_knowledge"
EMBEDDING_DIM = 1024
DEFAULT_TOP_K = 10


class MilvusRetriever:
    """
    Milvus 向量检索器

    Demo 模式：如果 Milvus 未连接，自动降级到内存检索（in-memory mock），
    保证 API 在没有 Milvus 服务时也能启动和响应。
    """

    def __init__(self, collection_name: str = COLLECTION_NAME) -> None:
        self.collection_name = collection_name
        self._milvus_available = False
        self._mock_store: list[dict[str, Any]] = []  # mock 存储（in-memory）
        self._collection = None

    def _connect(self) -> bool:
        """尝试连接 Milvus，失败时降级 mock"""
        if self._milvus_available:
            return True
        try:
            from pymilvus import MilvusClient
            from app.core.config import settings
            client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            )
            # 如果集合不存在则创建
            if not client.has_collection(self.collection_name):
                client.create_collection(
                    collection_name=self.collection_name,
                    dimension=EMBEDDING_DIM,
                    primary_field_name="id",
                    vector_field_name="embedding",
                )
                logger.info("已创建 Milvus 集合: %s", self.collection_name)
            self._collection = client
            self._milvus_available = True
            logger.info("Milvus 连接成功: %s:%s", settings.MILVUS_HOST, settings.MILVUS_PORT)
            return True
        except Exception as exc:
            logger.warning("Milvus 不可用（%s），使用 in-memory mock", exc)
            return False

    async def insert(self, chunks: list[dict[str, Any]]) -> int:
        """
        批量插入知识库块。

        chunks 格式：
          [{"content": "...", "source": "...", "category": "health", "embedding": [...]}]
        """
        from app.rag.embedder import embed_texts

        # Step 1: 对没有 embedding 的 chunk 批量向量化
        to_embed = [c for c in chunks if not c.get("embedding")]
        if to_embed:
            texts = [c["content"] for c in to_embed]
            vecs = await embed_texts(texts)  # 调用 embedding 模型
            for c, v in zip(to_embed, vecs):
                c["embedding"] = v

        # Step 2: 尝试存入 Milvus，失败则降级到内存
        if self._connect() and self._collection:
            try:
                # 构建 Milvus 格式的数据
                data = [
                    {
                        "id": c.get("id", str(uuid.uuid4())),
                        "embedding": c["embedding"],
                        "content": c["content"][:65535],  # Milvus VARCHAR 最大长度
                        "source": c.get("source", ""),
                        "category": c.get("category", "general"),
                        "created_at": int(time.time()),
                    }
                    for c in chunks
                ]
                self._collection.insert(self.collection_name, data)  # 向量入库
                logger.info("Milvus 插入 %d 条知识库数据", len(data))
                return len(data)
            except Exception as exc:
                logger.exception("Milvus 插入失败: %s", exc)

        # 降级方案：存入内存 mock 存储
        self._mock_store.extend(chunks)
        logger.debug("Mock 存储插入 %d 条", len(chunks))
        return len(chunks)

    async def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        向量相似度检索（粗召回）。

        Args:
            query:    查询文本
            top_k:    返回条数
            category: 过滤分类（可选）

        Returns:
            [{"content": "...", "source": "...", "score": 0.92, ...}]
        """
        from app.rag.embedder import embed_query
        
        # Step 1: 把查询文本向量化
        query_vec = await embed_query(query)

        # Step 2: 向 Milvus 发起向量检索
        if self._connect() and self._collection:
            try:
                # 构建分类过滤条件
                filter_expr = f"category == \"{category}\"" if category else ""
                results = self._collection.search(
                    collection_name=self.collection_name,
                    data=[query_vec],
                    limit=top_k,
                    filter=filter_expr or None,
                    output_fields=["content", "source", "category"],
                )
                hits = results[0] if results else []
                # 格式化返回结果
                return [
                    {
                        "content": h.get("entity", {}).get("content", ""),
                        "source": h.get("entity", {}).get("source", ""),
                        "category": h.get("entity", {}).get("category", ""),
                        "score": h.get("distance", 0.0),  # 相似度分数
                    }
                    for h in hits
                ]
            except Exception as exc:
                logger.exception("Milvus 检索失败: %s", exc)

        # 降级：内存检索（简单余弦相似度）
        return self._mock_search(query_vec, top_k, category)

    def _mock_search(
        self, query_vec: list[float], top_k: int, category: str | None
    ) -> list[dict[str, Any]]:
        """内存 mock 检索（开发/测试用）"""
        import math

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        candidates = self._mock_store
        if category:
            candidates = [c for c in candidates if c.get("category") == category]

        if not candidates:
            # 没有数据时返回示例数据（Demo 效果）
            return _demo_results(query_vec[:0], top_k)

        scored = []
        for chunk in candidates:
            emb = chunk.get("embedding", [])
            if emb:
                sim = cosine_sim(query_vec, emb)
                scored.append({**chunk, "score": sim})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def hybrid_search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        category: str | None = None,
        keyword_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """
        混合检索 = 向量检索 + 关键词检索结果融合（RRF 算法）

        向量检索擅长语义理解，关键词检索擅长精确匹配，
        两者融合能有效提升召回率和命中准确率。
        """
        # 向量检索结果（权重 0.7）
        vec_results = await self.search(query, top_k=top_k * 2, category=category)

        # 关键词检索（权重 0.3，简单 in 匹配）
        kw_results = self._keyword_search(query, top_k=top_k * 2, category=category)

        # RRF (Reciprocal Rank Fusion) 融合
        scores: dict[str, float] = {}
        content_map: dict[str, dict] = {}

        for rank, item in enumerate(vec_results):
            key = item["content"][:100]
            scores[key] = scores.get(key, 0) + (1 - keyword_weight) / (rank + 60)
            content_map[key] = item

        for rank, item in enumerate(kw_results):
            key = item["content"][:100]
            scores[key] = scores.get(key, 0) + keyword_weight / (rank + 60)
            content_map[key] = item

        merged = sorted(
            [{"score": s, **content_map[k]} for k, s in scores.items()],
            key=lambda x: x["score"],
            reverse=True,
        )
        return merged[:top_k]

    def _keyword_search(
        self, query: str, top_k: int, category: str | None
    ) -> list[dict[str, Any]]:
        """简单关键词检索（BM25 的轻量替代，生产环境可接 Elasticsearch）"""
        keywords = [w.strip() for w in query.split() if len(w.strip()) > 1]
        candidates = self._mock_store
        if category:
            candidates = [c for c in candidates if c.get("category") == category]

        scored = []
        for chunk in candidates:
            content = chunk.get("content", "")
            hit = sum(1 for kw in keywords if kw in content)
            if hit > 0:
                scored.append({**chunk, "score": hit / max(len(keywords), 1)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


def _demo_results(_, top_k: int) -> list[dict[str, Any]]:
    """当知识库为空时返回示例数据（纯展示用，不影响生产逻辑）"""
    samples = [
        {
            "content": "猫咪出现呕吐症状时，应先观察呕吐频率和内容物。单次呕吐可能是进食过快，若持续超过24小时或呕吐物带血，应立即就医。",
            "source": "宠物健康手册_v2.pdf",
            "category": "health",
            "score": 0.95,
        },
        {
            "content": "狗狗发热判断：正常体温 37.5-38.5°C，可通过耳温计或肛温计测量。超过 39.5°C 需就医，超过 40°C 属于紧急情况。",
            "source": "常见宠物疾病指南.pdf",
            "category": "health",
            "score": 0.91,
        },
        {
            "content": "宠物智能喂食器断线处理步骤：1) 检查 Wi-Fi 密码 2) 重启设备（长按复位键 5 秒）3) 重新配网 4) 若仍无法连接请联系客服。",
            "source": "智能设备使用说明书.pdf",
            "category": "device",
            "score": 0.88,
        },
    ]
    return samples[:top_k]


# 全局单例
retriever = MilvusRetriever()
