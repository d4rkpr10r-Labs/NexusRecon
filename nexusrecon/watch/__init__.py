"""Watch Mode — Phase 5 PR A (NEX-29 re-collect default).

Default ``tick`` re-collects campaign seeds (crt.sh vertical slice),
builds a stable-id EntityGraph, then fingerprints / diffs. Snapshot
diff of frozen ``state.json`` remains available as an explicit
``mode=snapshot`` opt-in.

What works today
- **Sensors** (``watch/sensors.py``) define WHAT to watch:
    * :class:`EntitySensor` — single entity by id.
    * :class:`ScopeSensor` — entities matching a scope
      filter (e.g. "all subdomains of acme.com").
    * :class:`TimedSensor` — fires on a polling schedule
      regardless of graph state.
- **Diff + severity** (``watch/severity.py``) compute what
  changed since the last tick and grade it.
- **Actions** (``watch/actions.py``) decide what to do with
  graded changes — append an alert, send a notification,
  or queue a micro-campaign.
- **Storage** (``watch/storage.py``) persists watch configs +
  fingerprints + alert history under
  ``~/.nexusrecon/watch/<watch-id>/``.
- **Recollect** (``watch/recollect.py``) re-runs seed collectors
  before fingerprinting (default path).
- **Runner** (``watch/runner.py``) ties everything together.
  ``tick(watch_id)`` runs one pass.

Sensor activation modes
- Diff-driven: fingerprint the watched entities; trigger when
  the fingerprint changes vs the previous tick.
- Polling: TimedSensor fires on a cadence regardless of graph
  state (recollect mode still refreshes the underlying graph).

Action policy (locked in: "tiered")
- ``low`` severity → alert (append to ``alerts.jsonl``).
- ``medium`` severity → alert + notification (a
  notification file the operator can tail or pipe).
- ``high`` severity → alert + notification + queue a
  micro-campaign that targets the changed entity.

What's NOT in PR A
- Signed receipts (deferred per the architecture choice —
  PR B candidate).
- Multi-modal reasoning (Phase 5 follow-up).
- Live notification channels (Slack / email / webhook).
  v1 writes a ``notifications.jsonl`` the operator's
  external tooling tails.
- Full phase-1 re-run (amass/subfinder/etc.); the vertical
  slice uses crt.sh unless a broader tool list is injected.
"""
from nexusrecon.watch.actions import (
    Action,
    ActionResult,
    apply_action,
)
from nexusrecon.watch.recollect import (
    RECOLLECT_SEED_TOOLS,
    load_campaign_state,
    load_recollect_graph,
    recollect_seeds,
    resolve_watch_seeds,
)
from nexusrecon.watch.runner import (
    TickResult,
    list_watches,
    tick,
)
from nexusrecon.watch.sensors import (
    EntitySensor,
    ScopeSensor,
    Sensor,
    SensorFingerprint,
    TimedSensor,
)
from nexusrecon.watch.severity import (
    GraphDiff,
    Severity,
    classify_diff,
    diff_graphs,
)
from nexusrecon.watch.storage import (
    SUPPORTED_WATCH_MODES,
    WATCH_MODE_RECOLLECT,
    WATCH_MODE_SNAPSHOT,
    Watch,
    WatchAlert,
    WatchStorage,
    resolve_watch_dir,
)

__all__ = [
    "Action",
    "ActionResult",
    "EntitySensor",
    "GraphDiff",
    "RECOLLECT_SEED_TOOLS",
    "SUPPORTED_WATCH_MODES",
    "ScopeSensor",
    "Sensor",
    "SensorFingerprint",
    "Severity",
    "TickResult",
    "TimedSensor",
    "WATCH_MODE_RECOLLECT",
    "WATCH_MODE_SNAPSHOT",
    "Watch",
    "WatchAlert",
    "WatchStorage",
    "apply_action",
    "classify_diff",
    "diff_graphs",
    "list_watches",
    "load_campaign_state",
    "load_recollect_graph",
    "recollect_seeds",
    "resolve_watch_dir",
    "resolve_watch_seeds",
    "tick",
]
