"""
AI 模型配置 — QMI平台 AI 全局配置

从 cyberlife.toml 加载 prompt 模板、模型参数、MCP 工具、Agent 编排等配置
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python 3.9-3.10


class AIConfig:
    """AI 模型全局配置（懒加载单例）"""

    _instance: "AIConfig | None" = None
    _config: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        config_path = Path(__file__).parent.parent.parent / "cyberlife.toml"
        try:
            with open(config_path, "rb") as f:
                self._config = tomllib.load(f)
        except FileNotFoundError:
            self._config = {}

    # ── LLM 模型参数 ─────────────────────────────────
    @property
    def model_name(self) -> str:
        return self._config.get("model", {}).get("model_name", "gpt-4o-mini")

    @property
    def temperature(self) -> float:
        return self._config.get("model", {}).get("temperature", 0.3)

    @property
    def max_tokens(self) -> int:
        return self._config.get("model", {}).get("max_tokens", 2048)

    # ── Embedding / bge-m3 ───────────────────────────
    @property
    def embedding_model(self) -> str:
        return self._config.get("embedding", {}).get("model", "bge-m3")

    @property
    def embedding_dimensions(self) -> int:
        return self._config.get("embedding", {}).get("dimensions", 1024)

    @property
    def embedding_batch_size(self) -> int:
        return self._config.get("embedding", {}).get("batch_size", 32)

    # ── Prompts ──────────────────────────────────────
    def get_prompt(self, scenario: str) -> dict[str, str]:
        """获取指定场景的 prompt 模板"""
        return self._config.get("prompts", {}).get(scenario, {})

    @property
    def pet_analysis_prompt(self) -> dict[str, str]:
        return self.get_prompt("pet_analysis")

    @property
    def pet_naming_prompt(self) -> dict[str, str]:
        return self.get_prompt("pet_naming")

    @property
    def health_advice_prompt(self) -> dict[str, str]:
        return self.get_prompt("health_advice")

    @property
    def asset_tagging_prompt(self) -> dict[str, str]:
        return self.get_prompt("asset_tagging")

    # ── 健康 Agent Prompt ─────────────────────────────
    @property
    def health_agent_system(self) -> str:
        return self._config.get("agents", {}).get(
            "health_system",
            "你是宠物健康分析 Agent，负责综合 RAG 知识库和 IoT 设备数据给出专业健康分析。",
        )

    @property
    def device_agent_system(self) -> str:
        return self._config.get("agents", {}).get(
            "device_system",
            "你是设备运维 Agent，负责 IoT 设备状态监控、故障诊断和 OTA 升级任务调度。",
        )

    @property
    def ticket_agent_system(self) -> str:
        return self._config.get("agents", {}).get(
            "ticket_system",
            "你是客服工单 Agent，负责自动分类工单、匹配知识库回答、升级人工处理。",
        )

    @property
    def orchestrator_system(self) -> str:
        return self._config.get("agents", {}).get(
            "orchestrator_system",
            "你是宠物生态平台总编排 Agent，负责分析用户任务，动态路由到合适的子 Agent。",
        )

    # ── Endpoints（多模型路由） ────────────────────────
    @property
    def endpoints(self) -> list[dict[str, str]]:
        return self._config.get("endpoint", [])

    @property
    def raw_config(self) -> dict[str, Any]:
        """暴露原始配置"""
        return self._config


# 全局单例
ai_config = AIConfig()
