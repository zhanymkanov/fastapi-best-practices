"""
会员权益 API — 会员信息 + 权益管理

端点：
  GET    /api/v1/members/me            — 获取当前用户会员信息
  GET    /api/v1/members/benefits      — 获取会员权益列表
  POST   /api/v1/members/benefits/use  — 使用会员权益
  GET    /api/v1/members/points        — 积分记录查询
  POST   /api/v1/members/upgrade       — 会员升级（购买/续费）

会员等级体系：
  免费版 → 银牌会员 → 黄金会员 → 铂金会员
  权益逐级增强：更多 AI 咨询次数、设备保修延长、优先客服、专属健康报告等
"""
from __future__ import annotations

import logging
from enum import Enum

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/members", tags=["会员权益"])


# ── 枚举 ─────────────────────────────────────────────────────────────────────

class MemberLevel(str, Enum):
    FREE = "free"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


# ── Schemas ──────────────────────────────────────────────────────────────────

class MemberInfo(BaseModel):
    user_id: str
    level: MemberLevel
    level_label: str
    points: int
    valid_until: str | None
    joined_at: str


class BenefitItem(BaseModel):
    benefit_id: str
    name: str
    description: str
    benefit_type: str
    remaining_quota: int = Field(description="剩余可用次数，-1 表示无限")
    used_quota: int = 0
    valid_until: str | None = None
    is_available: bool = True


class BenefitUseRequest(BaseModel):
    benefit_id: str
    context: dict = Field(default_factory=dict, description="使用上下文（如健康报告对应的 pet_id）")


# ── 路由 ─────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=MemberInfo, summary="获取当前用户会员信息")
async def get_member_info() -> MemberInfo:
    """
    获取当前登录用户的会员等级、积分、到期时间等基础会员信息。
    """
    # Demo 数据 — 实际项目查询 MongoDB users 集合
    return MemberInfo(
        user_id="user_demo_001",
        level=MemberLevel.GOLD,
        level_label="黄金会员",
        points=2850,
        valid_until="2025-12-31",
        joined_at="2023-06-01",
    )


@router.get("/benefits", summary="获取会员权益列表")
async def list_benefits() -> dict:
    """
    返回当前用户会员等级对应的所有权益，以及每项权益的剩余配额。
    权益包括：AI 咨询次数、健康报告、设备保修延期、在线问诊券等。
    """
    benefits = [
        BenefitItem(
            benefit_id="BEN-AI-CONSULT",
            name="AI 健康咨询",
            description="每月可使用 AI 进行宠物健康咨询的次数",
            benefit_type="ai_consult",
            remaining_quota=3,
            used_quota=2,
            is_available=True,
        ),
        BenefitItem(
            benefit_id="BEN-HEALTH-REPORT",
            name="专属健康报告",
            description="由 AI 生成的宠物全面健康分析报告，每季度 1 次",
            benefit_type="health_report",
            remaining_quota=1,
            used_quota=0,
            is_available=True,
        ),
        BenefitItem(
            benefit_id="BEN-WARRANTY",
            name="设备延保",
            description="IoT 设备保修期从 12 个月延长至 24 个月",
            benefit_type="device_warranty",
            remaining_quota=-1,
            used_quota=0,
            valid_until="2025-12-31",
            is_available=True,
        ),
        BenefitItem(
            benefit_id="BEN-VET-CONSULT",
            name="在线问诊券",
            description="每季度 1 次免费在线兽医问诊",
            benefit_type="vet_consultation",
            remaining_quota=0,
            used_quota=1,
            is_available=False,
        ),
    ]
    available = [b for b in benefits if b.is_available]
    return {
        "level": "gold",
        "level_label": "黄金会员",
        "benefits": [b.model_dump() for b in benefits],
        "available_count": len(available),
        "total_count": len(benefits),
    }


@router.post("/benefits/use", summary="使用会员权益")
async def use_benefit(req: BenefitUseRequest) -> dict:
    """
    核销一次会员权益，减少对应配额。
    调用前应先通过 /benefits 接口确认该权益仍有剩余配额。
    """
    # Demo 逻辑 — 实际项目更新数据库配额，并记录使用日志
    return {
        "benefit_id": req.benefit_id,
        "used": True,
        "remaining_quota": 2,
        "message": "权益已成功使用，本月剩余次数：2",
    }


@router.get("/points", summary="查询积分记录")
async def get_points_history() -> dict:
    """查询用户积分变动历史（购买、兑换、任务奖励等）。"""
    records = [
        {"date": "2025-01-15", "type": "earn", "points": +100, "description": "购买宠物食品"},
        {"date": "2025-01-10", "type": "earn", "points": +50, "description": "完成每日健康打卡"},
        {"date": "2025-01-05", "type": "redeem", "points": -200, "description": "兑换在线问诊券"},
    ]
    return {"current_points": 2850, "records": records, "total_records": len(records)}


@router.post("/upgrade", summary="会员升级购买")
async def upgrade_membership(target_level: str, months: int = 12) -> dict:
    """
    购买或续费指定会员等级。
    返回支付链接（实际项目接入支付宝/微信支付）。
    """
    price_map = {
        "silver": 98,
        "gold": 198,
        "platinum": 398,
    }
    if target_level not in price_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的会员等级: {target_level}",
        )
    total = price_map[target_level] * months
    return {
        "target_level": target_level,
        "months": months,
        "total_price": total,
        "payment_url": f"https://pay.example.com/order?plan={target_level}&months={months}",
        "message": f"请在 10 分钟内完成支付，升级为{target_level}会员",
    }
