"""Opt-in Continuous Confidence wire-up (NEX-13 / F-007).

Default runs stay dark: nothing constructs the orchestrator unless
``state["enable_verify"]`` is true (CLI ``--verify`` or
``NEXUS_ENABLE_VERIFY=1``).

Call sites:
  - :meth:`EntityGraph.from_state` attaches the orchestrator before
    entities are materialised so multi-source merges fire
    corroboration / contradiction / propagation.
  - Phase-boundary helpers run :class:`AdversarialSelfCheck` +
    :func:`compute_verification_health` after the graph is built.
"""
from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger(__name__)


def is_verify_enabled(state: dict[str, Any] | None) -> bool:
    """True when Continuous Confidence should run for this campaign."""
    if not state:
        return False
    return bool(state.get("enable_verify"))


def build_default_orchestrator(
    state: dict[str, Any],
    audit_log: Any | None = None,
) -> Any:
    """Construct orchestrator with the four in-tree verifiers registered.

    Registration order matches the natural flow documented in
    :class:`~nexusrecon.verification.orchestrator.VerificationOrchestrator`:
    corroboration → contradiction → propagation. Adversarial self-check
    is on-demand (phase boundary), not mutation-driven.
    """
    from nexusrecon.verification.contradictions import ContradictionDetector
    from nexusrecon.verification.corroboration import CorroborationEngine
    from nexusrecon.verification.orchestrator import VerificationOrchestrator
    from nexusrecon.verification.propagation import ConfidencePropagator

    orch = VerificationOrchestrator(state=state, audit_log=audit_log)
    orch.register(CorroborationEngine())
    orch.register(ContradictionDetector())
    orch.register(ConfidencePropagator())
    return orch


def attach_continuous_confidence(
    graph: Any,
    state: dict[str, Any],
    *,
    audit_log: Any | None = None,
) -> Any | None:
    """Attach a fully-registered orchestrator to ``graph``.

    Returns the orchestrator, or ``None`` when verify is disabled /
    attach fails (failures are non-fatal — a broken verifier must
    not take down the campaign).
    """
    if not is_verify_enabled(state):
        return None
    try:
        orch = build_default_orchestrator(state, audit_log=audit_log)
        orch.attach(graph)
        state["_verification_attached"] = True
        return orch
    except Exception as exc:
        log.warning(
            "Continuous Confidence attach failed — continuing without verify",
            error=str(exc),
        )
        state.setdefault("errors", []).append(f"verify/attach: {exc}")
        return None


def run_boundary_verification(
    graph: Any,
    state: dict[str, Any],
    *,
    audit_log: Any | None = None,
) -> None:
    """Adversarial self-check + health snapshot at a phase boundary.

    Safe to call repeatedly; weak_links / verification_health are
    replaced with the current picture (not compounded).
    """
    if not is_verify_enabled(state):
        return
    try:
        from nexusrecon.verification.adversarial import (
            AdversarialSelfCheck,
            compute_verification_health,
        )

        AdversarialSelfCheck().run(graph, state, audit_log=audit_log)
        compute_verification_health(graph, state)
    except Exception as exc:
        log.warning(
            "Continuous Confidence boundary pass failed",
            error=str(exc),
        )
        state.setdefault("errors", []).append(f"verify/boundary: {exc}")


def verify_campaign_graph(
    state: dict[str, Any],
    *,
    audit_log: Any | None = None,
) -> Any | None:
    """Rebuild/attach Continuous Confidence for a campaign state dict.

    Prefers the serialized ``state["entity_graph"]`` when present;
    otherwise builds via :meth:`EntityGraph.from_state` (which itself
    attaches when ``enable_verify`` is set). Returns the live graph
    or ``None`` on failure / when verify is off.
    """
    if not is_verify_enabled(state):
        return None
    try:
        from nexusrecon.core.entity_graph import EntityGraph

        raw = state.get("entity_graph") or {}
        if isinstance(raw, dict) and raw.get("nodes"):
            graph = EntityGraph.from_dict(raw)
            attach_continuous_confidence(graph, state, audit_log=audit_log)
            run_boundary_verification(graph, state, audit_log=audit_log)
            # Persist confidence / weak-link updates back into state.
            state["entity_graph"] = graph.to_dict()
            return graph
        graph = EntityGraph.from_state(state)
        # from_state already attached + ran boundary when enable_verify.
        return graph
    except Exception as exc:
        log.warning(
            "Continuous Confidence campaign pass failed",
            error=str(exc),
        )
        state.setdefault("errors", []).append(f"verify/campaign: {exc}")
        return None
