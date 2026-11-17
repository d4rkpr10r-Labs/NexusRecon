"""NEX-6: abort-or-warn when campaign checkpoint persistence fails."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusrecon.core.campaign_runner import run_campaign


def _patch_phases(identity):
    names = [
        "phase1_passive_footprinting",
        "phase2_identity_cloud",
        "phase2_5_personal_identity_pivot",
        "phase3_code_leakage",
        "phase4_correlation",
        "phase5_light_active",
        "phase6_active",
        "phase7_vuln_pretext",
        "phase7_5_harvest",
        "phase7_7_pretext_intelligence",
        "phase8_attack_surface",
        "phase9_reporting",
        "reflection_node",
    ]
    return [
        patch(f"nexusrecon.graph.nodes.{n}", new=AsyncMock(side_effect=identity))
        for n in names
    ]


@pytest.mark.asyncio
async def test_checkpoint_failure_warns_and_continues_by_default():
    state = {
        "campaign_id": "nr-ckpt",
        "completed_phases": [],
        "findings": [],
        "errors": [],
        "dispatch_log": [],
        "llm_cost_usd": 0.0,
        "abort_on_checkpoint_failure": False,
    }
    campaign = MagicMock()
    campaign.audit_log = None
    campaign.cost_tracker = None
    campaign.campaign_dir = None
    campaign.begin_phase = MagicMock()
    campaign.end_phase = MagicMock()
    campaign.save_state = MagicMock(side_effect=OSError("disk full"))
    scope_model = SimpleNamespace(tier_value=lambda: 0)
    events: list[dict] = []

    async def identity(s):
        return s

    patches = _patch_phases(identity)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], \
         patches[12], patch("nexusrecon.tools.registry.get_registry") as gr:
        gr.return_value.availability_report.return_value = {
            "counts": {}, "buckets": {},
        }
        result = await run_campaign(
            state, campaign, scope_model, on_event=events.append,
        )

    assert result.get("aborted") is not True
    assert any("save_state" in e for e in result.get("errors", []))
    assert any(e.get("type") == "checkpoint_failed" and e.get("abort") is False for e in events)
    # Continued past first phase despite checkpoint failure.
    assert campaign.begin_phase.call_count >= 2


@pytest.mark.asyncio
async def test_checkpoint_failure_aborts_when_flag_set():
    state = {
        "campaign_id": "nr-ckpt-abort",
        "completed_phases": [],
        "findings": [],
        "errors": [],
        "dispatch_log": [],
        "llm_cost_usd": 0.0,
        "abort_on_checkpoint_failure": True,
    }
    campaign = MagicMock()
    campaign.audit_log = None
    campaign.cost_tracker = None
    campaign.campaign_dir = None
    campaign.begin_phase = MagicMock()
    campaign.end_phase = MagicMock()
    campaign.save_state = MagicMock(side_effect=OSError("disk full"))
    scope_model = SimpleNamespace(tier_value=lambda: 0)
    events: list[dict] = []

    async def identity(s):
        return s

    patches = _patch_phases(identity)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], \
         patches[12], patch("nexusrecon.tools.registry.get_registry") as gr:
        gr.return_value.availability_report.return_value = {
            "counts": {}, "buckets": {},
        }
        result = await run_campaign(
            state, campaign, scope_model, on_event=events.append,
        )

    assert result.get("aborted") is True
    assert "checkpoint failure" in (result.get("abort_reason") or "")
    assert any(e.get("type") == "checkpoint_failed" and e.get("abort") is True for e in events)
    # Stopped after first phase's failed checkpoint — no further begin_phase.
    assert campaign.begin_phase.call_count == 1
    complete = [e for e in events if e.get("type") == "campaign_complete"]
    assert complete and complete[0].get("aborted") is True
