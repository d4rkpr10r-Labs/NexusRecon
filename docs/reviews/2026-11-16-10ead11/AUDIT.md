# AUDIT — NexusRecon Software Assurance

**Baseline commit:** `10ead117569180a0a3aa75bfa54035760271bd2e`  
**Work branch:** `cursor/assurance-review-3c7b`  
**REPAIR_MODE:** bounded-repair (no push / merge / publish)  
**Date:** 2026-11-16  
**Pre-repair scorecard:** `PRE_REPAIR_SCORECARD.md`

---

## Executive summary

Default campaign tooling, graph merge, reporting, and unit/integration suites are largely healthy (2135 unit + 518 integration passed pre-repair). Trustworthiness gaps dominate: STIX secret export leaked plaintext; registry clear left proxy bound; CLI `resume` diverged from `run_campaign`; checkpoint failures were silent; Watch cannot observe live drift; Continuous Confidence / Strategy criteria / Packs marketplace remain demoted or unwired. Bounded repairs landed for secrets, registry isolation, persistence logging, resume spine, smoke skip narrowing, and verifier packaging.

---

## Pass results

| Pass | Result | Notes |
|------|--------|-------|
| A Build/smoke | PASS | Editable install 0.7.0; smoke 6/6; wheel builds |
| B Load-bearing correctness | PARTIAL→improved | STIX leak fixed; resume uses shared runner; campaign integration mocked-pass |
| C Concurrency/resources/long runs | PARTIAL | Singleton registry; no 10k/100k bench executed; dispatch caps present |
| D Product self-security | PARTIAL→improved | Secret redaction fixed; proxy clear fixed; OPSEC dormancy residual (OPSEC_STATUS) |
| E Rot/consistency | FAIL (docs) | README stable badges vs ROADMAP demotions; MANUAL/TESTING_RUNBOOK drift |

---

## Findings

### F-001 — STIX secret plaintext leak
- **Severity:** Critical (sensitive data in export)
- **Evidence:** `_map_secret` wrote `entity["value"]` into note `content`; repro printed `LEAKED` for `AKIA1234567890SECRET`. Test only asserted abstract contains “redacted.”
- **Expected:** Secret material never appears in bundle JSON.
- **Observed:** Value in `content` and id seed.
- **Root cause:** SecretEntity.value *is* the secret; mapper treated it as a location.
- **Regression:** `TestEntityMapping.test_secret_redacted` now asserts absence from blob/content/id.
- **Fix:** Applied — digest-seeded note; no plaintext in export.
- **Residual:** In-memory graph and `state.json` still hold plaintext by design for campaign use.

### F-002 — Registry `clear_campaign_context` skips proxy
- **Severity:** High (cross-campaign OPSEC routing leak)
- **Evidence:** `self._proxy_manager = None` was dead code after `return` in `audit_log` property; clear left proxy set.
- **Fix:** Applied — clear sets `_proxy_manager = None`; regression test added.
- **Residual:** Process-global `@lru_cache` singleton still shared across campaigns in one process.

### F-003 — CLI `resume` ≠ `run_campaign`
- **Severity:** High (silent capability/OPSEC loss on resume)
- **Evidence:** `cli/main.py:resume` omitted phase2_5 / 7_5 / 7_7, reflection, registry OPSEC bind.
- **Fix:** Applied — resume reconstructs scope, binds OPSEC, calls `run_campaign`; runner skips `completed_phases`.
- **Residual:** Metadata-only scope lacks full in-scope lists if YAML missing; LangGraph `--use-graph` remains a third spine.

### F-004 — Swallowed checkpoint exceptions
- **Severity:** Medium–High (silent data loss)
- **Evidence:** `campaign_runner` `except Exception: pass` around save/begin/end phase.
- **Fix:** Applied — log + append to `state["errors"]`.
- **Residual:** Campaign still continues after checkpoint failure (does not abort).

### F-005 — Smoke dispatcher catch-all skip
- **Severity:** Medium (hidden regressions)
- **Evidence:** `tests/smoke/test_e2e_campaign.py` skipped on any Exception.
- **Fix:** Applied — soft-skip only for known env/LLM/network phrases; else re-raise.

### F-006 — Watch freshness structural limit
- **Severity:** High (product claim vs behavior)
- **Evidence:** `_default_graph_loader` rebuilds from frozen `state.json`; ROADMAP Demoted.
- **Fix:** Not in bounded-repair (design change). Documented; backlog item.
- **Residual:** CLI Watch still implies monitoring.

### F-007 — Continuous Confidence unwired
- **Severity:** Low as dormancy; Medium as marketing risk
- **Evidence:** `VerificationOrchestrator(` only in tests; README/ARCHITECTURE agree experimental.
- **Fix:** None (intentional). Align remaining ARCHITECTURE planner-bias language.

