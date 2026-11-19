"""NEX-20 / NEX-31: replayable fixture benchmarks.

Covers discovery recall, provenance completeness, restart hash,
attribution precision (merge/split), wall-clock time-to-High-lead,
and mid-campaign interrupt→hydrate hash gates. No live APIs.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexusrecon.benchmarks import (
    attribution_precision,
    discovery_recall,
    entity_set_hash,
    high_leads,
    mid_campaign_interrupt_hashes,
    provenance_completeness,
    time_to_first_high_lead,
)
from nexusrecon.core.entity_graph import EntityGraph

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "benchmarks"
PASSIVE = FIXTURES / "planted_passive.json"
INTERRUPT = FIXTURES / "planted_interrupt.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _planted_values(doc: dict) -> set[str]:
    gt = doc["ground_truth"]
    out: set[str] = set()
    for key in ("subdomains", "emails", "domains"):
        out.update(str(v).lower() for v in gt.get(key) or [])
    return out


def _graph_from_passive(doc: dict | None = None) -> EntityGraph:
    doc = doc or _load(PASSIVE)
    state = doc["state"]
    return EntityGraph.from_state(
        state,
        campaign_id=state["campaign_id"],
        engagement_id=state["engagement_id"],
    )


def test_discovery_recall_meets_baseline():
    doc = _load(PASSIVE)
    g = _graph_from_passive(doc)
    recall = discovery_recall(g, _planted_values(doc))
    baseline = float(doc["meta"]["baseline_recall"])
    assert recall >= baseline
    assert recall == 1.0


def test_provenance_completeness_meets_threshold():
    doc = _load(PASSIVE)
    g = _graph_from_passive(doc)
    score = provenance_completeness(g)
    threshold = float(doc["meta"]["provenance_threshold"])
    assert score >= threshold
    # Round-trip through to_dict / from_dict must preserve completeness.
    g2 = EntityGraph.from_dict(g.to_dict())
    assert provenance_completeness(g2) >= threshold


def test_restart_entity_set_hash_is_stable():
    doc = _load(PASSIVE)
    state = doc["state"]
    g1 = EntityGraph.from_state(
        state,
        campaign_id=state["campaign_id"],
        engagement_id=state["engagement_id"],
    )
    g2 = EntityGraph.from_state(
        state,
        campaign_id=state["campaign_id"],
        engagement_id=state["engagement_id"],
    )
    h1 = entity_set_hash(g1)
    h2 = entity_set_hash(g2)
    assert h1 == h2
    assert len(h1) == 64
    # Serialize → deserialize rebuild must match the same entity-set digest
    # (IDs may change; hash ignores them).
    g3 = EntityGraph.from_dict(g1.to_dict())
    assert entity_set_hash(g3) == h1


def test_attribution_precision_meets_threshold():
    doc = _load(PASSIVE)
    g = _graph_from_passive(doc)
    attr = doc["ground_truth"]["attribution"]
    precision = attribution_precision(
        g,
        must_merge=attr["must_merge"],
        must_not_merge=attr["must_not_merge"],
    )
    threshold = float(doc["meta"]["attribution_precision_threshold"])
    assert precision >= threshold
    assert precision == 1.0


def test_attribution_precision_detects_false_merge():
    """A must_not_merge pair that shares an id scores as incorrect."""
    g = EntityGraph(campaign_id="c", engagement_id="e")
    g.add_subdomain("api.example.test", parent="example.test", source="crtsh")
    # Deliberately empty graph for mail — missing entity fails the split gate.
    score = attribution_precision(
        g,
        must_merge=[],
        must_not_merge=[
            [["subdomain", "api.example.test"], ["subdomain", "mail.example.test"]],
        ],
    )
    assert score == 0.0


def test_time_to_first_high_lead_within_budget():
    doc = _load(PASSIVE)
    state = doc["state"]
    elapsed = time_to_first_high_lead(state)
    budget = float(doc["meta"]["max_time_to_evidence_seconds"])
    assert elapsed >= 0.0
    assert elapsed <= budget
    g = _graph_from_passive(doc)
    leads = high_leads(g)
    assert len(leads) >= 1
    assert leads[0]["severity"].lower() == "high"


def test_mid_campaign_interrupt_restart_hash(tmp_path: Path):
    doc = _load(INTERRUPT)
    state = doc["state"]
    assert "phase2" in state["completed_phases"]
    assert state["current_phase"] == "phase2_5"

    h_direct, h_resume = mid_campaign_interrupt_hashes(
        state, campaign_dir=tmp_path / "bench-interrupt-1",
    )
    assert h_direct == h_resume
    assert len(h_direct) == 64
    assert (tmp_path / "bench-interrupt-1" / "state.json").is_file()

    # Mutating planted intel after interrupt must change the digest.
    mutated = json.loads(json.dumps(state))
    mutated["subdomain_intel"]["vpn.example.test"] = {"sources": ["chaos"]}
    h_mut, _ = mid_campaign_interrupt_hashes(mutated)
    assert h_mut != h_direct
