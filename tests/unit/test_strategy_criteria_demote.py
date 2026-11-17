"""NEX-15 / F-008: unread Strategy criteria demoted from planner prompts."""
from __future__ import annotations

from nexusrecon.strategy.plan import KillCriterion, Strategy, SuccessCriterion
from nexusrecon.strategy.planner import _build_planner_prompt, _coerce_to_strategy


def test_planner_prompt_omits_criteria_schema():
    prompt = _build_planner_prompt(
        scope_summary="acme.test",
        seeds=["acme.test"],
        mode="medium",
        dispatch_policy_name="lite",
        max_llm_cost_usd=10.0,
    )
    assert "Do NOT author `success_criteria`" in prompt
    assert "not enforced" in prompt
    assert '"success_criteria"' not in prompt
    assert '"kill_criteria"' not in prompt
    # Real control plane still documented.
    assert "dispatch_policy_name" in prompt
    assert "vision_calls" in prompt


def test_coerce_marks_legacy_criteria_advisory():
    strategy = _coerce_to_strategy(
        {
            "name": "legacy",
            "phases": ["phase1"],
            "dispatch_policy_name": "lite",
            "success_criteria": [
                {"metric": "findings", "op": ">=", "threshold": 1},
            ],
            "kill_criteria": [
                {
                    "metric": "llm_cost_usd",
                    "op": ">",
                    "threshold": 5,
                    "action": "abort",
                },
            ],
        },
        fallback_dispatch_policy_name="lite",
        operator_metadata={},
    )
    assert len(strategy.success_criteria) == 1
    assert len(strategy.kill_criteria) == 1
    assert strategy.metadata.get("criteria_enforced") is False
    assert strategy.metadata.get("criteria_status") == "advisory"


def test_coerce_without_criteria_skips_advisory_flag():
    strategy = _coerce_to_strategy(
        {
            "name": "clean",
            "phases": ["phase1", "phase2"],
            "dispatch_policy_name": "lite",
            "tool_budgets": {"vision_calls": 2},
        },
        fallback_dispatch_policy_name="lite",
        operator_metadata={},
    )
    assert strategy.success_criteria == []
    assert strategy.kill_criteria == []
    assert "criteria_enforced" not in strategy.metadata
    assert strategy.tool_budgets == {"vision_calls": 2}


def test_strategy_dataclass_still_holds_criteria():
    s = Strategy(
        success_criteria=[
            SuccessCriterion(metric="findings", op=">=", threshold=3),
        ],
        kill_criteria=[
            KillCriterion(metric="errors", op=">", threshold=10),
        ],
    )
    d = s.to_dict()
    assert d["success_criteria"][0]["metric"] == "findings"
    assert d["kill_criteria"][0]["metric"] == "errors"
