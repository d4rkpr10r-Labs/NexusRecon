"""
LangGraph workflow builder — constructs the campaign execution graph.

Builds a StateGraph with the same phase set as ``campaign_runner.run_campaign``
and an optional in-process MemorySaver. Durable cross-process resume remains
``nexusrecon resume`` / ``state.json`` on the default runner (F-014).

``--use-graph`` is an experimental alternate engine: same phase nodes and
registry OPSEC context (bound by the CLI before invoke), not a second
product spine with its own resume story.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from nexusrecon.graph.nodes import (
    phase1_passive_footprinting,
    phase2_5_personal_identity_pivot,
    phase2_identity_cloud,
    phase3_code_leakage,
    phase4_correlation,
    phase5_light_active,
    phase6_active,
    phase7_5_harvest,
    phase7_7_pretext_intelligence,
    phase7_vuln_pretext,
    phase8_attack_surface,
    phase9_reporting,
    reflection_node,
)
from nexusrecon.graph.state import CampaignGraphState
from nexusrecon.models.campaign import CampaignMode

PHASE_ORDER: list[str] = [
    "phase1", "phase2", "phase2_5", "phase3", "phase4",
    "phase5", "phase6", "phase7", "phase7_5", "phase7_7",
    "phase8", "phase9",
]

# Minimum tier required to run each phase (F-009)
PHASE_TIERS: dict[str, int] = {
    "phase1": 0, "phase2": 0, "phase2_5": 0, "phase3": 0, "phase4": 0,
    "phase5": 2, "phase6": 3, "phase7": 0, "phase7_5": 0, "phase7_7": 0,
    "phase8": 0, "phase9": 0,
}

# Maximum tier allowed per campaign mode (F-009)
MODE_TIER_LIMITS: dict[CampaignMode, int] = {
    CampaignMode.LIGHT: 0,
    CampaignMode.MEDIUM: 2,
    CampaignMode.DEEP: 3,
    CampaignMode.MONITOR: 0,
}

PHASE_NODES = {
    "phase1": phase1_passive_footprinting,
    "phase2": phase2_identity_cloud,
    "phase2_5": phase2_5_personal_identity_pivot,
    "phase3": phase3_code_leakage,
    "phase4": phase4_correlation,
    "phase5": phase5_light_active,
    "phase6": phase6_active,
    "phase7": phase7_vuln_pretext,
    "phase7_5": phase7_5_harvest,
    "phase7_7": phase7_7_pretext_intelligence,
    "phase8": phase8_attack_surface,
    "phase9": phase9_reporting,
}


def build_campaign_workflow(
    mode: CampaignMode = CampaignMode.MEDIUM,
) -> StateGraph:
    """
    Build the LangGraph StateGraph for a NexusRecon campaign.

    Args:
        mode: Campaign mode — controls which phases are included (F-009).
    """
    tier_limit = MODE_TIER_LIMITS.get(mode, 3)
    active_phases = [p for p in PHASE_ORDER if PHASE_TIERS.get(p, 0) <= tier_limit]

    workflow = StateGraph(CampaignGraphState)

    # Add only the phase nodes allowed by this mode (F-009)
    for phase in active_phases:
        workflow.add_node(phase, PHASE_NODES[phase])
    workflow.add_node("reflect", reflection_node)

    workflow.set_entry_point(active_phases[0])

    # Routing map covers only active phases
    phase_map = {p: p for p in active_phases}
    phase_map["__end__"] = END

    # Each phase (except the last) transitions to the reflection node
    for phase in active_phases[:-1]:
        workflow.add_edge(phase, "reflect")

    # Reflection routes to the next incomplete active phase
    def _route_next(state: CampaignGraphState) -> str:
        completed = set(state.get("completed_phases", []))
        for p in active_phases:
            if p not in completed:
                return p
        return "__end__"

    workflow.add_conditional_edges("reflect", _route_next, phase_map)
    workflow.add_edge(active_phases[-1], END)

    return workflow


def _compile_app(workflow: StateGraph, *, thread_id: str):
    """Compile with in-process MemorySaver when available.

    F-014: the previous SqliteSaver path imported
    ``langgraph.checkpoint.sqlite`` (not a declared dependency) and never
    passed ``configurable.thread_id``, so the checkpointer was dead code.
    MemorySaver + thread_id is honest for a single process; durable resume
    stays on ``state.json`` / ``nexusrecon resume``.
    """
    config = {"configurable": {"thread_id": thread_id or "nexusrecon"}}
    try:
        from langgraph.checkpoint.memory import MemorySaver

        app = workflow.compile(checkpointer=MemorySaver())
        return app, config
    except Exception:
        return workflow.compile(), config


async def run_workflow(
    state: dict[str, Any],
    mode: CampaignMode = CampaignMode.MEDIUM,
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """
    Compile and run the campaign workflow with the given initial state.

    Returns the final state after all phases complete (or error).
    """
    workflow = build_campaign_workflow(mode=mode)
    tid = thread_id or str(state.get("campaign_id") or "nexusrecon")
    app, config = _compile_app(workflow, thread_id=tid)

    current = dict(state)

    async for event in app.astream(current, config):
        for node_name, node_state in event.items():
            if isinstance(node_state, dict):
                current.update(node_state)

    return current
