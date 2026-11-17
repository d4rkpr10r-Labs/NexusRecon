"""Watch Mode — Phase 5 PR A (honesty: snapshot-diff).

As shipped (NEX-14 / F-006), each ``tick`` rebuilds the campaign
graph from frozen ``state.json`` and fingerprints that snapshot.
It is **not** live continuous monitoring: digests only change
after a new campaign run rewrites the checkpoint. A future
``recollect`` mode may re-run seed collectors before
fingerprinting; that path is not implemented yet.

What works today
- **Sensors** (``watch/sensors.py``) define WHAT to watch on
  the snapshot graph:
    * :class:`EntitySensor` — single entity by id.
    * :class:`ScopeSensor` — entities matching a scope
      filter (e.g. "all subdomains of acme.com").
    * :class:`TimedSensor` — fires on a polling schedule
      regardless of graph state (still against the snapshot).
- **Diff + severity** (``watch/severity.py``) compute what
  changed since the last tick and grade it.
- **Actions** (``watch/actions.py``) decide what to do with
  graded changes — append an alert, send a notification,
  or queue a micro-campaign.
- **Storage** (``watch/storage.py``) persists watch configs +
  fingerprints + alert history under
  ``~/.nexusrecon/watch/<watch-id>/``.
- **Runner** (``watch/runner.py``) ties everything together.
  ``tick(watch_id)`` runs one pass.

Sensor activation modes
- Diff-driven: fingerprint the watched entities; trigger when
  the fingerprint changes (vs the previous tick's digest of
  the same frozen checkpoint lineage).
- Polling: TimedSensor fires on a cadence regardless of graph
  state (still no live re-collection).

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
"""
from nexusrecon.watch.actions import (
    Action,
    ActionResult,
    apply_action,
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
    "resolve_watch_dir",
    "tick",
]
