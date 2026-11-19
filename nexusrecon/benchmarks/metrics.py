"""Fixture-benchmark metrics for the Living Graph (NEX-20 / NEX-31).

All helpers are pure / deterministic given an ``EntityGraph`` (or node
payloads) and optional planted ground truth. Timestamps and entity UUIDs
are excluded from the restart hash so two ``from_state`` rebuilds of the
same intel compare equal.

NEX-31 adds attribution precision (planted merge/split decisions),
wall-clock time-to-first-High-lead, and mid-campaign interrupt→hydrate
hash gates — still no live APIs.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

from nexusrecon.core.entity_graph import EntityGraph
from nexusrecon.models.entities import EntityType

# Entity types counted for discovery recall (planted assets).
_DISCOVERY_TYPES = frozenset({"subdomain", "email", "domain"})

# Ref alias: (entity_type, value)
EntityRef = tuple[str, str]


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


def _as_ref(item: Sequence[Any] | dict[str, Any]) -> EntityRef:
    """Normalize a fixture ref to ``(entity_type, value)``."""
    if isinstance(item, dict):
        return (_norm(item.get("entity_type") or item.get("type")), _norm(item.get("value")))
    if len(item) < 2:
        raise ValueError(f"entity ref needs (type, value), got {item!r}")
    return (_norm(item[0]), _norm(item[1]))


def _resolve_entity_id(graph: EntityGraph | dict[str, Any], ref: EntityRef) -> str | None:
    """Return the graph node id for ``(type, value)``, if present."""
    etype, value = ref
    if isinstance(graph, EntityGraph):
        try:
            et = EntityType(etype)
        except ValueError:
            return None
        return graph.get_entity_id(et, value)
    # Serialized graph / node list: match on normalized type+value.
    for data in _iter_nodes(graph):
        if _norm(data.get("entity_type")) == etype and _norm(data.get("value")) == value:
            eid = data.get("entity_id")
            return str(eid) if eid else None
    return None


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


def attribution_precision(
    graph: EntityGraph | dict[str, Any],
    *,
    must_merge: Iterable[Sequence[Any]] | None = None,
    must_not_merge: Iterable[Sequence[Any]] | None = None,
) -> float:
    """Fraction of planted merge/split decisions that hold on the graph.

    STRATEGY §6: plant merges/splits; measure incorrect entity merges
    (gate ≥ 0.95).

    * ``must_merge`` — each group is a sequence of ``(type, value)`` (or
      ``{entity_type, value}`` dicts) that must resolve to the **same**
      entity id (case-variant aliases, multi-source observations).
    * ``must_not_merge`` — each pair (length-2 sequence of refs) must
      resolve to **different** entity ids (near-collisions that must
      stay split).

    Missing entities count as incorrect decisions. Returns ``0.0`` when
    no decisions are planted.
    """
    correct = 0
    total = 0

    for group in must_merge or ():
        refs = [_as_ref(item) for item in group]
        if len(refs) < 2:
            continue
        total += 1
        ids = [_resolve_entity_id(graph, ref) for ref in refs]
        if all(i is not None for i in ids) and len({*ids}) == 1:
            correct += 1

    for pair in must_not_merge or ():
        if len(pair) < 2:
            continue
        left, right = _as_ref(pair[0]), _as_ref(pair[1])
        total += 1
        a = _resolve_entity_id(graph, left)
        b = _resolve_entity_id(graph, right)
        # Distinct present ids → correct split. Same id → false merge.
        # Either missing → incorrect (planted entity not discovered).
        if a is not None and b is not None and a != b:
            correct += 1

    if total == 0:
        return 0.0
    return correct / total


def high_leads(graph: EntityGraph | dict[str, Any]) -> list[dict[str, Any]]:
    """Lead nodes with severity ``high`` or ``critical`` (case-insensitive)."""
    out: list[dict[str, Any]] = []
    for data in _iter_nodes(graph):
        if str(data.get("entity_type") or "") != "lead":
            continue
        sev = _norm(data.get("severity"))
        if sev in {"high", "critical"}:
            out.append(data)
    return out


def time_to_first_high_lead(
    state: dict[str, Any],
    *,
    campaign_id: str = "",
    engagement_id: str = "",
    clock: Callable[[], float] = time.perf_counter,
    build: Callable[..., EntityGraph] | None = None,
) -> float:
    """Wall-clock seconds to materialize graph and observe ≥1 High lead.

    STRATEGY §6 time-to-useful-evidence gate for fixture campaigns (no
    live APIs). Raises ``ValueError`` if the planted state yields no
    High/critical lead after rebuild.
    """
    builder = build or EntityGraph.from_state
    t0 = clock()
    graph = builder(
        state,
        campaign_id=campaign_id or str(state.get("campaign_id") or ""),
        engagement_id=engagement_id or str(state.get("engagement_id") or ""),
    )
    elapsed = clock() - t0
    if not high_leads(graph):
        raise ValueError("fixture produced no High/critical lead")
    return elapsed


def mid_campaign_interrupt_hashes(
    interrupt_state: dict[str, Any],
    *,
    campaign_dir: Path | str | None = None,
) -> tuple[str, str]:
    """Entity-set hashes for direct rebuild vs interrupt→hydrate→rebuild.

    Simulates STRATEGY §6 restart consistency without ``run_campaign``:

    1. Hash A — ``entity_set_hash(from_state(interrupt_state))``
    2. Persist ``state.json`` (optional ``campaign_dir``), hydrate via
       ``hydrate_runner_state``, rebuild, Hash B

    Caller asserts ``A == B`` (timestamp-free entity-set match).
    """
    from nexusrecon.core.campaign_resume import hydrate_runner_state

    cid = str(interrupt_state.get("campaign_id") or "bench-interrupt")
    eid = str(interrupt_state.get("engagement_id") or "")

    g_direct = EntityGraph.from_state(
        interrupt_state, campaign_id=cid, engagement_id=eid,
    )
    hash_direct = entity_set_hash(g_direct)

    loaded = interrupt_state
    if campaign_dir is not None:
        cdir = Path(campaign_dir)
        cdir.mkdir(parents=True, exist_ok=True)
        state_path = cdir / "state.json"
        state_path.write_text(
            json.dumps(interrupt_state, sort_keys=True),
            encoding="utf-8",
        )
        loaded = json.loads(state_path.read_text(encoding="utf-8"))

    hydrated = hydrate_runner_state(loaded, campaign_id=cid)
    # hydrate_runner_state omits open_questions; re-attach so interrupt
    # fixtures with planted questions keep a stable entity-set hash.
    if "open_questions" in loaded and "open_questions" not in hydrated:
        hydrated["open_questions"] = loaded["open_questions"]

    g_resume = EntityGraph.from_state(
        hydrated,
        campaign_id=str(hydrated.get("campaign_id") or cid),
        engagement_id=str(hydrated.get("engagement_id") or eid),
    )
    hash_resume = entity_set_hash(g_resume)
    return hash_direct, hash_resume
