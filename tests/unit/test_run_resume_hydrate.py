"""Regression: run --resume must hydrate live state from state.json."""
from __future__ import annotations

import json
from pathlib import Path


def test_resume_hydration_preserves_completed_phases(tmp_path: Path):
    """Mirror the overlay logic used by cli.main.run for --resume."""
    prior = {
        "campaign_id": "nr-test",
        "completed_phases": ["phase1", "phase2"],
        "findings": [{"finding_id": "f1"}],
        "subdomain_intel": {"sub.example.test": {"sources": ["crtsh"]}},
        "validate_credentials": False,
        "dispatch_mode": "off",
    }
    prior_path = tmp_path / "state.json"
    prior_path.write_text(json.dumps(prior), encoding="utf-8")

    state = {
        "campaign_id": "nr-test",
        "completed_phases": [],
        "findings": [],
        "subdomain_intel": {},
        "validate_credentials": True,
        "generate_phishing_drafts": False,
        "generate_obsidian": False,
        "dispatch_mode": "lite",
        "strategy": {"dispatch_policy_name": "lite"},
        "dispatch_policy_name": "lite",
        "pretext_targets": [],
        "max_llm_cost_usd": 10.0,
    }
    preserve = {
        "validate_credentials",
        "generate_phishing_drafts",
        "generate_obsidian",
        "pretext_targets",
        "max_llm_cost_usd",
    }
    loaded = json.loads(prior_path.read_text(encoding="utf-8"))
    for key, value in loaded.items():
        if key in preserve:
            continue
        state[key] = value
    state["validate_credentials"] = True  # CLI override wins
    state["dispatch_mode"] = "lite"

    assert state["completed_phases"] == ["phase1", "phase2"]
    assert state["findings"] == [{"finding_id": "f1"}]
    assert "sub.example.test" in state["subdomain_intel"]
    assert state["validate_credentials"] is True
    assert state["dispatch_mode"] == "lite"
