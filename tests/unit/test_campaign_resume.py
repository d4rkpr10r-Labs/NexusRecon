"""Unit tests for shared campaign resume hydration (F-013 / NEX-12)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexusrecon.core.campaign_resume import (
    ResumeError,
    find_campaign_dir,
    hydrate_runner_state,
    load_resume_context,
    resolve_scope_model,
)
from nexusrecon.tui.screens.campaigns import CampaignsScreen


def _write_campaign(tmp: Path, *, completed: list[str] | None = None) -> Path:
    cdir = tmp / "client" / "eng-1" / "nr-resume-test"
    cdir.mkdir(parents=True)
    state = {
        "campaign_id": "nr-resume-test",
        "engagement_id": "eng-1",
        "scope_hash": "abc123",
        "seeds": ["example.com"],
        "completed_phases": completed or ["phase1", "phase2"],
        "current_phase": "phase2_5",
        "findings": [{"finding_id": "f1"}],
        "dispatch_mode": "full",
        "mode": "medium",
        "llm_cost_usd": 1.25,
    }
    (cdir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (cdir / "scope_metadata.json").write_text(
        json.dumps({
            "engagement": {
                "client": "Acme",
                "engagement_id": "eng-1",
                "authorized_by": "tester",
                "authorization_date": "2026-01-01",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "signed_sow_hash": "sha256:" + ("a" * 64),
            },
            "constraints": {"max_tier": "T1"},
            "scope_hash": "abc123",
        }),
        encoding="utf-8",
    )
    return cdir


def test_find_campaign_dir(tmp_path: Path):
    cdir = _write_campaign(tmp_path)
    assert find_campaign_dir("nr-resume-test", tmp_path) == cdir
    assert find_campaign_dir("missing", tmp_path) is None


def test_load_resume_context_from_metadata(tmp_path: Path):
    cdir = _write_campaign(tmp_path)
    ctx = load_resume_context(cdir)
    assert ctx.campaign_id == "nr-resume-test"
    assert ctx.completed_phases == ["phase1", "phase2"]
    assert ctx.current_phase == "phase2_5"
    assert ctx.scope_model.engagement.client == "Acme"
    assert ctx.campaign_mode.value == "medium"


def test_hydrate_preserves_completed_and_findings(tmp_path: Path):
    cdir = _write_campaign(tmp_path)
    ctx = load_resume_context(cdir)
    state = hydrate_runner_state(ctx.state_data, campaign_id=ctx.campaign_id)
    assert state["completed_phases"] == ["phase1", "phase2"]
    assert state["findings"] == [{"finding_id": "f1"}]
    assert state["dispatch_mode"] == "full"
    assert state["llm_cost_usd"] == 1.25
    assert state["report_paths"] == {}


def test_load_resume_missing_state(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ResumeError):
        load_resume_context(empty)


def test_resolve_scope_prefers_campaign_scope_yaml(tmp_path: Path):
    cdir = _write_campaign(tmp_path)
    sow = "sha256:" + ("b" * 64)
    (cdir / "scope.yaml").write_text(
        "\n".join([
            "engagement:",
            "  client: FromYaml",
            "  engagement_id: eng-yaml",
            "  authorized_by: tester",
            "  authorization_date: '2026-01-01'",
            "  start_date: '2026-01-01'",
            "  end_date: '2026-12-31'",
            f"  signed_sow_hash: '{sow}'",
            "constraints:",
            "  max_tier: T0",
            "scope:",
            "  in_scope:",
            "    domains: [yaml.example.com]",
        ]),
        encoding="utf-8",
    )
    scope = resolve_scope_model(
        cdir, {"engagement_id": "eng-1", "scope_hash": "x"},
    )
    assert scope.engagement.client == "FromYaml"


@pytest.mark.parametrize(
    ("resume_mode", "status", "expected"),
    [
        (True, "PARTIAL", True),
        (True, "RUNNING", True),
        (True, "DONE", False),
        (False, "PARTIAL", False),
        (False, "DONE", False),
    ],
)
def test_should_resume_via_runner(resume_mode: bool, status: str, expected: bool):
    assert CampaignsScreen.should_resume_via_runner(resume_mode, status) is expected


@pytest.mark.asyncio
async def test_open_campaign_resume_pushes_runner(tmp_path: Path):
    """Resume mode + incomplete → RunnerScreen with resume_campaign_dir."""
    from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

    fake_app = MagicMock()
    fake_app.push_screen = AsyncMock()
    screen = CampaignsScreen(resume_mode=True)
    camp = {
        "campaign_dir": str(tmp_path / "nr-x"),
        "status": "PARTIAL",
        "state": {
            "mode": "deep",
            "dispatch_mode": "lite",
            "validate_credentials": False,
            "generate_phishing_drafts": False,
        },
    }
    with patch.object(type(screen), "app", PropertyMock(return_value=fake_app)):
        await screen._open_campaign(camp)
    fake_app.push_screen.assert_awaited_once()
    runner = fake_app.push_screen.await_args.args[0]
    assert runner.__class__.__name__ == "RunnerScreen"
    assert getattr(runner, "resume_campaign_dir") == str(tmp_path / "nr-x")
    assert getattr(runner, "mode") == "deep"


@pytest.mark.asyncio
async def test_open_campaign_browse_pushes_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

    class _FakeResults:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    import nexusrecon.tui.screens.results as results_mod
    monkeypatch.setattr(results_mod, "ResultsScreen", _FakeResults)

    fake_app = MagicMock()
    fake_app.push_screen = AsyncMock()
    screen = CampaignsScreen(resume_mode=False)
    camp = {
        "campaign_dir": str(tmp_path / "nr-y"),
        "status": "PARTIAL",
        "state": {"findings": []},
    }
    with patch.object(type(screen), "app", PropertyMock(return_value=fake_app)):
        await screen._open_campaign(camp)
    fake_app.push_screen.assert_awaited_once()
    results = fake_app.push_screen.await_args.args[0]
    assert results.__class__.__name__ == "_FakeResults"
    assert results.kwargs["campaign_dir"] == str(tmp_path / "nr-y")
