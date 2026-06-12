"""
宠物健康分析工具 — MCP 工具封装

业务场景：
  - 宠物整体健康状态摘要（体重趋势、近期记录）
  - 症状分析与初步建议（AI 辅助，非诊断）
  - 疫苗接种记录查询
  - 健康档案历史
"""
from __future__ import annotations

import logging
from typing import Any

from app.mcp.base import BaseMCPTool, MCPToolMeta

logger = logging.getLogger(__name__)


class GetPetHealthSummaryTool(BaseMCPTool):
    """获取宠物健康摘要"""

    meta = MCPToolMeta(
        name="get_pet_health_summary",
        description="获取指定宠物的健康状态摘要，包含体重趋势、最近就诊记录、健康评分、饮食情况。",
        parameters={
            "type": "object",
            "properties": {
                "pet_id": {"type": "string", "description": "宠物 ID"},
            },
            "required": ["pet_id"],
        },
        category="health",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        pet_id = params["pet_id"]
        return {
            "success": True,
            "pet_id": pet_id,
            "health_score": 88,
            "weight_trend": "stable",
            "last_checkup": "2026-05-20",
            "vaccinations_up_to_date": True,
            "diet_notes": "建议减少零食，每日主食 200g",
            "alerts": [],
            "_mock": True,
        }


class AnalyzePetSymptomsTool(BaseMCPTool):
    """症状分析（AI 辅助，非诊断）"""

    meta = MCPToolMeta(
        name="analyze_pet_symptoms",
        description=(
            "根据描述的宠物症状给出初步分析和建议。"
            "注意：本工具仅提供参考，不能替代执业兽医的诊断，紧急情况请立即就医。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "pet_id": {"type": "string", "description": "宠物 ID"},
                "symptoms": {"type": "string", "description": "症状描述，如：食欲不振、精神萎靡、呕吐"},
                "duration_hours": {"type": "integer", "description": "症状持续时长（小时）"},
            },
            "required": ["pet_id", "symptoms"],
        },
        category="health",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        pet_id = params["pet_id"]
        symptoms = params["symptoms"]
        duration = params.get("duration_hours", 0)

        # 紧急症状关键词检测
        urgent_keywords = ["抽搐", "呼吸困难", "大量出血", "晕厥", "无法站立"]
        is_urgent = any(kw in symptoms for kw in urgent_keywords)

        result = {
            "success": True,
            "pet_id": pet_id,
            "symptoms": symptoms,
            "duration_hours": duration,
            "is_urgent": is_urgent,
            "analysis": "症状可能与消化道问题或应激反应有关，建议观察 24 小时。",
            "suggestions": [
                "保持饮水充足",
                "暂时喂食易消化食物（熟鸡胸肉/米饭）",
                "避免剧烈活动",
                "若 24 小时后无改善，建议就医",
            ],
            "disclaimer": "⚠️ 以上分析由 AI 生成，仅供参考，不能替代执业兽医诊断。",
            "_mock": True,
        }

        if is_urgent:
            result["suggestions"] = ["⚠️ 检测到紧急症状！请立即联系最近的宠物医院或拨打宠物急救热线。"]

        return result


class GetHealthHistoryTool(BaseMCPTool):
    """获取宠物健康档案历史"""

    meta = MCPToolMeta(
        name="get_health_history",
        description="查询宠物的历史健康记录，包括就诊记录、体检报告、用药记录等时间线。",
        parameters={
            "type": "object",
            "properties": {
                "pet_id": {"type": "string", "description": "宠物 ID"},
                "limit": {"type": "integer", "description": "返回记录数量，默认 10"},
            },
            "required": ["pet_id"],
        },
        category="health",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        pet_id = params["pet_id"]
        limit = params.get("limit", 10)
        mock_history = [
            {"date": "2026-05-20", "type": "checkup", "summary": "年度体检，一切正常", "vet": "王医生"},
            {"date": "2026-03-10", "type": "vaccination", "summary": "狂犬疫苗注射", "vet": "李医生"},
            {"date": "2026-01-05", "type": "treatment", "summary": "外耳炎治疗，滴耳液 7 天", "vet": "王医生"},
        ]
        return {
            "success": True,
            "pet_id": pet_id,
            "records": mock_history[:limit],
            "_mock": True,
        }


class GetVaccinationRecordTool(BaseMCPTool):
    """查询宠物疫苗接种记录"""

    meta = MCPToolMeta(
        name="get_vaccination_record",
        description="查询宠物的疫苗接种记录和下次接种提醒，包括狂犬、五联苗、驱虫等。",
        parameters={
            "type": "object",
            "properties": {
                "pet_id": {"type": "string", "description": "宠物 ID"},
            },
            "required": ["pet_id"],
        },
        category="health",
    )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        pet_id = params["pet_id"]
        return {
            "success": True,
            "pet_id": pet_id,
            "vaccinations": [
                {
                    "name": "狂犬疫苗",
                    "last_date": "2026-03-10",
                    "next_date": "2027-03-10",
                    "status": "up_to_date",
                },
                {
                    "name": "猫五联疫苗",
                    "last_date": "2026-02-15",
                    "next_date": "2027-02-15",
                    "status": "up_to_date",
                },
                {
                    "name": "体内驱虫",
                    "last_date": "2026-05-01",
                    "next_date": "2026-08-01",
                    "status": "due_soon",
                },
            ],
            "_mock": True,
        }
