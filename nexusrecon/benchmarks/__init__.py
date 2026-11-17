"""Replayable fixture benchmarks (NEX-20 / P4.15).

Synthetic planted-state metrics for defending architecture bets without
live APIs: discovery recall, provenance completeness, and a timestamp-free
entity-set restart hash over ``EntityGraph.from_state``.
"""
from nexusrecon.benchmarks.metrics import (
    discovery_recall,
    entity_set_hash,
    provenance_completeness,
)

__all__ = [
    "discovery_recall",
    "entity_set_hash",
    "provenance_completeness",
]
