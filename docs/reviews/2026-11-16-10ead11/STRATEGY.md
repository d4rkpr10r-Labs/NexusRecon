# STRATEGY — NexusRecon Product Architecture Consultation

**Commit:** `10ead117569180a0a3aa75bfa54035760271bd2e` (`10ead11`)  
**Date:** 2026-11-16  
**Package:** 0.7.0 (pre-beta)  
**Mode:** consultation → assurance (bounded-repair follows in AUDIT)

---

**Decisive recommendation:** Make the Living Intelligence Graph the single trustworthy knowledge plane on one execution spine—provenance-complete entities, honest confidence, and a unified resume/persist path—before any new collector, marketplace, or monitoring surface.

---

## 1. Recommendation (expanded)

NexusRecon already orchestrates a large collector surface (~97 tools), a phase-sequenced campaign runner, NetworkX-backed entity/relationship graphs, ranked reporting, and a signed STIX 2.1 handoff. Those pieces are real on the default `nexusrecon run` path (ROADMAP “What actually works”; `nexusrecon/core/campaign_runner.py`, `nexusrecon/graph/nodes.py`, `nexusrecon/core/entity_graph.py`, `nexusrecon/export/stix.py`, `nexusrecon/crypto/`).

What operators cannot yet rely on is *epistemic quality*: which observations are current, multi-sourced, and still true; whether resume will replay the same contract as a fresh run; whether export redacts sensitive material; whether Watch observes live drift. Docs still partially market Strategy / Packs / Watch / Vision as durable while ROADMAP (2026-06-09 honesty pass) demotes them.

The next unit of product investment should not be more collectors or fleet learning. It should be:

1. **One execution spine** — CLI `run`, CLI `resume`, TUI, and any LangGraph workflow share `run_campaign` (or a thin wrapper) with identical phase set, OPSEC bind, reflection, and persistence semantics.
2. **Graph as source of truth** — every default-path entity carries source list + confidence that survive `from_state` / export / import; CITES/BLOCKS remain first-class.
3. **Honest product surface** — demoted modules stay in-tree and labeled experimental; README Status matches ROADMAP.
4. **Only then** promote Continuous Confidence as opt-in on that foundation, and Watch as true re-collection diff (not frozen `state.json` vs itself).

### Counter-case

Competitors already win on raw discovery yield (BBOT recursion, Amass asset DB depth, ProjectDiscovery speed/templates) and on continuous monitoring UX (reNgine). If NexusRecon spends a release cycle only on graph trust while demos still look thinner than `subfinder | httpx | nuclei`, buyers may never reach the trust story. Mitigation: keep passive footprinting + ranked threads as the demo spine; make trust fixes invisible improvements to that same demo (resume, STIX redaction, provenance in reports), not a separate product pitch.

---

## 2. Strengths (demonstrated)

| Strength | Evidence | Durability |
|----------|----------|------------|
| Phase-sequenced campaign with scope gate + audit chain | `campaign_runner.py`, `scope.py`, `audit.py`; tests green | High — core path |
| Living graph with entity merge, edges, hypotheses/leads | `entity_graph.py`; unit suite `test_entity_graph.py` | High if provenance writers finish |
| Dynamic dispatch / reflection loop | `graph/dynamic_dispatcher.py`, `reflection_node` | Medium — real loop; Strategy criteria unread |
| Ranked attack-surface reporting | `reports/engine.py`; integration campaign report tests | High for operator value |
| Signed STIX + standalone verifier design | `export/stix.py`, `crypto/`, `scripts/nexusrecon-verify.py` | High *if* redaction + packaging fixed |
| Large tool registry with tier/prereq gating | `tools/registry.py`; ~97 tools registered at import | Medium — many key/binary gated |
| Adversarial CLI scan (standalone) | `adversarial/`; separate from verification engine | Medium — useful when invoked |
| Doc honesty infrastructure (ROADMAP demotions) | ROADMAP Demoted section | High — engineering culture asset |

---

## 3. Weaknesses (architecture stress)

### Execution vs knowledge

