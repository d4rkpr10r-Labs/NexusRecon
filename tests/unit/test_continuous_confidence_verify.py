"""NEX-13: Continuous Confidence behind --verify / enable_verify."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nexusrecon.core.entity_graph import EntityGraph
from nexusrecon.verification.setup import (
    attach_continuous_confidence,
    is_verify_enabled,
    verify_campaign_graph,
)


def _multi_source_state(*, enable_verify: bool = False) -> dict[str, Any]:
    return {
        "campaign_id": "nr-verify-test",
        "engagement_id": "eng-1",
        "enable_verify": enable_verify,
        "seeds": ["acme.test"],
        "subdomain_intel": {
            # crtsh = certificate, subfinder = passive_dns → 2 classes
            "api.acme.test": {
                "sources": ["crtsh", "subfinder"],
            },
        },
        "email_intel": {"emails": {}},
        "cloud_intel": {},
        "code_intel": {},
        "findings": [],
    }


def test_is_verify_enabled():
    assert is_verify_enabled(None) is False
    assert is_verify_enabled({}) is False
    assert is_verify_enabled({"enable_verify": False}) is False
    assert is_verify_enabled({"enable_verify": True}) is True


def test_from_state_without_verify_leaves_log_empty():
    state = _multi_source_state(enable_verify=False)
    EntityGraph.from_state(state)
    assert not state.get("verification_log")
    assert not state.get("verification_health")
    assert not state.get("_verification_attached")


def test_from_state_with_verify_attaches_and_logs():
    state = _multi_source_state(enable_verify=True)
    g = EntityGraph.from_state(state)
    assert state.get("_verification_attached") is True
    # Multi-class merge should produce at least one corroboration verdict.
    log = state.get("verification_log") or []
    assert isinstance(log, list)
    assert any(e.get("verifier") == "corroboration" for e in log)
    health = state.get("verification_health") or {}
    assert health.get("entity_count", 0) >= 1
    # Graph should still contain the subdomain.
    values = {d.get("value") for _, d in g.graph.nodes(data=True)}
    assert "api.acme.test" in values


def test_attach_noop_when_disabled():
    g = EntityGraph(campaign_id="c", engagement_id="e")
    assert attach_continuous_confidence(g, {}) is None


def test_verify_campaign_graph_from_serialized():
    # Build without verify, serialize, then run verify against the dict.
    state = _multi_source_state(enable_verify=False)
    g = EntityGraph.from_state(state)
    state["entity_graph"] = g.to_dict()
    state["enable_verify"] = True
    out = verify_campaign_graph(state)
    assert out is not None
    assert state.get("verification_health")
    assert "weak_links" in state


@pytest.mark.asyncio
async def test_run_campaign_calls_verify_after_phase_with_graph():
    """campaign_runner invokes verify_campaign_graph when enable_verify."""
    from nexusrecon.core.campaign_runner import run_campaign

    state: dict[str, Any] = {
        "campaign_id": "nr-v",
        "enable_verify": True,
        "completed_phases": [],
        "findings": [],
        "errors": [],
        "dispatch_log": [],
        "llm_cost_usd": 0.0,
        "entity_graph": {"nodes": [{"id": "n1"}], "edges": []},
    }
    campaign = MagicMock()
    campaign.audit_log = None
    campaign.cost_tracker = None
    campaign.campaign_dir = None
    scope = MagicMock()
    scope.tier_value.return_value = 0

    async def _identity(s):
        s.setdefault("completed_phases", []).append(s.get("current_phase", "x"))
        # Keep a nodes payload so the verify gate fires.
        s["entity_graph"] = {"nodes": [{"id": "n1"}], "edges": []}
        return s

    called: list[bool] = []

    def _fake_verify(s, *, audit_log=None):
        called.append(True)
        return None

    with patch("nexusrecon.graph.nodes.phase1_passive_footprinting", new=_identity), \
         patch("nexusrecon.graph.nodes.phase2_identity_cloud", new=_identity), \
         patch("nexusrecon.graph.nodes.phase2_5_personal_identity_pivot", new=_identity), \
         patch("nexusrecon.graph.nodes.phase3_code_leakage", new=_identity), \
         patch("nexusrecon.graph.nodes.phase4_correlation", new=_identity), \
         patch("nexusrecon.graph.nodes.phase5_light_active", new=_identity), \
         patch("nexusrecon.graph.nodes.phase6_active", new=_identity), \
         patch("nexusrecon.graph.nodes.phase7_vuln_pretext", new=_identity), \
         patch("nexusrecon.graph.nodes.phase7_5_harvest", new=_identity), \
         patch("nexusrecon.graph.nodes.phase7_7_pretext_intelligence", new=_identity), \
         patch("nexusrecon.graph.nodes.phase8_attack_surface", new=_identity), \
         patch("nexusrecon.graph.nodes.phase9_reporting", new=_identity), \
         patch("nexusrecon.graph.nodes.reflection_node", new=_identity), \
         patch("nexusrecon.tools.registry.get_registry") as gr, \
         patch(
             "nexusrecon.verification.setup.verify_campaign_graph",
             side_effect=_fake_verify,
         ):
        gr.return_value.availability_report.return_value = {
            "counts": {}, "buckets": {},
        }
        # Mark all but phase1 complete so we only run one phase quickly.
        state["completed_phases"] = [
            "phase2", "phase2_5", "phase3", "phase4", "phase5", "phase6",
            "phase7", "phase7_5", "phase7_7", "phase8", "phase9",
        ]
        await run_campaign(state, campaign, scope)

    assert called, "verify_campaign_graph should run after a phase with entity_graph"
