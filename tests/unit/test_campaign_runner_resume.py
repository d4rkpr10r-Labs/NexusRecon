"""Regression: run_campaign skips completed phases (resume parity)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusrecon.core.campaign_runner import run_campaign


@pytest.mark.asyncio
async def test_run_campaign_skips_completed_phases():
    state = {
        "campaign_id": "nr-test",
        "completed_phases": ["phase1", "phase2"],
        "findings": [],
        "errors": [],
        "dispatch_log": [],
        "llm_cost_usd": 0.0,
    }
    campaign = MagicMock()
    campaign.audit_log = None
    campaign.cost_tracker = None
    campaign.campaign_dir = None
    scope_model = SimpleNamespace(tier_value=lambda: 0)

    skipped: list[str] = []

    def on_event(evt: dict) -> None:
        if evt.get("type") == "phase_skipped" and evt.get("reason") == "already completed":
            skipped.append(evt["phase"])

    async def _identity(s):
        return s

    with patch("nexusrecon.graph.nodes.phase1_passive_footprinting", new=AsyncMock(side_effect=_identity)) as p1, \
         patch("nexusrecon.graph.nodes.phase2_identity_cloud", new=AsyncMock(side_effect=_identity)) as p2, \
         patch("nexusrecon.graph.nodes.phase2_5_personal_identity_pivot", new=AsyncMock(side_effect=_identity)) as p25, \
         patch("nexusrecon.graph.nodes.phase3_code_leakage", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase4_correlation", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase5_light_active", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase6_active", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase7_vuln_pretext", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase7_5_harvest", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase7_7_pretext_intelligence", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase8_attack_surface", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.phase9_reporting", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.graph.nodes.reflection_node", new=AsyncMock(side_effect=_identity)), \
         patch("nexusrecon.tools.registry.get_registry") as gr:
        gr.return_value.availability_report.return_value = {
            "counts": {}, "buckets": {},
        }
        await run_campaign(state, campaign, scope_model, on_event=on_event)

    assert "phase1" in skipped and "phase2" in skipped
    p1.assert_not_awaited()
    p2.assert_not_awaited()
    p25.assert_awaited()