### F-008 — Strategy criteria unread / simulation $0
- **Severity:** Medium (misleading Strategy product)
- **Evidence:** ROADMAP Demoted; simulation uses unset `cost_per_run_usd`.
- **Fix:** Not applied (feature work). Backlog.

### F-009 — Verifier script absent from wheel
- **Severity:** Medium (handoff incomplete when installed)
- **Evidence:** Pre-repair wheel lacked `nexusrecon-verify.py`.
- **Fix:** Applied — `nexusrecon/assets/nexusrecon-verify.py` + package-data; unit test.
- **Residual:** First-party `packs/burp` still not in wheel (demoted packs).

### F-010 — Docs maturity overclaim
- **Severity:** Medium
- **Evidence:** Claim inventory — Strategy/Packs/Watch/Vision “stable” vs ROADMAP demotions.
- **Fix:** Not applied in code; STRATEGY + backlog call for README Status rewrite.

### F-011 — `from_state` single-source truncation
- **Severity:** Medium (blocks corroboration)
- **Evidence:** `entity_graph.from_state` takes first source only for subdomains; ROADMAP item 8.
- **Fix:** Not applied (needs careful multi-source restore). Backlog.

### F-012 — `run --resume` rebuilt empty live state
- **Severity:** High (re-runs all phases from blank intel)
- **Evidence:** Architecture lead report — `cli/main.py` built fresh `completed_phases: []` after CampaignManager load. Confirmed on branch before follow-up patch.
- **Fix:** Applied — hydrate live dict from `state.json` when `--resume` / `is_resume`.
- **Residual:** LangGraph SqliteSaver unused (F-014). F-013 fixed in NEX-12.

### F-013 — TUI Resume opens ResultsScreen only
- **Severity:** Medium (false resume UX)
- **Evidence:** `tui/screens/campaigns.py` Enter → ResultsScreen only.
- **Fix:** Applied (NEX-12) — Resume mode pushes `RunnerScreen(resume_campaign_dir=…)` for incomplete campaigns; shared `campaign_resume` hydration + `run_campaign`. DONE / browse still open Results.

### F-014 — LangGraph SqliteSaver non-functional
- **Severity:** Medium
- **Evidence:** `workflow.py` compiles checkpointer but `astream` lacks `thread_id`/config; default `:memory:`.
- **Fix:** Not applied. Backlog (prefer deprecating third spine).

### F-015 — TUI `_TOTAL_PHASES` out of sync
- **Severity:** Low
- **Evidence:** Was 10; runner has 12 phases.
- **Fix:** Applied — set to 12 with comment pointing at campaign_runner.

---

## Lead close-out (1–10)

| # | Disposition |
|---|-------------|
| 1 | OPEN (docs) — tracked F-010 |
| 2 | PARTIAL — mocked E2E passes; live success blocked without keys |
| 3 | FIXED (narrowed skip) |
| 4 | FIXED |
| 5 | FIXED (runner + CLI `resume` + `run --resume` hydrate + TUI Resume F-013); LangGraph residual F-014 |
| 6 | FIXED (log/errors; not abort) |
| 7 | FIXED (proxy clear) |
| 8 | CLOSED as intentional dormancy |
| 9 | OPEN structural — F-006 |
| 10 | PARTIAL — verifier packaged; burp pack deferred |

Architecture deep-dive (sibling): `/cursor/stores/bc-5320a189-5267-455a-b4f4-deb5bdee1a88/internal/nexusrecon-architecture-leads.md`

---

## Post-repair scorecard deltas

| Surface | Pre | Post |
|---------|-----|------|
| STIX export | BROKEN | VERIFIED (redaction) |
| Registry isolation | BROKEN | PARTIAL (proxy cleared; singleton remains) |
| CLI resume | BROKEN | PARTIAL (shared runner; scope YAML preferred) |
| Checkpoint integrity | PARTIAL | PARTIAL (visible errors; no hard fail) |
| Smoke dispatcher honesty | PARTIAL | IMPROVED |
| Wheel verifier | BROKEN | VERIFIED (asset present) |

---

## Changes made (this branch)

- `nexusrecon/export/stix.py` — secret redaction
- `nexusrecon/tools/registry.py` — clear proxy
- `nexusrecon/core/campaign_runner.py` — completed_phases skip; log checkpoint failures
- `nexusrecon/cli/main.py` — `resume` → shared runner + OPSEC bind; `run --resume` hydrates live state
- `nexusrecon/tui/screens/runner.py` — `_TOTAL_PHASES = 12`
- `nexusrecon/assets/nexusrecon-verify.py` + `pyproject.toml` package-data
- Tests: STIX, registry, resume skip, run-resume hydrate, packaged verifier, smoke skip narrowing
