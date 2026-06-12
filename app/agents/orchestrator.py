"""
OrchestratorAgent — A2A 多 Agent 编排主控

职责：
  1. 意图识别：判断用户消息属于哪个业务域（health/device/ticket/general）
  2. Agent 路由：把请求委托给对应的子 Agent
  3. 结果聚合：收集子 Agent 的回复，返回给 API 层

A2A 模式说明：
  Orchestrator 和子 Agent 都是独立的对象（可以运行在独立进程/服务）。
  本 Demo 中为简化部署，采用进程内直接调用（in-process A2A），
  生产环境可通过消息队列（Redis Pub/Sub）或 gRPC 实现跨服务调用。

意图关键词规则（规则匹配 + 可扩展为 LLM 分类器）：
  health  : 健康/症状/生病/疫苗/体重/饮食/...
  device  : 设备/传感器/OTA/升级/离线/在线/...
  ticket  : 工单/报修/投诉/客服/反馈/...
  general : 默认
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# 意图关键词映射
_INTENT_KEYWORDS: dict[str, list[str]] = {
    "health": [
        "健康", "症状", "生病", "不吃", "呕吐", "腹泻", "发烧", "咳嗽",
        "疫苗", "体重", "喝水", "精神", "打蔫", "过敏", "皮肤", "毛发",
        "脱毛", "眼睛", "耳朵", "牙齿", "驱虫", "绝育", "医疗", "看诊",
        "兽医", "饮食", "喂食", "健康报告", "体检",
    ],
    "device": [
        "设备", "传感器", "IoT", "iot", "离线", "在线", "故障", "OTA",
        "升级", "固件", "信号", "wifi", "Wi-Fi", "连接", "设备码",
        "摄像头", "水盆", "喂食器", "温度计",
    ],
    "ticket": [
        "工单", "报修", "投诉", "建议", "反馈", "客服", "退款", "换货",
        "售后", "问题", "不好用", "坏了", "创建工单", "提交",
    ],
}


def _identify_intent(message: str) -> str:
    """规则匹配意图识别，返回 health/device/ticket/general"""
    lower = message.lower()
    # 按权重顺序匹配
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                return intent
    return "general"


class OrchestratorAgent(BaseAgent):
    """
    A2A 多 Agent 编排主控器

    流程：
      用户消息 → 意图识别 → 路由到子 Agent → 获取回复 → 返回
    """

    name = "orchestrator"
    domain = "general"

    def __init__(self) -> None:
        super().__init__()
        # 懒加载子 Agent（避免循环导入和不必要的初始化开销）
        self._agents: dict[str, BaseAgent] = {}

    def _get_sub_agent(self, intent: str) -> BaseAgent:
        """获取或创建对应意图的子 Agent（工厂模式+缓存）"""
        if intent not in self._agents:
            # 按意图类型懒加载对应的专业 Agent，避免循环导入
            if intent == "health":
                from app.agents.health_agent import HealthAgent
                self._agents[intent] = HealthAgent()  # 健康咨询 Agent
            elif intent == "device":
                from app.agents.device_agent import DeviceAgent
                self._agents[intent] = DeviceAgent()  # 设备问题 Agent
            elif intent == "ticket":
                from app.agents.ticket_agent import TicketAgent
                self._agents[intent] = TicketAgent()  # 工单处理 Agent
            else:
                # general 意图由 Orchestrator 自己处理（LLM 直接回答，不调用工具）
                self._agents[intent] = self
        return self._agents[intent]

    async def run(
        self,
        user_message: str,
        session_id: str,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        history: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        A2A 编排主流程：
        1. 意图识别
        2. 路由到子 Agent
        3. 返回子 Agent 结果（含 intent 字段）
        """
        intent = _identify_intent(user_message)
        logger.info(
            "[Orchestrator] session=%s intent=%s msg=%r",
            session_id, intent, user_message[:60],
        )

        # general 意图直接用 LLM 回答，不调用工具
        if intent == "general":
            answer = await self._llm_with_tools(
                system_prompt="你是QMI平台的智能助手，为宠物主人提供有关宠物护理、设备使用和平台服务的帮助。回答简洁、亲切，如果不确定请建议用户联系客服。",
                user_message=user_message,
                tool_results=[],
                history=history,
            )
            return {
                "answer": answer,
                "tool_calls": [],
                "agent": self.name,
                "intent": intent,
            }

        # 路由到子 Agent
        sub_agent = self._get_sub_agent(intent)
        result = await sub_agent.run(
            user_message=user_message,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            history=history,
            **kwargs,
        )
        result["intent"] = intent  # 确保 intent 字段存在
        return result
