"""
Agent 编排 API — A2A 多智能体对话接口

端点：
  POST /api/v1/agent/chat         — 发送消息给 OrchestratorAgent，返回回复
  GET  /api/v1/agent/health       — Agent 系统健康检查
  GET  /api/v1/agent/tools        — 列出所有已注册 MCP 工具
  GET  /api/v1/agent/tools/schema — 获取 OpenAI function calling 格式的工具描述

典型对话流程：
  前端 POST {message: "我的猫最近不吃东西"} →
  OrchestratorAgent 意图识别（health）→
  委托 HealthAgent →
  调用 analyze_pet_health + RAG 检索 →
  LLM 生成建议 →
  返回 {reply: "..."}
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent 编排（A2A）"])


# ── Schemas ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="会话 ID，不填则自动生成"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="额外上下文，如 {'pet_id': 'xxx', 'device_code': 'DEV-001'}",
    )


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    reply: str
    intent: str = Field(default="", description="识别到的意图（health/device/ticket/general）")
    agent_used: str = Field(default="", description="实际处理的 Agent 名称")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="调用的 MCP 工具列表")


class ToolInfo(BaseModel):
    """MCP 工具信息"""
    name: str
    description: str
    category: str


# ── 路由 ────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, summary="Agent 智能对话")
async def agent_chat(req: ChatRequest) -> ChatResponse:
    """
    向 OrchestratorAgent 发送消息，触发 A2A 多 Agent 编排。

    流程：
    1. OrchestratorAgent 意图识别（health/device/ticket/general）
    2. 路由到对应的子 Agent（HealthAgent/DeviceAgent/TicketAgent）
    3. 子 Agent 通过 MCP 工具调用业务服务
    4. LLM 整合工具结果，生成自然语言回答
    5. 返回最终回复和调用链路元数据
    """
    try:
        from app.agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        result = await agent.run(
            user_message=req.message,
            session_id=req.session_id,
            tenant_id=req.context.get("tenant_id", "default"),
            user_id=req.context.get("user_id", "anonymous"),
            history=req.context.get("history"),
        )
        return ChatResponse(
            session_id=req.session_id,
            reply=result.get("answer", ""),
            intent=result.get("intent", ""),
            agent_used=result.get("agent", ""),
            tool_calls=result.get("tool_calls", []),
        )
    except Exception as exc:
        logger.exception("Agent 对话失败: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent 执行失败，请稍后重试: {exc}",
        )


@router.get("/health", summary="Agent 系统健康检查")
async def agent_health() -> dict[str, Any]:
    """检查 Agent 系统和 MCP 工具注册情况。"""
    from app.mcp.registry import mcp_registry
    tools = mcp_registry.list_tools()
    categories: dict = {}
    for t in tools:
        cat = getattr(t, "category", "unknown")
        categories.setdefault(cat, []).append(t.name)
    return {
        "status": "ok",
        "total_tools": len(tools),
        "categories": categories,
    }


@router.get("/tools", response_model=list[ToolInfo], summary="列出所有 MCP 工具")
async def list_tools(category: str | None = None) -> list[ToolInfo]:
    """
    列出所有已注册的 MCP 工具。
    可通过 category 参数过滤：device / health / ticket / member / ota
    """
    from app.mcp.registry import mcp_registry
    tools = [t for t in mcp_registry.list_tools() if category is None or getattr(t, 'category', '') == category]
    return [ToolInfo(name=t.name, description=t.description, category=t.category) for t in tools]


@router.get("/tools/schema", summary="获取工具 function calling Schema")
async def get_tool_schemas(category: str | None = None) -> dict[str, Any]:
    """
    返回所有工具的 OpenAI function calling 格式 schema，供前端/外部集成使用。
    """
    from app.mcp.registry import mcp_registry
    tools = mcp_registry.list_tools()
    if category:
        tools = [t for t in tools if getattr(t, "category", "") == category]
    schemas = [t.to_function_spec() for t in tools]
    return {"total": len(schemas), "tools": schemas}
