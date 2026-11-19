"""NEX-19 / NEX-28: ProvenanceRecord writers + audit evidence_hash join."""
from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

import pytest

from nexusrecon.core.audit import AuditLog
from nexusrecon.core.entity_graph import EntityGraph
from nexusrecon.models.entities import DomainEntity
from nexusrecon.reports.engine import ReportEngine
from nexusrecon.tools.base import Category, OSINTTool, Tier, ToolResult
from nexusrecon.tools.registry import ToolRegistry


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


def test_add_helper_forwards_evidence_hash():
    g = EntityGraph(campaign_id="c1", engagement_id="e1")
    sid = g.add_subdomain(
        "api.example.test",
        parent="example.test",
        source="crtsh",
        evidence_hash="sha256:deadbeef",
        tool_name="CrtshTool",
    )
    prov = g.graph.nodes[sid].get("provenance") or []
    assert len(prov) >= 1
    assert prov[0]["evidence_hash"] == "sha256:deadbeef"
    assert prov[0]["tool_name"] == "CrtshTool"


def test_from_state_joins_evidence_hashes_from_intel():
    """Default Living Graph path: intel evidence_hashes → ProvenanceRecord."""
    state = {
        "seeds": ["example.test"],
        "subdomain_intel": {
            "api.example.test": {
                "sources": ["crtsh", "subfinder"],
                "evidence_hashes": {
                    "crtsh": "sha256:aaa",
                    "subfinder": "sha256:bbb",
                },
            },
        },
        "email_intel": {
            "emails": {
                "ops@example.test": {
                    "source": "hunter",
                    "evidence_hash": "sha256:ccc",
                },
            },
        },
        "cloud_intel": {},
        "code_intel": {},
        "findings": [],
    }
    g = EntityGraph.from_state(state, campaign_id="c1", engagement_id="e1")

    sub = next(
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "api.example.test"
    )
    by_source = {p["source"]: p.get("evidence_hash") for p in (sub.get("provenance") or [])}
    assert by_source["crtsh"] == "sha256:aaa"
    assert by_source["subfinder"] == "sha256:bbb"

    email = next(
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "ops@example.test"
    )
    email_prov = email.get("provenance") or []
    assert any(
        p.get("source") == "hunter" and p.get("evidence_hash") == "sha256:ccc"
        for p in email_prov
    )


@pytest.mark.asyncio
async def test_registry_response_hash_matches_audit_and_graph(tmp_path):
    """Smoke: when audit exists, graph evidence_hash equals audit response_hash."""

    class _HashTool(OSINTTool):
        name = "hash_join_tool"
        tier = Tier.T0
        category = Category.DOMAIN
        requires_keys: list[str] = []
        description = "fixture"
        target_types = ["domain"]

        async def run(self, target: str, **kwargs: object) -> ToolResult:
            return ToolResult(
                success=True,
                source=self.name,
                data={"subdomains": [f"api.{target}"]},
                result_count=1,
            )

    audit = AuditLog(
        log_path=tmp_path / "audit.jsonl",
        campaign_id="c1",
        scope_hash="deadbeef",
    )
    registry = ToolRegistry()
    registry.register(_HashTool)
    registry.set_campaign_context(
        scope_guard=None,
        cache=None,
        audit_log=audit,
        stealth_profile=None,
        rate_limiter=None,
        proxy_manager=None,
    )

    result = await registry.execute("hash_join_tool", "example.test", "domain")
    assert result.success
    assert result.response_hash
    assert result.response_hash.startswith("sha256:")
    expected = "sha256:" + hashlib.sha256(
        json.dumps(result.data, default=str).encode(),
    ).hexdigest()
    assert result.response_hash == expected

    # Audit log carries the same hash on the tool_result entry.
    entries = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text().splitlines()
        if line.strip()
    ]
    tool_results = [e for e in entries if e.get("event_type") == "tool_result"]
    assert tool_results
    assert tool_results[-1]["response_hash"] == result.response_hash

    # Simulate phase1 intel write + from_state join.
    subdomain_intel = {
        "api.example.test": {
            "sources": [result.source],
            "evidence_hashes": {result.source: result.response_hash},
        },
    }
    g = EntityGraph.from_state(
        {
            "seeds": ["example.test"],
            "subdomain_intel": subdomain_intel,
            "email_intel": {"emails": {}},
            "cloud_intel": {},
            "code_intel": {},
            "findings": [],
        },
        campaign_id="c1",
        engagement_id="e1",
    )
    node = next(
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "api.example.test"
    )
    prov = node.get("provenance") or []
    assert any(
        p.get("source") == result.source
        and p.get("evidence_hash") == result.response_hash
        for p in prov
    )


@pytest.mark.asyncio
async def test_phase1_stores_evidence_hashes_from_tool_result(monkeypatch):
    """phase1_passive_footprinting copies ToolResult.response_hash into intel."""
    from nexusrecon.graph import nodes as nodes_mod

    crtsh_hash = "sha256:" + "a" * 64

    async def _execute(tool_name, target, target_type="domain", **kwargs):
        if tool_name == "crtsh":
            return ToolResult(
                success=True,
                source="crtsh",
                data={"subdomains": [f"www.{target}"]},
                result_count=1,
                response_hash=crtsh_hash,
            )
        return ToolResult(success=False, source=tool_name, error="skip")

    mock_registry = MagicMock()
    mock_registry.execute = _execute
    monkeypatch.setattr(nodes_mod, "get_registry", lambda: mock_registry)

    async def _run_agent(*_a, **_k):
        return {"output": ""}

    monkeypatch.setattr(
        nodes_mod,
        "_get_executor",
        lambda: MagicMock(run_agent=_run_agent),
    )

    state = await nodes_mod.phase1_passive_footprinting({
        "seeds": ["example.test"],
        "completed_phases": [],
        "agent_messages": [],
    })

    intel = state["subdomain_intel"]["www.example.test"]
    assert "crtsh" in intel["sources"]
    assert intel["evidence_hashes"]["crtsh"] == crtsh_hash

    g = EntityGraph.from_state(
        {
            "seeds": ["example.test"],
            "subdomain_intel": state["subdomain_intel"],
            "email_intel": {"emails": {}},
            "cloud_intel": {},
            "code_intel": {},
            "findings": [],
        },
        campaign_id="c1",
        engagement_id="e1",
    )
    node = next(
        data for _, data in g.graph.nodes(data=True)
        if data.get("value") == "www.example.test"
    )
    assert any(
        p.get("source") == "crtsh" and p.get("evidence_hash") == crtsh_hash
        for p in (node.get("provenance") or [])
    )
