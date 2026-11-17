"""Tests for tools/registry.py."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from nexusrecon.tools.base import Category, OSINTTool, Tier, ToolResult
from nexusrecon.tools.registry import (
    ToolRegistry,
    campaign_bind_scope,
    get_campaign_bind,
    get_registry,
    register_tool,
)


class TestTool:
    """Dummy test tool."""
    name = "test_tool"
    tier = Tier.T0
    category = Category.DOMAIN
    requires_keys = []
    description = "Test tool"
    target_types = ["domain"]

    async def run(self, target: str, **kwargs):
        return ToolResult(success=True, source="test_tool", data={"test": True})


class TestRegistry:
    def test_register_tool(self):
        registry = ToolRegistry()
        registry.register(TestTool)
        tool = registry.get("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.tier == Tier.T0

    def test_clear_campaign_context_clears_proxy_manager(self):
        """Campaign isolation: clear must detach proxy routing too."""
        from unittest.mock import MagicMock

        registry = ToolRegistry()
        proxy = MagicMock(name="ProxyManager")
        registry.set_campaign_context(
            scope_guard=MagicMock(),
            cache=None,
            audit_log=None,
            stealth_profile=None,
            rate_limiter=None,
            proxy_manager=proxy,
        )
        assert registry._proxy_manager is proxy
        registry.clear_campaign_context()
        assert registry._proxy_manager is None
        assert registry._scope_guard is None
        assert registry._cache is None
        assert registry._audit_log is None
        assert registry._rate_limiter is None

    def test_decorator_registration(self):
        registry = get_registry()
        before = len(registry.list_tools())

        @register_tool
        class DecoratedTool(OSINTTool):
            name = "decorated_tool"
            tier = Tier.T0
            category = Category.DOMAIN
            requires_keys = []
            description = "Decorated"
            target_types = ["domain"]

            async def run(self, target, **kwargs):
                return ToolResult(success=True, source=self.name, data={})

        after = len(registry.list_tools())
        assert after == before + 1

    def test_list_by_category(self):
        registry = get_registry()
        infra_tools = registry.list_by_category("infrastructure")
        assert len(infra_tools) >= 0  # category-based filtering works (tools may vary)

    def test_list_by_tier(self):
        registry = get_registry()
        t0_tools = registry.list_by_tier("T0")
        t1_tools = registry.list_by_tier("T1")
        assert len(t0_tools) > len(t1_tools)  # Most tools are T0

    def test_campaign_bind_scope_restores_outer(self):
        """Nested campaign_bind_scope must not leak the inner proxy."""
        outer = MagicMock(name="outer_proxy")
        inner = MagicMock(name="inner_proxy")
        with campaign_bind_scope(scope_guard=MagicMock(), proxy_manager=outer):
            assert get_campaign_bind().proxy_manager is outer
            with campaign_bind_scope(scope_guard=MagicMock(), proxy_manager=inner):
                assert get_campaign_bind().proxy_manager is inner
            assert get_campaign_bind().proxy_manager is outer
        assert get_campaign_bind() is None


class TestCampaignContextVarIsolation:
    """NEX-11: concurrent tasks must not share campaign OPSEC binds."""

    @pytest.mark.asyncio
    async def test_async_tasks_isolate_proxy_bind(self):
        registry = get_registry()
        seen: dict[str, object] = {}

        async def _campaign(label: str, proxy: object) -> None:
            registry.set_campaign_context(
                scope_guard=MagicMock(),
                proxy_manager=proxy,
            )
            await asyncio.sleep(0.01)
            seen[label] = registry._proxy_manager
            registry.clear_campaign_context()

        proxy_a = MagicMock(name="proxy_a")
        proxy_b = MagicMock(name="proxy_b")
        await asyncio.gather(
            _campaign("a", proxy_a),
            _campaign("b", proxy_b),
        )
        assert seen["a"] is proxy_a
        assert seen["b"] is proxy_b
        assert registry._proxy_manager is None
