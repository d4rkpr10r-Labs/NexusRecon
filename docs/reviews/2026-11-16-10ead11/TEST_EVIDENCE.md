# TEST_EVIDENCE — NexusRecon assurance

**Environment:** Linux, Python 3.12.3, editable install `nexusrecon==0.7.0`  
**Baseline commit:** `10ead11`  
**Repair branch:** `cursor/assurance-review-3c7b`  
**Live APIs / arbitrary public targets:** not used (fixtures / mocks only)

## Pre-repair baseline

| Command | Result | Artifact |
|---------|--------|----------|
| `python3 -m pytest tests/unit/ -q` | 2135 passed, 13 skipped | `/tmp/nr-unit-all.txt` |
| `python3 -m pytest tests/integration/ -q` | 518 passed, 1 skipped, 1 warning | `/tmp/nr-int-all.txt` |
| `python3 -m pytest tests/smoke/ -q` | 6 passed | `/tmp/nr-smoke.txt` |
| STIX secret repro (inline) | `LEAKED` — value in bundle | shell session |
| Registry proxy clear repro | proxy remained after clear | shell session |
| `python3 -m build --wheel` | wheel built; verify script absent; packs/burp absent | `/tmp/nr-wheel/` |

## Post-repair verification

| Command | Result | Artifact |
|---------|--------|----------|
| `pytest …test_secret_redacted …clear_campaign… …campaign_runner_resume …verifier_packaged …smoke` | 10 passed | `/tmp/nr-repair-verify.txt` |
| `pytest tests/unit/test_phase_4b_stix_export.py tests/unit/test_tool_registry.py tests/unit/test_campaign_runner_resume.py tests/unit/test_entity_graph.py -q` | 39 passed | stdout |
| `python3 -m build --wheel -o /tmp/nr-wheel2` | `nexusrecon/assets/nexusrecon-verify.py` present in wheel | `/tmp/nr-wheel2/` |

## Blocked / skipped

- **Live collector campaigns:** no engagement credentials / authorized targets in environment — marked blocked; use fixtures.
- **100k entity performance:** not measured; envelope inferred from architecture (NetworkX + full state.json).
- **pytest skips:** unit 13 + integration 1 pre-repair (environment / optional deps); not expanded here.

## Interpretation

Pre-repair suite green does **not** imply claim verification: several defects had weak or missing assertions (STIX redaction, registry clear, resume). Repairs add regressions for those. Residual risk sits in doc overclaim, Watch design, Strategy enforcement, OPSEC tool migration, and LangGraph alternate spine.
