"""NEX-29: Watch re-collect seeds then fingerprint/diff vertical slice."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexusrecon.core.entity_graph import EntityGraph, stable_entity_id
from nexusrecon.watch import (
    WATCH_MODE_RECOLLECT,
    ScopeSensor,
    Watch,
    WatchStorage,
    load_recollect_graph,
    recollect_seeds,
    resolve_watch_seeds,
    tick,
)


@pytest.mark.asyncio
async def test_recollect_seeds_builds_stable_graph():
    async def _execute(tool_name, target, target_type="domain", **kwargs):
        assert tool_name == "crtsh"
        return SimpleNamespace(
            success=True,
            source="crtsh",
            data={
                "subdomains": [
                    "api.acme.test",
                    "www.acme.test\nmail.acme.test",
                ],
            },
        )

    registry = SimpleNamespace(execute=_execute)
    graph = await recollect_seeds(
        ["acme.test"],
        campaign_id="cmp-r",
        engagement_id="eng-r",
        registry=registry,
    )
    assert graph.stable_ids is True
    api_id = stable_entity_id("subdomain", "api.acme.test")
    assert graph.get_entity(api_id) is not None
    mail_id = stable_entity_id("subdomain", "mail.acme.test")
    assert graph.get_entity(mail_id) is not None


def test_resolve_watch_seeds_unions_state_and_parent_domain():
    watch = Watch(
        watch_id="w",
        campaign_id="c",
        sensors=[
            ScopeSensor(sensor_id="s", parent_domain="extra.test"),
        ],
    )
    seeds = resolve_watch_seeds(
        watch,
        {"seeds": ["Acme.TEST", "acme.test", "other.test"]},
    )
    assert seeds == ["acme.test", "other.test", "extra.test"]


def test_recollect_tick_fires_when_collector_returns_new_host(tmp_path: Path):
    storage = WatchStorage("w-rec", root=tmp_path)
    storage.save_watch(Watch(
        watch_id="w-rec",
        campaign_id="cmp-rec",
        sensors=[ScopeSensor(
            sensor_id="subs",
            parent_domain="acme.test",
            entity_type="subdomain",
        )],
        mode=WATCH_MODE_RECOLLECT,
    ))

    hosts = {"api.acme.test"}

    def collector(seeds, watch):
        assert "acme.test" in seeds
        g = EntityGraph(
            campaign_id=watch.campaign_id,
            engagement_id="e",
            stable_ids=True,
        )
        g.add_domain("acme.test", source="scope")
        for host in sorted(hosts):
            g.add_subdomain(host, "acme.test", "crtsh", confidence=0.9)
        return g

    r1 = tick(
        "w-rec",
        watch_root=tmp_path,
        seed_collector=collector,
        now=datetime.now(UTC),
    )
    assert r1.mode == WATCH_MODE_RECOLLECT
    assert r1.sensors_evaluated == 1
    assert r1.sensors_fired == 0
    assert r1.errors == []

    hosts.add("fresh.acme.test")
    r2 = tick(
        "w-rec",
        watch_root=tmp_path,
        seed_collector=collector,
        now=datetime.now(UTC),
    )
    assert r2.sensors_fired == 1
    assert r2.actions
    assert r2.actions[0].action.severity in {"medium", "high"}


def test_recollect_identical_surface_does_not_refire(tmp_path: Path):
    storage = WatchStorage("w-stable", root=tmp_path)
    storage.save_watch(Watch(
        watch_id="w-stable",
        campaign_id="cmp-stable",
        sensors=[ScopeSensor(sensor_id="s", parent_domain="acme.test")],
        mode=WATCH_MODE_RECOLLECT,
    ))

    def collector(seeds, watch):
        g = EntityGraph(
            campaign_id=watch.campaign_id,
            engagement_id="e",
            stable_ids=True,
        )
        g.add_domain("acme.test", source="scope")
        g.add_subdomain("api.acme.test", "acme.test", "crtsh")
        return g

    r1 = tick("w-stable", watch_root=tmp_path, seed_collector=collector)
    r2 = tick("w-stable", watch_root=tmp_path, seed_collector=collector)
    assert r1.sensors_fired == 0
    assert r2.sensors_fired == 0


def test_load_recollect_graph_requires_seeds():
    watch = Watch(
        watch_id="empty",
        campaign_id="missing-campaign",
        sensors=[ScopeSensor(sensor_id="s", entity_type="domain")],
    )
    with pytest.raises(ValueError, match="no seeds"):
        load_recollect_graph(
            watch,
            campaign_state={},
            seed_collector=lambda seeds, w: None,
        )


def test_stable_entity_id_is_deterministic():
    a = stable_entity_id("domain", "Acme.TEST")
    b = stable_entity_id("domain", "acme.test")
    assert a == b
    assert a.startswith("nr-")