- **Execution model:** phase pipeline + inter-phase reflection/dispatch (`campaign_runner` → phase nodes → `reflection_node`). Not BBOT-style continuous event fan-out; fan-out is batched between phases. Dedup is largely cache-key + graph merge; backpressure is dispatch caps (`MAX_PER_CYCLE` / `MAX_TOTAL`), not queue depth.
- **Knowledge model:** NetworkX `EntityGraph` in campaign `state.json`. Persistence is checkpoint files, not a queryable historical store (contrast Amass asset-db / reNgine Postgres). Multi-campaign merge and access boundaries are weak; handle-ubiquity is opt-in salted hashes only (OPSEC_STATUS)—not fleet learning.
- **Resume parity (defect):** `cli/main.py:resume` reimplements a reduced phase list (missing `phase2_5`, `phase7_5`, `phase7_7`, reflection, registry OPSEC bind) vs `run_campaign`. LangGraph `workflow.py` SqliteSaver is a third spine.
- **Persistence contract:** `campaign_runner` swallows `save_state` / `begin_phase` / `end_phase` exceptions (`except Exception: pass`), so operators can finish “successfully” with a stale checkpoint.
- **Registry isolation:** process-global `@lru_cache` singleton; `clear_campaign_context` never clears `_proxy_manager` (dead assignment after `return` in `audit_log` property). Concurrent or sequential campaigns can leak OPSEC routing.
- **Watch:** sensors fingerprint graphs loaded from frozen `state.json` (`watch/runner.py::_default_graph_loader`). Without re-collection, continuous monitoring is structurally a no-op after the first non-trivial tick settles—ROADMAP Demoted is correct; ARCHITECTURE §18 still reads “live.”
- **Verification:** Opt-in via `--verify` / `NEXUS_ENABLE_VERIFY` (NEX-13); still off on default run. Multi-source `from_state` restored in NEX-8.
- **Strategy framing:** `kill_criteria` / `success_criteria` demoted from planner prompts (NEX-15); only `dispatch_policy_name` + `vision_calls` budget enforced; simulation often reports `$0.00` when `cost_per_run_usd` unset.
- **Packaging:** verifier asset + `nexusrecon-verify` console entry ship in the wheel (NEX-16); `packs/burp` intentionally omitted and documented as checkout dogfood (NEX-17). Editable checkout ≠ installed product for packs.
- **STIX secret mapper:** `_map_secret` embeds `entity["value"]` in `content` (confirmed leak of `AKIA…` in bundle JSON); unit test only asserts abstract contains “redacted.”
- **Scale envelope (inspection, not measured at 100k):** in-process NetworkX + full `state.json` serialize implies soft envelope ~1k–10k entities on a laptop before memory/export cost dominates; 100k needs shard/index strategy (not prescribed here).

### Lifecycle gaps (operator questions)

| Lifecycle | Assessment |
|-----------|------------|
| Discovery/coverage | Strong passive footprint tooling; recursive depth weaker than BBOT |
| Attribution / entity resolution | Graph merge + identity helpers; provenance writers on default path (NEX-19); evidence_hash join deferred |
| Evidence / confidence | Audit + citations; Continuous Confidence unwired; LLM evidence often `unverified` |
| Hypotheses / investigation planning | Hypothesis/lead entities + correlator; Intent planner exists as CLI island |
| Prioritization | Phase 8 ranking works on default path |
| Continuous refresh | Watch demoted; micro-campaigns queue only |
| Extensibility | Pack/SDK demoted; entry-point tools real |
| Reliability / deployment | Smoke+unit strong; resume/OPSEC gaps closed; Linux x86_64 wheel CI (NEX-18); arm64/pipx-from-PyPI open |

MITRE ATT&CK Enterprise mapping (taxonomy only, not executable proof): collectors primarily support **Reconnaissance** (T1590–T1598 family) and feed **Resource Development** context (e.g. compromised credentials as planning inputs). Do not treat taxonomy tags as coverage claims.

---

## 4. Competitive comparison (primary-source based)

Closest baselines: **BBOT**, **OWASP Amass (OAM + asset-db)**, **ProjectDiscovery toolchain / Cloud**, with **reNgine** and **SpiderFoot** as workflow/correlation references.

