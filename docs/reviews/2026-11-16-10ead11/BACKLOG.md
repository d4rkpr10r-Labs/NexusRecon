# BACKLOG — NexusRecon (post-assurance)

Ordered by dependency. Items marked **done-on-branch** are in `cursor/assurance-review-3c7b` (not pushed).

## P0 — Trust / reliability

1. **Merge assurance repairs** after human review (STIX redaction, registry clear, resume spine, checkpoint logging, verifier asset). — *done-on-branch*
2. **Abort-or-warn UX when checkpoint fails** — optional hard-stop flag if `save_state` fails mid-run.
3. **README / ARCHITECTURE Status rewrite** — align Strategy, Packs, Watch, Vision with ROADMAP demotions (F-010).
4. **Preserve multi-source lists in `EntityGraph.from_state`** — unblock Continuous Confidence corroboration (F-011).

## P1 — Execution spine

5. **Route `--use-graph` through same phase set + OPSEC bind** or document as experimental alternate spine; wire SqliteSaver `thread_id` or remove dead checkpointer (F-014).
6. **Bind rate_limiter / proxy_manager on all campaign entry points** and migrate remaining HTTP tools to `registry.opsec_http_get` (OPSEC_STATUS).
7. **Per-campaign registry context** (ContextVar) to replace process-global singleton for parallel/TUI safety.
7b. **TUI Resume continues phases** via shared runner (F-013) — *done (NEX-12)*.

## P2 — Knowledge plane

8. **Wire Continuous Confidence behind `--verify` / config flag** after P0.4 — *done (NEX-13)*.
9. **Watch vertical slice: re-collect seeds then fingerprint** — or permanently label CLI as snapshot-diff (F-006) — *honesty relabel done (NEX-14); re-collect still deferred*.
10. **Enforce Strategy `tool_budgets` / kill / success criteria** or remove from planner prompts — *demotion done (NEX-15); enforcement deferred*.

## P3 — Interop / packaging

11. **Ship `nexusrecon-verify` console entry** that extracts/runs the packaged asset — *done (NEX-16)*.
12. **Decide packs/burp load path** — include in wheel or stop advertising packs as stable.
13. **Fresh-VM / PyPI install matrix** (ROADMAP open item).

## P4 — Differentiation bets (STRATEGY)

14. Provenance writers on default path + report surfacing.
15. Replayable fixture benchmarks (recall, provenance completeness, restart hash).
16. Ingest BBOT/Amass graphs rather than reimplementing recursive DNS.
17. Defer: marketplace, Vision autonomy, fleet learning.

## Explicitly deferred / reject for 1.0

- Fleet-level learning across clients
- Auto-exec micro-campaigns without human approve
- Packs marketplace curation
- Cobalt Strike emitter polish (ROADMAP honesty)
