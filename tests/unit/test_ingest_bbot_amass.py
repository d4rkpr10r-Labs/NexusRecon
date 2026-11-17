"""NEX-21 / P4.16: BBOT + Amass graph ingest adapters."""
from __future__ import annotations

from pathlib import Path

import pytest

from nexusrecon.core.entity_graph import EntityGraph
from nexusrecon.ingest import AmassImporter, BBOTImporter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"


@pytest.fixture
def graph() -> EntityGraph:
    return EntityGraph(campaign_id="cmp-ingest", engagement_id="eng-ingest")


def test_amass_importer_maps_hosts_ips_and_edges(graph: EntityGraph):
    path = FIXTURES / "amass_enum.jsonl"
    report = AmassImporter().import_file(path, graph)
    assert report.entities_added >= 3
    assert report.relationships_added >= 1
    values = {
        d.get("value") for _, d in graph.graph.nodes(data=True)
    }
    assert "www.example.test" in values
    assert "api.example.test" in values
    assert "203.0.113.10" in values
    www = next(
        d for _, d in graph.graph.nodes(data=True)
        if d.get("value") == "www.example.test"
    )
    assert "imported_from:amass" in (www.get("sources") or [])
    assert any(
        (p.get("source") if isinstance(p, dict) else None) == "imported_from:amass"
        for p in (www.get("provenance") or [])
    )
    # Secondary Amass collector provenance
    assert any(
        str(s).startswith("amass:") for s in (www.get("sources") or [])
    )


def test_amass_skips_malformed_lines(graph: EntityGraph):
    body = (
        '{"name": "ok.example.test", "addresses": []}\n'
        "NOT JSON\n"
        '{"name": "", "addresses": []}\n'
    )
    report = AmassImporter().import_text(body, graph)
    assert report.skipped >= 1
    assert report.warnings
    assert any(
        d.get("value") == "ok.example.test"
        for _, d in graph.graph.nodes(data=True)
    )


def test_bbot_importer_maps_dns_and_ips(graph: EntityGraph):
    path = FIXTURES / "bbot_events.ndjson"
    report = BBOTImporter().import_file(path, graph)
    assert report.entities_added >= 3
    # OPEN_TCP_PORT skipped
    assert report.skipped >= 1
    values = {
        d.get("value") for _, d in graph.graph.nodes(data=True)
    }
    assert "www.example.test" in values
    assert "api.example.test" in values
    assert "203.0.113.10" in values
    www = next(
        d for _, d in graph.graph.nodes(data=True)
        if d.get("value") == "www.example.test"
    )
    assert "imported_from:bbot" in (www.get("sources") or [])
    assert any(
        str(s).startswith("bbot:") for s in (www.get("sources") or [])
    )
    # RESOLVES_TO present
    edge_types = {
        str(data.get("rel_type") or data.get("relationship_type") or "")
        for _, _, data in graph.graph.edges(data=True)
    }
    assert "resolves_to" in edge_types


def test_bbot_file_missing_warns(graph: EntityGraph, tmp_path: Path):
    report = BBOTImporter().import_file(tmp_path / "missing.ndjson", graph)
    assert report.entities_added == 0
    assert report.warnings
