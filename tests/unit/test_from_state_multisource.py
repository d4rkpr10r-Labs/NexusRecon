"""NEX-8: EntityGraph.from_state preserves multi-source lists."""
from __future__ import annotations

from nexusrecon.core.entity_graph import EntityGraph


def test_from_state_keeps_all_subdomain_sources():
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
    g = EntityGraph.from_state(
        state, campaign_id="c1", engagement_id="e1",
    )
    matches = [
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "api.example.test"
    ]
    assert len(matches) == 1
    sources = set(matches[0].get("sources") or [])
    assert sources == {"crtsh", "subfinder", "amass"}


def test_from_state_keeps_all_email_sources():
    state = {
        "seeds": ["example.test"],
        "subdomain_intel": {},
        "email_intel": {
            "emails": {
                "ops@example.test": {
                    "sources": ["hunter", "theharvester"],
                },
            },
        },
        "cloud_intel": {},
        "code_intel": {},
        "findings": [],
    }
    g = EntityGraph.from_state(
        state, campaign_id="c1", engagement_id="e1",
    )
    matches = [
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "ops@example.test"
    ]
    assert len(matches) == 1
    sources = set(matches[0].get("sources") or [])
    assert sources == {"hunter", "theharvester"}
