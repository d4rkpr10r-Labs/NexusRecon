"""Watch re-collect vertical slice (NEX-29 / F-006).

Default Watch ticks re-run a small set of seed collectors, materialise
an EntityGraph from the fresh results, then fingerprint / diff as
usual. This is the path that can observe live attack-surface drift.

Scope of the slice
- Seeds come from the campaign ``state.json`` ``seeds`` list plus any
  ``ScopeSensor.parent_domain`` values on the watch.
- Collectors default to ``crtsh`` only (no binary deps). Operators /
  tests can inject a broader tool list or a fake collector.
- Does **not** rewrite the campaign checkpoint; the recollected graph
  lives only for the tick.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# Vertical-slice default: Certificate Transparency only. No local
# binary required; enough to surface new subdomain names between ticks.
RECOLLECT_SEED_TOOLS: tuple[str, ...] = ("crtsh",)

SeedCollector = Callable[..., Any]


def find_campaign_state_path(campaign_id: str) -> Path:
    """Locate ``state.json`` for ``campaign_id`` under the output dir."""
    from nexusrecon.core.config import get_config

    output_dir = Path(get_config().output_dir)
    for candidate in output_dir.rglob(campaign_id):
        if candidate.is_dir():
            state_path = candidate / "state.json"
            if state_path.exists():
                return state_path
    raise FileNotFoundError(
        f"campaign {campaign_id!r} state.json not found"
    )


def load_campaign_state(campaign_id: str) -> dict[str, Any]:
    """Load the frozen campaign checkpoint dict."""
    path = find_campaign_state_path(campaign_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            f"campaign {campaign_id!r} state.json is not an object"
        )
    return data


def resolve_watch_seeds(watch: Any, state: dict[str, Any] | None) -> list[str]:
    """Union of campaign seeds and ScopeSensor parent domains."""
    seeds: list[str] = []
    seen: set[str] = set()

    def _add(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        value = raw.strip().lower()
        if not value or value in seen:
            return
        seen.add(value)
        seeds.append(value)

    if state:
        for seed in state.get("seeds") or []:
            _add(seed)

    for sensor in getattr(watch, "sensors", None) or []:
        _add(getattr(sensor, "parent_domain", None))

    return seeds


def _normalize_subdomain(raw: Any) -> list[str]:
    """Flatten crt.sh-style name_value blobs into individual hostnames."""
    if isinstance(raw, dict):
        raw = raw.get("subdomain") or raw.get("name_value") or raw.get("value")
    if not isinstance(raw, str):
        return []
    out: list[str] = []
    for part in raw.replace(",", "\n").splitlines():
        host = part.strip().lower().lstrip("*.")
        if host and "." in host:
            out.append(host)
    return out


async def recollect_seeds(
    seeds: Sequence[str],
    *,
    campaign_id: str,
    engagement_id: str = "",
    tools: Sequence[str] = RECOLLECT_SEED_TOOLS,
    registry: Any | None = None,
) -> Any:
    """Run seed collectors and build a stable-id EntityGraph."""
    from nexusrecon.core.entity_graph import EntityGraph
    from nexusrecon.tools.registry import get_registry

    registry = registry or get_registry()
    subdomain_intel: dict[str, dict[str, Any]] = {}

    for seed in seeds:
        for tool_name in tools:
            try:
                result = await registry.execute(tool_name, seed, "domain")
            except Exception as exc:
                log.warning(
                    "Watch recollect: tool raised",
                    tool=tool_name, seed=seed, error=str(exc),
                )
                continue
            if result is None or not getattr(result, "success", False):
                continue
            data = getattr(result, "data", None) or {}
            source = getattr(result, "source", None) or tool_name
            for sub in data.get("subdomains", []) if isinstance(data, dict) else []:
                for host in _normalize_subdomain(sub):
                    entry = subdomain_intel.setdefault(host, {"sources": []})
                    if source not in entry["sources"]:
                        entry["sources"].append(source)

    return EntityGraph.from_state(
        {
            "campaign_id": campaign_id,
            "engagement_id": engagement_id,
            "seeds": list(seeds),
            "subdomain_intel": subdomain_intel,
        },
        campaign_id=campaign_id,
        engagement_id=engagement_id,
        stable_ids=True,
    )


def load_recollect_graph(
    watch: Any,
    *,
    campaign_state: dict[str, Any] | None = None,
    seed_collector: SeedCollector | None = None,
    tools: Sequence[str] = RECOLLECT_SEED_TOOLS,
) -> Any:
    """Resolve seeds and return a recollected EntityGraph for one tick.

    ``seed_collector`` is an injectable ``(seeds, watch) -> EntityGraph``
    for unit tests. Production leaves it ``None`` and runs the async
    collectors via :func:`asyncio.run`.
    """
    state = campaign_state
    if state is None:
        try:
            state = load_campaign_state(watch.campaign_id)
        except FileNotFoundError:
            # Sensors alone may still supply parent_domain seeds.
            state = None

    seeds = resolve_watch_seeds(watch, state)
    if not seeds:
        raise ValueError(
            f"watch {watch.watch_id!r} has no seeds to recollect "
            f"(campaign seeds + ScopeSensor parent_domain are empty)"
        )

    if seed_collector is not None:
        return seed_collector(seeds, watch)

    engagement_id = ""
    if isinstance(state, dict):
        engagement_id = str(state.get("engagement_id") or "")

    return asyncio.run(
        recollect_seeds(
            seeds,
            campaign_id=watch.campaign_id,
            engagement_id=engagement_id,
            tools=tools,
        ),
    )
