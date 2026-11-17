"""NEX-20 / P4.15: replayable fixture benchmarks (recall, provenance, restart)."""
from __future__ import annotations

import json
from pathlib import Path

from nexusrecon.benchmarks import (
    discovery_recall,
    entity_set_hash,
    provenance_completeness,
)
from nexusrecon.core.entity_graph import EntityGraph

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "benchmarks"
    / "planted_passive.json"
)


def _load_planted() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _planted_values(doc: dict) -> set[str]:
    gt = doc["ground_truth"]
    out: set[str] = set()
    for key in ("subdomains", "emails", "domains"):
        out.update(str(v).lower() for v in gt.get(key) or [])
    return out


def test_discovery_recall_meets_baseline():
    doc = _load_planted()
    g = EntityGraph.from_state(
        doc["state"],
        campaign_id=doc["state"]["campaign_id"],
        engagement_id=doc["state"]["engagement_id"],
    )
    recall = discovery_recall(g, _planted_values(doc))
    baseline = float(doc["meta"]["baseline_recall"])
    assert recall >= baseline
    assert recall == 1.0


def test_provenance_completeness_meets_threshold():
    doc = _load_planted()
    g = EntityGraph.from_state(
        doc["state"],
        campaign_id=doc["state"]["campaign_id"],
        engagement_id=doc["state"]["engagement_id"],
    )
    score = provenance_completeness(g)
    threshold = float(doc["meta"]["provenance_threshold"])
    assert score >= threshold
    # Round-trip through to_dict / from_dict must preserve completeness.
    g2 = EntityGraph.from_dict(g.to_dict())
    assert provenance_completeness(g2) >= threshold


def test_restart_entity_set_hash_is_stable():
    doc = _load_planted()
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
