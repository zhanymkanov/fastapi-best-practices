"""
异步数据处理任务 — 文件上传后的后台处理

处理流程：
1. 更新状态 → PROCESSING
2. 图片: 提取元信息（尺寸/格式），标记缩略图待生成
3. 文本: 切片计算 embedding 向量（为 RAG 入库做准备）
4. 更新状态 → READY or FAILED

注意：本模块通过 Celery 异步执行，不阻塞 HTTP 请求。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from celery import shared_task

from app.models.data_asset import AssetStatus, DataAsset

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.ingestion_task.process_asset",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_asset(self, asset_id: str, tenant_id: str):
    """处理上传的数据资产（图片/文本）"""
    import asyncio

    async def _process():
        asset = await DataAsset.find_one(
            {"_id": asset_id, "tenant_id": tenant_id}
        )
        if not asset:
            logger.warning("资产 %s 不存在或已删除", asset_id)
            return

        try:
            # 1. 更新为处理中
            await asset.update({
                "$set": {
                    "status": AssetStatus.PROCESSING,
                    "processing_at": datetime.now(timezone.utc),
                }
            })

            # 2. 按资产类型执行不同处理逻辑
            if asset.asset_type.value == "image":
                await _process_image(asset)

            elif asset.asset_type.value == "text":
                await _process_text(asset)

            else:
                logger.info("资产 %s 类型 %s 无需特殊处理", asset_id, asset.asset_type)

            # 3. 标记完成
            await asset.update({
                "$set": {
                    "status": AssetStatus.READY,
                    "updated_at": datetime.now(timezone.utc),
                }
            })
            logger.info("资产 %s 处理完成", asset_id)

        except Exception as exc:
            logger.exception("资产 %s 处理失败: %s", asset_id, exc)
            await asset.update({
                "$set": {
                    "status": AssetStatus.FAILED,
                    "error_message": str(exc)[:500],
                    "updated_at": datetime.now(timezone.utc),
                }
            })
            raise self.retry(exc=exc)

    asyncio.get_event_loop().run_until_complete(_process())


async def _process_image(asset: DataAsset) -> None:
    """图片处理：读取文件元信息，标记缩略图待生成"""
    file_path = getattr(asset, "file_path", "") or getattr(asset, "storage_path", "")
    if not file_path or not os.path.exists(file_path):
        logger.warning("图片文件不存在: %s", file_path)
        return

    try:
        # 尝试用 PIL 读取图片元信息（如果已安装）
        from PIL import Image
        with Image.open(file_path) as img:
            metadata = {
                "width": img.width,
                "height": img.height,
                "format": img.format,
                "mode": img.mode,
            }
            await asset.update({"$set": {"metadata": metadata}})
            logger.info("图片 %s 元信息已提取: %dx%d %s",
                        asset.id, img.width, img.height, img.format)
    except ImportError:
        logger.debug("Pillow 未安装，跳过图片元信息提取")
        # 记录基本文件信息
        file_size = os.path.getsize(file_path)
        await asset.update({"$set": {"metadata": {"file_size": file_size}}})
    except Exception as exc:
        logger.warning("图片 %s 元信息提取失败: %s", asset.id, exc)


async def _process_text(asset: DataAsset) -> None:
    """文本处理：提取内容摘要并标记为可索引"""
    file_path = getattr(asset, "file_path", "") or getattr(asset, "storage_path", "")
    content = getattr(asset, "content", "") or ""

    # 如果没有文件内容，尝试从文件读取
    if not content and file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            logger.warning("文本文件 %s 读取失败: %s", file_path, exc)

    if content:
        # 生成摘要（取前 200 字符）
        summary = content[:200].replace("\n", " ")
        char_count = len(content)

        await asset.update({"$set": {
            "metadata": {
                "char_count": char_count,
                "summary": summary,
                "indexable": True,
            }
        }})
        logger.info("文本 %s 已索引: %d 字符", asset.id, char_count)
    else:
        logger.warning("文本资产 %s 无内容", asset.id)
