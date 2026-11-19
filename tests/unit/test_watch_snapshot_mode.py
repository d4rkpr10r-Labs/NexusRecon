"""NEX-29 / F-006: snapshot mode remains explicit opt-in."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from nexusrecon.core.entity_graph import EntityGraph
from nexusrecon.watch import (
    SUPPORTED_WATCH_MODES,
    WATCH_MODE_RECOLLECT,
    WATCH_MODE_SNAPSHOT,
    ScopeSensor,
    Watch,
    WatchStorage,
    tick,
)


def test_supported_modes_include_recollect_and_snapshot():
    assert WATCH_MODE_SNAPSHOT in SUPPORTED_WATCH_MODES
    assert WATCH_MODE_RECOLLECT in SUPPORTED_WATCH_MODES


def test_watch_defaults_to_recollect_and_round_trips(tmp_path: Path):
    storage = WatchStorage("w1", root=tmp_path)
    watch = Watch(
        watch_id="w1",
        campaign_id="nr-1",
        sensors=[ScopeSensor(sensor_id="w1.scope", parent_domain="acme.test")],
    )
    assert watch.mode == WATCH_MODE_RECOLLECT
    storage.save_watch(watch)
    loaded = storage.load_watch()
    assert loaded.mode == WATCH_MODE_RECOLLECT
    assert loaded.to_dict()["mode"] == WATCH_MODE_RECOLLECT


def test_explicit_snapshot_mode_round_trips(tmp_path: Path):
    storage = WatchStorage("w-snap", root=tmp_path)
    watch = Watch(
        watch_id="w-snap",
        campaign_id="nr-snap",
        sensors=[ScopeSensor(sensor_id="s", parent_domain="acme.test")],
        mode=WATCH_MODE_SNAPSHOT,
    )
    storage.save_watch(watch)
    loaded = storage.load_watch()
    assert loaded.mode == WATCH_MODE_SNAPSHOT


def test_unknown_mode_falls_back_to_recollect(tmp_path: Path):
    storage = WatchStorage("w2", root=tmp_path)
    watch = Watch(
        watch_id="w2",
        campaign_id="nr-2",
        sensors=[ScopeSensor(sensor_id="w2.scope", parent_domain="acme.test")],
        mode=WATCH_MODE_RECOLLECT,
    )
    storage.save_watch(watch)
    raw = storage.config_path.read_text(encoding="utf-8")
    storage.config_path.write_text(
        raw.replace("mode: recollect", "mode: future-mode"),
        encoding="utf-8",
    )
    loaded = storage.load_watch()
    assert loaded.mode == WATCH_MODE_RECOLLECT


def test_tick_result_exposes_snapshot_mode(tmp_path: Path):
    storage = WatchStorage("w3", root=tmp_path)
    storage.save_watch(Watch(
        watch_id="w3",
        campaign_id="nr-3",
        sensors=[ScopeSensor(sensor_id="w3.scope", parent_domain="acme.test")],
        mode=WATCH_MODE_SNAPSHOT,
    ))

    g = EntityGraph(campaign_id="nr-3", engagement_id="e", stable_ids=True)
    g.add_domain("acme.test", source="scope")
    g.add_subdomain("api.acme.test", "acme.test", "crtsh")

    result = tick(
        "w3",
        watch_root=tmp_path,
        graph_loader=lambda _cid: g,
        now=datetime.now(UTC),
    )
    assert result.mode == WATCH_MODE_SNAPSHOT
    assert result.to_dict()["mode"] == WATCH_MODE_SNAPSHOT
    assert result.errors == []
