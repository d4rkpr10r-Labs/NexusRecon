"""NEX-19 / P4.14: ProvenanceRecord writers on the default path."""
from __future__ import annotations

from nexusrecon.core.entity_graph import EntityGraph
from nexusrecon.models.entities import DomainEntity
from nexusrecon.reports.engine import ReportEngine


def test_add_helpers_stamp_provenance_records():
    g = EntityGraph(campaign_id="c1", engagement_id="e1")
    sid = g.add_subdomain("api.example.test", parent="example.test", source="crtsh")
    data = g.graph.nodes[sid]
    assert "crtsh" in (data.get("sources") or [])
    prov = data.get("provenance") or []
    assert len(prov) >= 1
    assert prov[0]["source"] == "crtsh"


def test_merge_unions_provenance_across_sources():
    g = EntityGraph(campaign_id="c1", engagement_id="e1")
    a = DomainEntity(value="example.test")
    a.add_provenance("crtsh", evidence_hash="sha256:a")
    b = DomainEntity(value="example.test")
    b.add_provenance("whois", evidence_hash="sha256:b")
    id_a = g.add_entity(a)
    id_b = g.add_entity(b)
    assert id_a == id_b
    data = g.graph.nodes[id_a]
    sources = set(data.get("sources") or [])
    assert sources == {"crtsh", "whois"}
    prov_sources = {p["source"] for p in (data.get("provenance") or [])}
    assert prov_sources == {"crtsh", "whois"}


def test_from_state_writes_provenance_for_each_source():
    state = {
        "seeds": ["example.test"],
        "subdomain_intel": {
            "api.example.test": {
                "sources": ["crtsh", "subfinder", "amass"],
            },
        },
        "email_intel": {"emails": {}},
        "cloud_intel": {},
        "code_intel": {},
        "findings": [],
    }
    g = EntityGraph.from_state(state, campaign_id="c1", engagement_id="e1")
    matches = [
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "api.example.test"
    ]
    assert len(matches) == 1
    prov = matches[0].get("provenance") or []
    assert len(prov) >= 3
    assert {p["source"] for p in prov} == {"crtsh", "subfinder", "amass"}
    # Completeness: every legacy source has ≥1 provenance record.
    sources = set(matches[0].get("sources") or [])
    assert sources
    assert len(prov) >= len(sources)


def test_from_state_reads_singular_email_source():
    """Phase2 writers use singular ``source``; must not fall back to phase2."""
    state = {
        "seeds": ["example.test"],
        "subdomain_intel": {},
        "email_intel": {
            "emails": {
                "ops@example.test": {"source": "hunter"},
            },
        },
        "cloud_intel": {},
        "code_intel": {},
        "findings": [],
    }
    g = EntityGraph.from_state(state, campaign_id="c1", engagement_id="e1")
    matches = [
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "ops@example.test"
    ]
    assert len(matches) == 1
    assert "hunter" in (matches[0].get("sources") or [])
    prov = matches[0].get("provenance") or []
    assert any(p.get("source") == "hunter" for p in prov)


def test_full_report_surfaces_entity_provenance(tmp_path):
    state = {
        "seeds": ["example.test"],
        "subdomain_intel": {
            "api.example.test": {"sources": ["crtsh", "subfinder"]},
        },
        "email_intel": {"emails": {}},
        "cloud_intel": {},
        "code_intel": {},
        "findings": [],
        "completed_phases": ["phase1", "phase4"],
        "errors": [],
        "llm_cost_usd": 0.0,
        "tool_cost_usd": 0.0,
    }
    g = EntityGraph.from_state(state, campaign_id="c1", engagement_id="e1")
    state["entity_graph"] = g.to_dict()
    engine = ReportEngine(
        campaign_id="c1",
        engagement_id="e1",
        scope_hash="deadbeef",
        output_dir=tmp_path,
    )
    section = engine._entity_provenance_section(state)
    text = "\n".join(section)
    assert "Entity provenance" in text
    assert "api.example.test" in text
    assert "crtsh" in text
