"""Replayable fixture benchmarks (NEX-20 / NEX-31).

Synthetic planted-state metrics for defending architecture bets without
live APIs: discovery recall, provenance completeness, timestamp-free
entity-set restart hash, attribution precision (merge/split), wall-clock
time-to-first-High-lead, and mid-campaign interrupt→hydrate hash gates.
"""
from nexusrecon.benchmarks.metrics import (
    attribution_precision,
    discovery_recall,
    entity_set_hash,
    high_leads,
    mid_campaign_interrupt_hashes,
    provenance_completeness,
    time_to_first_high_lead,
)

__all__ = [
    "attribution_precision",
    "discovery_recall",
    "entity_set_hash",
    "high_leads",
    "mid_campaign_interrupt_hashes",
    "provenance_completeness",
    "time_to_first_high_lead",
]
