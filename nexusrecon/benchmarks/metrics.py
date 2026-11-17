"""Fixture-benchmark metrics for the Living Graph (NEX-20 / P4.15).

All helpers are pure / deterministic given an ``EntityGraph`` (or node
payloads) and optional planted ground truth. Timestamps and entity UUIDs
are excluded from the restart hash so two ``from_state`` rebuilds of the
same intel compare equal.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from nexusrecon.core.entity_graph import EntityGraph

# Entity types counted for discovery recall (planted assets).
_DISCOVERY_TYPES = frozenset({"subdomain", "email", "domain"})


def _iter_nodes(graph: EntityGraph | dict[str, Any]) -> Iterable[dict[str, Any]]:
    if isinstance(graph, EntityGraph):
        for _, data in graph.graph.nodes(data=True):
            if isinstance(data, dict):
                yield data
        return
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                yield node


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def discovered_values(
    graph: EntityGraph | dict[str, Any],
    *,
    types: frozenset[str] | None = None,
) -> set[str]:
    """Normalized entity values present in the graph for the given types."""
    want = types or _DISCOVERY_TYPES
    out: set[str] = set()
    for data in _iter_nodes(graph):
        etype = str(data.get("entity_type") or "")
        if etype not in want:
            continue
        val = _norm(data.get("value"))
        if val:
            out.add(val)
    return out


def discovery_recall(
    graph: EntityGraph | dict[str, Any],
    planted: Iterable[str],
    *,
    types: frozenset[str] | None = None,
) -> float:
    """``|discovered ∩ planted| / |planted|`` (0.0 when planted is empty)."""
    truth = {_norm(v) for v in planted if _norm(v)}
    if not truth:
        return 0.0
    found = discovered_values(graph, types=types)
    return len(truth & found) / len(truth)


def provenance_completeness(
    graph: EntityGraph | dict[str, Any],
    *,
    skip_types: frozenset[str] | None = None,
) -> float:
    """Fraction of entities with non-empty ``sources`` and ``provenance``.

    Reasoning artifacts (hypothesis / lead / open_question) are skipped by
    default so the gate matches STRATEGY's "entities with ≥1 real source".
    """
    skip = skip_types or frozenset({"hypothesis", "lead", "open_question"})
    total = 0
    complete = 0
    for data in _iter_nodes(graph):
        etype = str(data.get("entity_type") or "")
        if etype in skip:
            continue
        total += 1
        sources = data.get("sources") or []
        prov = data.get("provenance") or []
        if isinstance(sources, list) and any(sources) and isinstance(prov, list) and len(prov) >= 1:
            complete += 1
    if total == 0:
        return 0.0
    return complete / total


def entity_set_hash(graph: EntityGraph | dict[str, Any]) -> str:
    """SHA-256 of the canonical entity set (type, value, sources, tags).

    Excludes ``entity_id``, timestamps, confidence, and provenance
    timestamps so rebuilds of identical intel match (STRATEGY restart
    consistency gate).
    """
    items: list[dict[str, Any]] = []
    for data in _iter_nodes(graph):
        etype = str(data.get("entity_type") or "")
        value = _norm(data.get("value"))
        if not etype or not value:
            continue
        sources = sorted({str(s) for s in (data.get("sources") or []) if s})
        tags = sorted({str(t) for t in (data.get("tags") or []) if t})
        prov_sources: set[str] = set()
        for rec in data.get("provenance") or []:
            if isinstance(rec, dict):
                src = rec.get("source")
            else:
                src = getattr(rec, "source", None)
            if src:
                prov_sources.add(str(src))
        items.append({
            "entity_type": etype,
            "value": value,
            "sources": sources,
            "tags": tags,
            "provenance_sources": sorted(prov_sources),
        })
    items.sort(key=lambda row: (row["entity_type"], row["value"]))
    payload = json.dumps(items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
