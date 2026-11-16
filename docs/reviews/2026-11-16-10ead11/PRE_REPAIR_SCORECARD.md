# Pre-repair works-as-advertised scorecard

**Preserved before production repairs.** Commit baseline `10ead11`.  
Branch `cursor/assurance-review-3c7b`. Date 2026-11-16.

Scoring: VERIFIED / PARTIAL / UNSUBSTANTIATED / BROKEN / NOT APPLICABLE  
Operational state: default path | explicitly enabled | standalone | partially integrated | stubbed | planned only

| Claim / surface | Operational state | Score | Notes |
|-----------------|-------------------|-------|-------|
| Default campaign run (phases + reports) | default path | PARTIAL | Integration tests pass with mocks; live keys often absent |
| Living graph entities/edges | default path | VERIFIED | Unit + integration; provenance writers incomplete |
| Dynamic dispatch / reflection | default path | PARTIAL | Real loop; MockLLM often empty plan; smoke catch-all skip |
| Strategy criteria / budgets / kill | partially integrated | BROKEN | Authored, never enforced (ROADMAP) |
| Cost simulation abort | partially integrated | BROKEN | Often $0.00; no abort |
| Continuous Confidence on run | stubbed | UNSUBSTANTIATED | Unit-only orchestrator |
| Watch continuous monitoring | standalone | BROKEN | Diffs frozen state.json |
| Micro-campaign auto-exec | intentional limit | NOT APPLICABLE | Queue-only by design |
| Packs marketplace | partially integrated | UNSUBSTANTIATED | Empty URL; burp not in wheel |
| Vision autonomous loop | standalone | UNSUBSTANTIATED | Budget 0; hand artifacts |
| STIX export | default/export | BROKEN | Secret value leaks in note content |
| Ed25519 sign path | explicitly enabled | PARTIAL | Code present; verify script not in wheel |
| CLI resume ≡ run_campaign | partially integrated | BROKEN | Missing phases / OPSEC / reflection |
| Registry campaign isolation | default path | BROKEN | clear leaves proxy_manager |
| campaign_runner checkpoint integrity | default path | PARTIAL | save_state failures swallowed |
| OPSEC proxy/rate on campaigns | partially integrated | PARTIAL | Bind optional; many tools bypass (OPSEC_STATUS) |
| Fleet learning | planned only | NOT APPLICABLE | Design only |
| Wheel ≈ editable checkout | packaging | BROKEN | verify script + burp pack omitted |

## Lead disposition (pre-repair)

| # | Lead | Status |
|---|------|--------|
| 1 | Docs vs runtime maturity | OPEN — README overclaims vs ROADMAP |
| 2 | Campaign data flow beyond fixture | PARTIAL — mocked integration passes; not a full live success path |
| 3 | Smoke dispatcher catch-all skip | OPEN — masks real errors |
| 4 | STIX `_map_secret` | CONFIRMED DEFECT — value in content |
| 5 | Resume parity | CONFIRMED DEFECT |
| 6 | Persistence swallowed exceptions | CONFIRMED DEFECT |
| 7 | Registry context isolation | CONFIRMED DEFECT — proxy not cleared |
| 8 | Verification lifecycle | INTENTIONAL DORMANT — not wired |
| 9 | Watch freshness | CONFIRMED STRUCTURAL LIMIT |
| 10 | Wheel / STIX interchange | CONFIRMED DEFECT — packaging gap |

## Baseline test commands (pre-repair)

```
python3 -m pytest tests/unit/ -q          # 2135 passed, 13 skipped
python3 -m pytest tests/integration/ -q   # 518 passed, 1 skipped
python3 -m pytest tests/smoke/ -q         # 6 passed
```
