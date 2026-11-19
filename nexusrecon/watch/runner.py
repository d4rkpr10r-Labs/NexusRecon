"""Watch runner — loads a watch, runs its sensors once, fires
the action policy.

Public entry points
- :func:`tick(watch_id)` — run one pass.
- :func:`list_watches()` — enumerate configured watches.

**Mode (NEX-29 / F-006):** default ``recollect`` re-runs seed
collectors (crt.sh vertical slice), materialises a stable-id
graph, then fingerprints / diffs. ``snapshot`` remains an
explicit opt-in that fingerprints frozen ``state.json`` only.

The runner deliberately does NOT loop. The operator either
calls ``tick`` from cron / systemd timer (the typical
deployment) or wraps it in a sleep loop themselves. Keeping
this synchronous + one-shot means tests can exercise the
full path without time.sleep.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from nexusrecon.watch.actions import (
    ActionResult,
    apply_action,
)
from nexusrecon.watch.severity import (
    SeverityConfig,
    classify_diff,
    diff_graphs,
)
from nexusrecon.watch.storage import (
    WATCH_MODE_RECOLLECT,
    WATCH_MODE_SNAPSHOT,
    Watch,
    WatchStorage,
    resolve_watch_dir,
)

log = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────


@dataclass
class TickResult:
    """One full tick across all sensors in a watch."""

    watch_id: str
    timestamp: str
    mode: str = WATCH_MODE_RECOLLECT
    """Effective graph source: ``recollect`` (default) or
    ``snapshot`` (frozen state.json opt-in)."""
    sensors_evaluated: int = 0
    sensors_fired: int = 0
    actions: list[ActionResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "watch_id": self.watch_id,
            "timestamp": self.timestamp,
            "mode": self.mode,
            "sensors_evaluated": self.sensors_evaluated,
            "sensors_fired": self.sensors_fired,
            "actions": [a.action.to_dict() for a in self.actions],
            "errors": list(self.errors),
        }


# ──────────────────────────────────────────────────────────────────────
# tick
# ──────────────────────────────────────────────────────────────────────


def tick(
    watch_id: str,
    *,
    watch_root: Path | str | None = None,
    graph_loader: Any | None = None,
    seed_collector: Any | None = None,
    severity_config: SeverityConfig | None = None,
    now: datetime | None = None,
) -> TickResult:
    """Run one pass of the watch's sensors.

    ``graph_loader`` is an injectable callable
    ``(campaign_id) -> EntityGraph``. When provided it short-circuits
    both recollect and snapshot loaders (tests).

    ``seed_collector`` is an injectable
    ``(seeds, watch) -> EntityGraph`` used only on the recollect
    path when ``graph_loader`` is unset.
    """
    now = now or datetime.now(UTC)
    storage = WatchStorage(watch_id, root=watch_root)
    result = TickResult(
        watch_id=watch_id,
        timestamp=now.isoformat(),
        mode=WATCH_MODE_RECOLLECT,
    )

    try:
        watch = storage.load_watch()
    except FileNotFoundError as exc:
        result.errors.append(str(exc))
        return result

    result.mode = getattr(watch, "mode", None) or WATCH_MODE_RECOLLECT

    try:
        graph = _load_graph_for_tick(
            watch,
            graph_loader=graph_loader,
            seed_collector=seed_collector,
        )
    except Exception as exc:
        result.errors.append(
            f"graph load failed for campaign "
            f"{watch.campaign_id!r}: {exc}"
        )
        storage.append_tick_log(result.errors[-1])
        return result

    for sensor in watch.sensors:
        result.sensors_evaluated += 1
        previous = storage.load_fingerprint(sensor.sensor_id)
        try:
            trigger = sensor.evaluate(graph, previous, now)
        except Exception as exc:
            result.errors.append(
                f"sensor {sensor.sensor_id!r} raised: {exc}"
            )
            storage.append_tick_log(result.errors[-1])
            continue

        # Persist the new fingerprint regardless of whether
        # the sensor fired — operators rely on the
        # fingerprint history when troubleshooting "why
        # didn't this fire?".
        storage.save_fingerprint(trigger.fingerprint)

        if not trigger.fired:
            storage.append_tick_log(
                f"sensor={sensor.sensor_id} no_fire reason={trigger.reason}"
            )
            continue

        result.sensors_fired += 1

        # Build the diff + grade severity. Timed sensors
        # don't produce a graph diff — they get a stub diff
        # that's still useful for the alert.
        diff = diff_graphs(
            trigger.changed_entity_ids,
            graph,
            previous_entity_ids=(
                previous.entity_ids if previous is not None else None
            ),
        )
        severity, reason = classify_diff(
            diff, graph, config=severity_config,
        )
        # For timed sensors with no graph diff, the
        # classifier returns LOW + "minor update". Override
        # with a clearer message.
        if trigger.sensor_kind == "timed" and not diff.added \
                and not diff.removed and not diff.in_place_changes:
            reason = f"scheduled fire — {trigger.reason}"

        full_reason = f"{trigger.reason}; {reason}"

        action_result = apply_action(
            storage,
            severity=severity, reason=full_reason,
            sensor_id=sensor.sensor_id,
            sensor_kind=trigger.sensor_kind,
            changed_entity_ids=trigger.changed_entity_ids,
            diff=diff,
            watch_id=watch_id,
            campaign_id=watch.campaign_id,
        )
        result.actions.append(action_result)
        storage.append_tick_log(
            f"sensor={sensor.sensor_id} fired severity={severity} "
            f"reason={full_reason}"
        )

    storage.append_tick_log(
        f"tick complete mode={result.mode} "
        f"evaluated={result.sensors_evaluated} "
        f"fired={result.sensors_fired}"
    )
    return result


def _load_graph_for_tick(
    watch: Watch,
    *,
    graph_loader: Any | None,
    seed_collector: Any | None,
) -> Any:
    """Select snapshot vs recollect loader for this tick."""
    if graph_loader is not None:
        return graph_loader(watch.campaign_id)

    mode = getattr(watch, "mode", None) or WATCH_MODE_RECOLLECT
    if mode == WATCH_MODE_SNAPSHOT:
        return _default_graph_loader(watch.campaign_id)

    from nexusrecon.watch.recollect import load_recollect_graph

    return load_recollect_graph(
        watch,
        seed_collector=seed_collector,
    )


# ──────────────────────────────────────────────────────────────────────
# Discovery
# ──────────────────────────────────────────────────────────────────────


def list_watches(
    watch_root: Path | str | None = None,
) -> list[Watch]:
    """Enumerate every configured watch."""
    root = resolve_watch_dir(watch_root)
    if not root.exists():
        return []
    watches: list[Watch] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "config.yaml").exists():
            continue
        storage = WatchStorage(entry.name, root=root)
        try:
            watches.append(storage.load_watch())
        except Exception as exc:
            log.warning(
                "Watch: malformed config skipped",
                watch_id=entry.name, error=str(exc),
            )
    return watches


# ──────────────────────────────────────────────────────────────────────
# Default graph loader (snapshot mode)
# ──────────────────────────────────────────────────────────────────────


def _default_graph_loader(campaign_id: str):
    """Snapshot loader — frozen ``state.json`` only.

    Used when ``Watch.mode == snapshot``. Rebuilds the EntityGraph
    with stable ids so fingerprints survive reload across ticks.
    """
    from nexusrecon.core.entity_graph import EntityGraph
    from nexusrecon.watch.recollect import load_campaign_state

    data = load_campaign_state(campaign_id)
    return EntityGraph.from_state(
        data,
        campaign_id=data.get("campaign_id", campaign_id),
        engagement_id=data.get("engagement_id", ""),
        stable_ids=True,
    )
