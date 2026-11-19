# ADR-0001: Defer external graph index (NetworkX + `state.json`)

- **Status:** Accepted
- **Date:** 2026-11-19
- **Tracker:** NEX-32 (graph-gap plan PR5)
- **Deciders:** Living Graph consultation / d4rkpr10r-Labs

## Context

NexusRecon’s living intelligence graph (`EntityGraph` / `LivingGraph` in
`nexusrecon/core/entity_graph.py`) is an in-process **NetworkX** `DiGraph`.
Campaign persistence writes the full live execution dict (including
`state["entity_graph"]` from `EntityGraph.to_dict()`) to
`<campaign_dir>/state.json` via `CampaignManager.save_state`.

That design is intentional for engagement-scale campaigns:

- One file is the checkpoint for `resume`, Watch snapshot-diff loaders, reports,
  and STIX export.
- Round-trip is schema-simple (`to_dict` / `from_dict` / `from_state`).
- No second store to keep consistent with the audit chain.

Competitive systems (Amass asset-db, reNgine Postgres, SpiderFoot SQLite) use a
queryable historical store. NexusRecon does **not** today: multi-campaign merge,
historical query, and cross-run access boundaries remain weak by design
(see consultation strategy §3).

### Observed limits of NetworkX + full `state.json`

| Concern | Why it bites |
|---------|----------------|
| Memory | Whole graph resident; peeks and path queries walk the in-process digraph. |
| Checkpoint I/O | Every phase boundary can rewrite the **entire** JSON blob (`indent=2`, `default=str`). Cost grows with nodes + edges + provenance lists. |
| Resume / Watch load | Rebuild is `from_dict` / `from_state` over the full document — O(N) parse + index rebuild (`_value_index`). |
| Export | STIX / pyvis / reports walk the same materialized graph; export wall time tracks entity count. |
| Concurrency | One campaign process owns the graph; no shared indexed store across workers. |

**Soft operating envelope** (inspection + strategy targets — **not** yet measured
at 100k in-repo):

| Scale | Expectation |
|-------|-------------|
| ~1k entities | Interactive laptop campaigns stay comfortable. |
| ~10k entities | Overnight / large engagement on a laptop; serialize + export dominate. |
| ~100k entities | External index / shard strategy required; current store is insufficient. |

`ARCHITECTURE.md` §13 already marks a graph-database backend as out of scope
while NetworkX covers sizes operators see. This ADR makes the deferral criterion
explicit and measurable.

## Decision

**Defer any external graph index or sidecar store** (SQLite, Postgres, Neo4j,
Amass-style asset-db, or similar) until campaigns **measure** entity scale that
justifies it.

1. **Keep** NetworkX + `state.json` as the sole default knowledge store.
2. **Do not** land an experimental SQLite/index stub in-tree while the need is
   speculative (no measured breach of the envelope below).
3. **Revisit** when measured `total_entities` on real or fixture campaigns
   regularly approaches **10 000**, or when operators need historical /
   multi-campaign query that `state.json` cannot provide.
4. **Out of scope forever for this ADR:** packs marketplace, fleet learning, and
   any “graph product” surface that assumes a shared indexed store.

### Metrics hook (already shipped — use it)

No new telemetry subsystem. Revisit is gated on numbers already available:

| Surface | What to read |
|---------|----------------|
| `EntityGraph.stats()` | `total_entities`, `total_relationships`, `by_type` |
| `state["entity_graph"]["stats"]` | Same payload embedded on each `to_dict()` serialize |
| `CampaignManager.finalize()` return value | `"graph"` key is that stats dict |

**Revisit trigger (primary):** sustained `total_entities >= 10_000` on default-path
campaigns (or fixture benchmarks that model that size), **or** repeated operator
pain from checkpoint/export wall time at lower counts with evidence attached to
an issue.

**Secondary triggers:** need for cross-campaign entity query; need for partial
load without hydrating full `state.json`; multi-writer campaigns.

When triggered, a follow-up ADR must choose among (non-exhaustive): thin SQLite
value/edge index beside NetworkX, replace checkpoint with a DB-backed graph, or
shard `state.json` — labeled experimental until benchmarks pass the matrix in
strategy §6.

## Consequences

### Positive

- Avoids premature schema dual-write and migration debt.
- Keeps the persistence contract one-file and reviewable.
- Forces scale claims to ride on `stats()` / benchmarks, not aspiration.

### Negative / accepted risk

- Large engagements may hit serialize and memory cliffs before an index exists.
- Historical and multi-campaign questions stay file-grep / reload territory.
- Watch and resume remain full-document loaders.

### Explicit non-actions

- No optional SQLite spike in this change.
- No milestone or marketplace work tied to “graph store productization.”

## References

- `nexusrecon/core/entity_graph.py` — NetworkX backing, `to_dict` / `stats`
- `nexusrecon/core/campaign.py` — `save_state` → `state.json`, `finalize` graph summary
- `ARCHITECTURE.md` §13 — Living Intelligence Graph; graph DB out of scope
- Consultation strategy: soft envelope 1k / 10k / 100k; “document when exceeded”
