"""Shared resume hydration for CLI ``resume`` and TUI Resume (F-013).

Loads ``state.json`` + scope metadata from an on-disk campaign directory and
reconstructs a ``ScopeModel`` + hydrated runner state so callers can continue
incomplete phases via :func:`nexusrecon.core.campaign_runner.run_campaign`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexusrecon.core.campaign import CampaignManager
from nexusrecon.models.campaign import CampaignMode
from nexusrecon.models.scope import ScopeModel


class ResumeError(Exception):
    """Campaign directory cannot be resumed."""


@dataclass(frozen=True)
class ResumeContext:
    """Everything needed to continue a campaign through ``run_campaign``."""

    campaign_id: str
    campaign_dir: Path
    state_path: Path
    state_data: dict[str, Any]
    scope_model: ScopeModel
    campaign_mode: CampaignMode

    @property
    def completed_phases(self) -> list[str]:
        return list(self.state_data.get("completed_phases") or [])

    @property
    def current_phase(self) -> str:
        return str(self.state_data.get("current_phase") or "phase1")


def find_campaign_dir(campaign_id: str, output_dir: Path) -> Path | None:
    """Locate a campaign directory under ``output_dir`` by id."""
    if not output_dir.exists():
        return None
    for campaign_dir in output_dir.rglob(campaign_id):
        if campaign_dir.is_dir() and (campaign_dir / "state.json").exists():
            return campaign_dir
    return None


def _load_scope_meta(campaign_dir: Path) -> dict[str, Any]:
    meta_path = campaign_dir / "scope_metadata.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_scope_model(
    campaign_dir: Path,
    state_data: dict[str, Any],
    scope_meta: dict[str, Any] | None = None,
) -> ScopeModel:
    """Rebuild a ScopeModel for resume — prefer YAML, then metadata."""
    meta = scope_meta if scope_meta is not None else _load_scope_meta(campaign_dir)

    # Prefer the preserved copy written by the TUI / CLI run path.
    for candidate in (
        campaign_dir / "scope.yaml",
        Path(meta.get("scope_file_path") or ""),
    ):
        if candidate and candidate.is_file():
            try:
                return ScopeModel.from_yaml(candidate)
            except Exception:
                pass

    engagement = dict(meta.get("engagement") or {})
    engagement.setdefault("client", "unknown")
    engagement.setdefault(
        "engagement_id", state_data.get("engagement_id") or "unknown",
    )
    engagement.setdefault("authorized_by", "resume")
    engagement.setdefault("authorization_date", "1970-01-01")
    engagement.setdefault("start_date", "1970-01-01")
    engagement.setdefault("end_date", "2099-01-01")
    engagement.setdefault("signed_sow_hash", "sha256:" + ("0" * 64))
    try:
        scope_model = ScopeModel.model_validate({
            "engagement": engagement,
            "constraints": meta.get("constraints") or {},
        })
    except Exception as exc:
        raise ResumeError(f"Cannot reconstruct scope for resume: {exc}") from exc
    scope_model.scope_hash = (
        meta.get("scope_hash") or state_data.get("scope_hash") or ""
    )
    return scope_model


def hydrate_runner_state(
    state_data: dict[str, Any],
    *,
    campaign_id: str,
) -> dict[str, Any]:
    """Build the dict passed to ``run_campaign`` from persisted state.json."""
    completed = list(state_data.get("completed_phases") or [])
    return {
        "campaign_id": state_data.get("campaign_id", campaign_id),
        "engagement_id": state_data.get("engagement_id", ""),
        "scope_hash": state_data.get("scope_hash", ""),
        "seeds": state_data.get("seeds", []),
        "completed_phases": completed,
        "current_phase": state_data.get("current_phase", "phase1"),
        "findings": state_data.get("findings", []),
        "subdomain_intel": state_data.get("subdomain_intel", {}),
        "email_intel": state_data.get("email_intel", {"emails": {}}),
        "cloud_intel": state_data.get("cloud_intel", {}),
        "code_intel": state_data.get("code_intel", {}),
        "infra_intel": state_data.get("infra_intel", {}),
        "domain_intel": state_data.get("domain_intel", {}),
        "vuln_intel": state_data.get("vuln_intel", {}),
        "pretext_intel": state_data.get("pretext_intel", {}),
        "entity_graph": state_data.get("entity_graph", {}),
        "hypotheses": state_data.get("hypotheses", []),
        "confirmed_leads": state_data.get("confirmed_leads", []),
        "validate_credentials": state_data.get("validate_credentials", False),
        "generate_phishing_drafts": state_data.get(
            "generate_phishing_drafts", False,
        ),
        "llm_cost_usd": state_data.get("llm_cost_usd", 0.0),
        "max_llm_cost_usd": state_data.get("max_llm_cost_usd", 10.0),
        "tool_cost_usd": state_data.get("tool_cost_usd", 0.0),
        "step_count": state_data.get("step_count", 0),
        "errors": state_data.get("errors", []),
        "agent_messages": state_data.get("agent_messages", []),
        "report_paths": {},
        "dispatch_mode": state_data.get("dispatch_mode", "lite"),
        "strategy": state_data.get("strategy"),
        "dispatch_policy_name": state_data.get("dispatch_policy_name"),
        "mode": state_data.get("mode"),
        "enable_verify": bool(state_data.get("enable_verify", False)),
    }


def load_resume_context(campaign_dir: Path | str) -> ResumeContext:
    """Load resume context from an existing campaign directory."""
    cdir = Path(campaign_dir)
    state_path = cdir / "state.json"
    if not state_path.is_file():
        raise ResumeError(f"No state.json in {cdir}")
    try:
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ResumeError(f"Cannot read state.json: {exc}") from exc

    campaign_id = str(state_data.get("campaign_id") or cdir.name)
    scope_model = resolve_scope_model(cdir, state_data)
    mode_raw = str(state_data.get("mode") or "medium").lower()
    try:
        campaign_mode = CampaignMode(mode_raw)
    except ValueError:
        campaign_mode = CampaignMode.MEDIUM

    return ResumeContext(
        campaign_id=campaign_id,
        campaign_dir=cdir,
        state_path=state_path,
        state_data=state_data,
        scope_model=scope_model,
        campaign_mode=campaign_mode,
    )


def prepare_resume_campaign(ctx: ResumeContext) -> CampaignManager:
    """Create a CampaignManager pointed at the existing on-disk directory."""
    campaign = CampaignManager(
        scope=ctx.scope_model,
        mode=ctx.campaign_mode,
        campaign_id=ctx.campaign_id,
    )
    # Point at the discovered path rather than the reconstructed client/
    # engagement layout (which may not match after metadata-only resume).
    campaign.campaign_dir = ctx.campaign_dir
    campaign.report_dir = ctx.campaign_dir / "reports"
    campaign.artifacts_dir = ctx.campaign_dir / "artifacts"
    campaign.logs_dir = ctx.campaign_dir / "logs"
    campaign.setup()
    return campaign
