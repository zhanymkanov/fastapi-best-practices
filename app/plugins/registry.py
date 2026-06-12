"""
插件系统 — 基于 dialog（3）的 entry_points 模式

每个插件是一个 Python 包，暴露以下可选钩子：
- register_plugin(app: FastAPI) → 注册路由/中间件/事件处理器

支持两种发现方式：
1. entry_points（group="cyberlife"） — setuptools/pyproject.toml 声明
2. 显式注册 — 在 app/plugins/__init__.py 中 import
"""

import importlib
import logging
from typing import Callable

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# 插件注册函数签名
PluginRegister = Callable[[FastAPI], None]


class PluginRegistry:
    """插件注册中心"""

    def __init__(self):
        self._plugins: dict[str, PluginRegister] = {}

    def register(self, name: str, register_fn: PluginRegister) -> None:
        """显式注册一个插件"""
        if name in self._plugins:
            logger.warning("插件 %s 已存在，跳过重复注册", name)
            return
        self._plugins[name] = register_fn
        logger.info("插件已注册: %s", name)

    def discover_entry_points(self, group: str = "cyberlife") -> None:
        """从 entry_points 发现并加载插件"""
        try:
            from importlib.metadata import entry_points
        except ImportError:
            return
        try:
            eps = entry_points(group=group)
        except TypeError:
            eps = entry_points().get(group, [])

        for ep in eps:
            try:
                plugin_module = ep.load()
                register_fn = getattr(plugin_module, "register_plugin", None)
                if register_fn:
                    self.register(ep.name, register_fn)
            except Exception:
                logger.exception("加载插件 %s 失败", ep.name)

    def activate_all(self, app: FastAPI) -> None:
        """激活所有已注册插件"""
        for name, register_fn in self._plugins.items():
            try:
                register_fn(app)
                logger.info("插件已激活: %s", name)
            except Exception:
                logger.exception("插件 %s 激活失败", name)

    @property
    def plugin_names(self) -> list[str]:
        return list(self._plugins.keys())


# 全局单例
plugin_registry = PluginRegistry()