| Dimension | NexusRecon | BBOT | Amass/OAM | ProjectDiscovery | reNgine | SpiderFoot |
|-----------|------------|------|-----------|------------------|---------|------------|
| Collection style | Phase + dispatch | Event-driven recursive | Enum + transforms | Pipeline CLI / cloud | YAML engines + Celery | Event modules |
| Knowledge store | NetworkX + JSON state | Scan events/graph | Persistent asset-db (SQLite/PG/Neo4j) | Cloud asset graph / files | Postgres | SQLite |
| Continuous monitor | Watch (snapshot; demoted) | Re-scan | Historical reuse in DB | Cloud monitoring | Clocked/periodic + diffs | Re-scan |
| Reasoning / priority | LLM correlator + rank | Module recursion | Query (triples) | Templates + labels | Filters + GPT assists | YAML correlations |
| Handoff | Signed STIX (design) | Output modules | DB / enum output | JSON / tickets (cloud) | Export / H1 | CSV/JSON/GEXF |
| Licensing posture | Apache-2.0 OSS | OSS | OSS | OSS tools + paid cloud | OSS | OSS (+ HX history) |

Sources: [BBOT How it Works](https://www.blacklanternsecurity.com/bbot/Stable/how_it_works/), [Amass docs / OAM / asset-db](https://owasp-amass.github.io/docs/), [ProjectDiscovery opensource + cloud assets](https://docs.projectdiscovery.io/opensource), [reNgine](https://github.com/yogeshojha/rengine), [SpiderFoot correlations](https://github.com/smicallef/spiderfoot/blob/master/correlations/README.md).

**Differentiation that can stick:** citation-backed living graph + agentic phase planning + cryptographically signed interchange—if and only if maturity claims match runtime and resume/export are trustworthy. Discovery breadth alone is not durable vs BBOT/PD.

---

## 5. Ranked bets (~10)

Disposition key: keep / revise / defer / reject.

| Rank | Bet | Disposition | Why |
|------|-----|-------------|-----|
| 1 | **Unified execution spine** (`run`/`resume`/TUI → `run_campaign`) | keep | Removes silent behavior forks; prerequisite for reliability claims |
| 2 | **Provenance-complete graph + honest confidence on default path** | keep | Answers “can I trust this observation?”; enables later verification |
| 3 | **STIX/crypto handoff hardening** (redaction, wheel includes verifier) | keep | Unique chain-of-custody story; currently broken on secrets + packaging |
| 4 | **Registry/context isolation + OPSEC bind on all entry points** | keep | Cross-campaign leakage and dormant proxy/rate limiter are trust bugs |
| 5 | **Persistence/completion contract** (fail loud on checkpoint errors; surface errors in `campaign_complete`) | keep | Operators must know when state is incomplete |
| 6 | **Watch → re-collect then diff** (or permanently label snapshot-diff) | revise | Continuous monitoring is table stakes vs reNgine; current design cannot work |
| 7 | **Promote Continuous Confidence as opt-in after (2)** | defer→keep later | Code exists; wiring before provenance fix wastes the feature |
| 8 | **Question-driven collection (Intent → enforced Strategy budgets/criteria)** | revise | Planner exists; enforce read path or stop selling Strategy as product |
| 9 | **Replayable fixture benchmarks** (yield/precision/restart) | keep → *harness (NEX-20)* | `nexusrecon.benchmarks` + planted_passive fixture; attribution/wall-clock deferred |
| 10 | **Packs marketplace / Vision-as-autonomous / fleet learning** | defer / reject for 1.0 | ROADMAP correctly demotes; no audience yet |
| 11 | **Deception-aware evidence + adversarial hypothesis review** | keep (narrow) | Adversarial CLI exists; fold signals into ranking, don’t expand UI |
| 12 | **Integrate don’t rewrite** for recursive DNS depth (shell out / ingest BBOT or Amass graphs) | keep → *ingest adapters (NEX-21)* | `BBOTImporter` / `AmassImporter` + `nexusrecon ingest bbot|amass` |

### Three flagship workflows

1. **Authorized engagement campaign:** scope → plan/run → ranked threads → signed STIX (demo spine).
2. **Graph investigation:** open questions → CITES traversal → next tool suggestion under budget (post-spine).
3. **Refresh & certify:** re-collect watched seeds → diff → optional micro-campaign with human approve (post-Watch revise).

### Ordered implementation plan

1. Spine unify + persistence loud failures + registry clear fix.  
2. STIX redaction + package verifier script; strengthen export tests.  
3. Provenance writers + `from_state` multi-source fidelity.  
4. README/ARCHITECTURE alignment with ROADMAP demotions.  
5. Opt-in verification orchestrator behind flag.  
6. Watch re-collection vertical slice.  
7. Strategy criteria enforcement or UI demotion.  
8. Benchmark harness with synthetic ground truth.  
Defer marketplace, Vision autonomy, fleet learning; simplify downstream emitters to STIX-first; retire misleading “stable” badges for demoted modules.

---

## 6. Benchmark plan

Use synthetic scopes + recorded HTTP fixtures (no arbitrary public targets).

| Metric | Method | Gate idea |
|--------|--------|-----------|
| Discovery recall @ fixed budget | Seed graph with planted subdomains/emails; run passive phases | ≥ baseline recall of keyless tools |
| Attribution precision | Plant merges/splits; measure incorrect entity merges | ≥ 0.95 on fixture set |
| Time-to-useful-evidence | Wall clock to first High lead in fixture campaign | Track regression |
| Provenance completeness | % entities with ≥1 real source surviving export/import | ≥ 0.99 default path |
| Restart consistency | Interrupt after phase N; resume; compare graph hash excluding timestamps | Exact match on entity set |
| Degraded-state accuracy | Kill keys/binaries; run-health must list skips, not silent empty success | 0 false “healthy” |
| Export safety | Secret fixtures must not appear in STIX/JSON reports | 0 leaks |
| Cost honesty | Simulation vs actual `cost_per_run_usd` | Non-zero when tool declares cost |

Operating envelope targets (to measure, not prescribe DB): 1k entities interactive; 10k overnight laptop; 100k requires external index—document when exceeded.

---

## 7. Capability matrix (summary)

| Operator problem | Entry | Activation | Operational state | Evidence state | Gap |
|------------------|-------|------------|-------------------|----------------|-----|
| Passive footprint | `run` / TUI | Default | default path | executed (unit/int) + source | Depth vs BBOT |
| Identity/cloud | phases 2 / 2.5 | Default | default path | tests | Key gated tools |
| Correlation / leads | phase 4 / 8 | Default | default path | tests | Provenance writers |
| Strategy budgets | `plan` / Strategy obj | Explicit | partially integrated | source inspection | Criteria unread |
| Confidence verify | `verification/` | Not on run | stubbed/planned wiring | unit only | No production caller |
| Watch freshness | `watch tick` | Explicit CLI | standalone / broken for live | unit + ROADMAP | Frozen state loader |
| Packs | `packs` CLI | Explicit | partially integrated | source | Empty marketplace; burp not in wheel |
| Vision | `vision scan` | Explicit; budget 0 | standalone | unit | No campaign feed |
| STIX sign/verify | export / scripts | Explicit | default export; verify script unpackaged | executed leak repro | Redaction bug |
| Resume | `resume` | Explicit | partially integrated | source inspection | Phase/OPSEC divergence |
| Micro-campaigns | Watch HIGH | Queue only | intentional limit | docs aligned | No auto-exec |

Full row-level coverage tracked in `REVIEW_COVERAGE.csv`.

---

## 8. Sources

- Repo: README, ARCHITECTURE, ROADMAP, OPSEC_STATUS, MANUAL, TESTING_RUNBOOK, CHANGELOG @ `10ead11`
- Code: `nexusrecon/core/*`, `graph/*`, `tools/registry.py`, `watch/*`, `verification/*`, `export/stix.py`, `cli/main.py`
- Executed: unit 2135 passed / 13 skipped; integration 518 passed / 1 skipped; smoke 6 passed; STIX leak repro; registry proxy clear repro; wheel build
- External: BBOT docs; OWASP Amass docs; ProjectDiscovery docs; reNgine GitHub; SpiderFoot correlations README
- Internal claim inventory: `/cursor/stores/bc-5320a189-5267-455a-b4f4-deb5bdee1a88/internal/nexusrecon-doc-claims-inventory.md`
