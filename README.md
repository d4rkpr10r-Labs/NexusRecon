```
  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
           R E C O N   v 0 . 8 . 0
```

# NexusRecon

**Agentic OSINT orchestration framework for authorized red-team reconnaissance.**

[![status](https://img.shields.io/badge/status-beta-yellow)](#status)
[![version](https://img.shields.io/badge/version-0.8.0-blue)](nexusrecon/__init__.py)
[![python](https://img.shields.io/badge/python-3.11--3.13-blue)](pyproject.toml)
[![engine](https://img.shields.io/badge/engine-agentic-purple)](#why-agentic-osint)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![tests](https://github.com/d4rk-pri0r/NexusRecon/actions/workflows/test.yml/badge.svg)](https://github.com/d4rk-pri0r/NexusRecon/actions/workflows/test.yml)
[![live-drift](https://github.com/d4rk-pri0r/NexusRecon/actions/workflows/live-drift.yml/badge.svg)](https://github.com/d4rk-pri0r/NexusRecon/actions/workflows/live-drift.yml)

You hand it a scope file (or a single English sentence) and a seed
domain. ~30-60 minutes later it hands you back a ranked, prioritized,
citation-backed attack-surface report. Every finding traced to the
tool that produced it, every tool invocation validated against the
signed scope and written to a hash-chained audit log, the whole
campaign exportable as a cryptographically signed STIX 2.1 bundle that
downstream vuln scanners, C2 frameworks, and ticketing systems can
consume directly.

> ⚠ **Authorized use only.** Every tool invocation is validated against
> a signed scope file. Out-of-scope targets are silently dropped and
> logged. Use only against systems you have explicit written permission
> to test. See [DISCLAIMER.md](DISCLAIMER.md).

---

## Why agentic OSINT?

Running the tools is the easy part. The hard part is **deciding which
tool to run next, on what target, in response to what the previous
tool just told you**. And proving the resulting findings are still
true six weeks later when legal asks.

NexusRecon is built around two durable capabilities on the default
`nexusrecon run` path, plus signed handoff and several in-tree
surfaces that are real code but **not** 1.0 product claims (see
ROADMAP “Demoted out of the 1.0 story”):

1. **Living Intelligence Graph**: every entity (subdomain, IP, email,
   person, cloud asset, vulnerability, hypothesis, lead, open
   question) is a first-class node with confidence, citations, and
   traversable relationships. Agents reason over the graph instead of
   flat dictionaries. Per-source ``ProvenanceRecord`` writers stamp
   on the default ``from_state`` path (NEX-19); when a tool result is
   audited, its ``response_hash`` is joined into
   ``ProvenanceRecord.evidence_hash`` (NEX-28).
2. **Dispatch loop**: `reflection_node` + the dynamic dispatcher
   select follow-up tools between phases under lite/full/off
   policies. This loop is what earns its keep on a default run.
3. **Cryptographically signed handoff**: STIX 2.1 bundle export +
   Ed25519 signed receipts + a packaged standalone verifier for
   downstream consumers. Bidirectional import from Nessus, Nuclei,
   generic CSV, STIX, BBOT NDJSON, and Amass enum JSON is available
   as post-run CLI.

**In-tree but demoted / experimental (not default-run product):**
`Strategy` criteria/budgets/simulation/approval queue (planner +
dataclass exist; enforcement largely unread — keep the dispatch
loop, treat the rest as roadmap), Recon Packs + Contribution SDK
(loader/scaffolders exist; marketplace empty; first-party pack not
on the default load path), Watch Mode (snapshot-diff of frozen
`state.json`, not live monitoring), Vision (standalone CLI; default
`vision_calls` budget 0), and the **Continuous Confidence Engine**
(`nexusrecon/verification/` — opt-in via `--verify` /
`NEXUS_ENABLE_VERIFY`; off by default). See ARCHITECTURE.md §§14–18, 21
and ROADMAP demotions.

---

## A worked example

Given seed `acme.com`, mode `medium`, dispatcher `lite`, on a single
laptop with default API keys configured, typical 30-60 min run:

| When | What happens |
|------|-------------|
| **Plan** | `nexusrecon plan "find leaked creds at acme.com, passive only"` synthesizes a `scope.yaml` stub + a `Strategy` (lite dispatch, T1 ceiling, breach lookups enabled). Operator reviews + saves. |
| **Phase 1** · passive footprint | crt.sh + Subfinder + Amass + SecurityTrails surface 47 subdomains. One is `vpn.acme.com`. |
| **Dispatcher fires** | Notices the VPN endpoint and an Android app discovered in the Play Store probe. Simulator forecasts the dispatch will add ~12 entities at $0.02 cost; queues Shodan + the APK analyzer. |
| **Dispatched probe** | httpx fingerprints 12 live HTTP services; one is an unauthenticated admin console. |
| **Phase 2** · identity + cloud | Azure/M365 enumerator finds the M365 federation; bucket_enum finds two public S3 buckets. |
| **Phase 4** · correlation | LLM correlator promotes hypotheses to LeadEntities, draws CITES edges back to supporting evidence, scores attribution confidence. |
| **Phase 7** · vuln correlation | NVD + KEV + EPSS match 4 CVEs. KEV-listed VPN CVE with EPSS 0.87 lands in the graph. |
| **Adversarial scan** | `nexusrecon adversarial scan` finds 2 subdomains lockstep-fabricated by an upstream wildcard DNS server → confidence halved + queued for review. |
| **Phase 8** · attack-surface rank | Top thread: "KEV-listed VPN CVE on `vpn.acme.com` + 3 breached employees in scope for credential reuse". |
| **Phase 9** · reports | `master_reporter` writes the narrative. STIX 2.1 export + Ed25519 signed receipt produced for downstream consumers. |
| **Watch (optional)** | `nexusrecon watch create …` can fingerprint a campaign’s saved `state.json` and queue alerts / micro-campaigns on digest change. As shipped this is **snapshot-diff**, not live re-collection — see ROADMAP demotion. |

**Output**: a `campaigns/acme/<engagement>/<id>/reports/` directory
with the master report + ranked threads + STIX bundle + signed receipt
+ adversarial findings log + 20+ other deliverables.

By hand, you spend 6-8 hours bouncing across crt.sh, Subfinder, Amass,
SecurityTrails, Shodan, Censys, urlscan, GitHub, Hunter, HIBP, NVD,
KEV, EPSS, and Maltego, and you finish without the cross-tool
correlation, LLM follow-up, ranked threats, audit chain, signed STIX
bundle, or a snapshot-diff watch over the campaign checkpoint.

---

## How it works

```
   ┌──────────┐    ┌─────────────┐    ┌──────────────────┐
   │  Scope   ├───►│  Campaign   ├───►│ 12-phase pipeline│
   │  YAML    │    │  Manager    │    │ + LLM dispatcher │
   └──────────┘    └─────────────┘    └────────┬─────────┘
                                               │
       ┌───────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────┐
  │           Living Intelligence Graph                     │
  │  17+ entity types · provenance · confidence ·           │
  │  relationships · hypotheses · leads · open questions    │
  └────────┬──────────────────┬────────────────────┬────────┘
           │                  │                    │
           ▼                  ▼                    ▼
  ┌──────────────┐    ┌──────────────┐     ┌──────────────────┐
  │ OSINT tool   │    │ 11 LLM phase │     │ Strategic engine │
  │ registry +   │    │ agents       │     │ planner +        │
  │ recon packs  │    │              │     │ simulator +      │
  │ (T0-T3)      │    │              │     │ bounded agency   │
  └──────────────┘    └──────────────┘     └──────────────────┘
           │                  │                    │
           └────────────┬─────┴────────────────────┘
                        │
                        ▼
              ┌───────────────────────┐
              │  Adversarial defense  │
              │     (opt-in scan)     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Report engine         │
              │ + STIX 2.1 export     │
              │ + Ed25519 signing     │
              │ + downstream emitters │
              │   (Jira / Nuclei / CS)│
              └───────────────────────┘
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the phase pipeline, agent
personas, dispatcher loop, scoring formula, and a detailed walk
through the post-0.5 architecture additions (Living Graph, Strategy
engine, Verification engine, Pack format, Watch mode, signed bundles,
adversarial defense, vision pipeline).

---

## Quick start

### 1. Install

**Maintainer / full workstation** (`install.sh` — Python deps + optional
Go/CLI binaries):

```bash
git clone https://github.com/d4rkpr10r-Labs/NexusRecon.git
cd NexusRecon
./install.sh                  # creates venv, installs Python deps + system binaries
source venv/bin/activate
./scripts/verify_install.sh   # local health check (also used in CI)
```

**Wheel / PyPI-like path** (what CI automates on Linux x86_64): build a
wheel, install into a clean venv, confirm `nexusrecon` and
`nexusrecon-verify` console scripts, then run `scripts/verify_install.sh`.
See [docs/install-verification.md](docs/install-verification.md) and the
`fresh-install` job in `.github/workflows/test.yml`. `packs/burp` is
checkout-only (not shipped in the wheel). Linux arm64 and
`pipx install nexusrecon` remain maintainer-manual until published.

**Python 3.13 is recommended** (3.11-3.13 supported; **not 3.14**,
CrewAI incompatibility). If `python3` points at 3.14:

```bash
PYTHON=python3.13 ./install.sh
```

### 2. Launch the TUI

```bash
nexusrecon
```

Running with no arguments opens an interactive Textual UI:

![NexusRecon TUI walkthrough](docs/demo/nexusrecon.gif)

From the TUI you can:

- Walk a **new-campaign wizard** that builds the scope file for you
- **Browse the live tool catalogue** with category labels, per-tool
  required + optional key status, and a `c`-shortcut that pops a
  masked edit modal right where the missing key lives
- **Configure** application-wide settings (LLM, OPSEC, storage, debug)
  in the Configuration screen. Tool API keys live in the Tools
  surface
- **Resume** prior campaigns (campaign **diff** is available via the
  `nexusrecon diff <old> <new>` CLI command)
- See the **top-impact missing API keys** ranked by how many tools
  each one would unlock, right on the dashboard

### 3. Or use the CLI directly

```bash
# Author a campaign from a natural-language goal
nexusrecon plan "find leaked credentials at acme.com, passive only"

# Validate a scope file
nexusrecon validate examples/scopes/minimal_seed.yaml

# Dry-run (validate scope + show scope summary, no tools fired)
nexusrecon run --scope examples/scopes/minimal_seed.yaml --dry-run

# Show the planner's proposed Strategy without launching
nexusrecon run --scope my-scope.yaml --plan-only

# Default run (T0+T1, lite dispatcher, ~30-60 min)
nexusrecon run --scope my-scope.yaml --seeds acme.com

# Full agentic dispatch
nexusrecon run --scope my-scope.yaml --seeds acme.com --dispatch-mode full

# Credential harvest + phishing drafts (authorized engagements only)
nexusrecon run --scope my-scope.yaml --seeds acme.com \
  --validate-creds --generate-phishing

# Export a STIX 2.1 bundle + sign it
nexusrecon export <campaign-id> --format stix2
nexusrecon keys generate corp-red-team-2026
nexusrecon sign <campaign-id> --key-id corp-red-team-2026

# Verify a signed bundle (installed console entry OR standalone script)
nexusrecon-verify --bundle stix2-bundle.json \
  --receipt stix2-bundle.json.receipt.json --public-key corp.pub.pem
# Extract the cryptography-only script for auditors without NexusRecon:
nexusrecon-verify --extract ./nexusrecon-verify.py
# In-package crypto verify (same receipt schema):
nexusrecon verify stix2-bundle.json stix2-bundle.json.receipt.json corp.pub.pem

# Continuously monitor a campaign for material changes
nexusrecon watch create acme-watch <campaign-id> \
  --parent-domain acme.com --interval-hours 6
nexusrecon watch tick acme-watch        # one pass; cron-friendly

# Pull in third-party tool output
nexusrecon ingest stix   <campaign-id> partner-bundle.json
nexusrecon ingest nessus <campaign-id> scan-report.nessus
nexusrecon ingest nuclei <campaign-id> nuclei-output.jsonl
nexusrecon ingest bbot   <campaign-id> bbot-output.ndjson
nexusrecon ingest amass  <campaign-id> amass-enum.jsonl

# Author a new agent / tool / dispatch policy
nexusrecon agent new
nexusrecon tool new
nexusrecon policy new

# Install + browse a community recon pack
nexusrecon packs install gh:operator-x/corp-red-team
nexusrecon packs list

# Run adversarial detectors on a campaign's graph
nexusrecon adversarial scan <campaign-id>

# Resume from a checkpoint
nexusrecon resume nr-20260514-120000-abc12345
```

`nexusrecon --help` lists every command. The full reference is in
[`MANUAL.md`](MANUAL.md#5-cli-reference).

---

## Capabilities

### Reconnaissance pipeline (12 phases)

| Phase | What it does | Sample tools |
|-------|-------------|--------------|
| **1. Passive footprint** | Subdomain harvest, cert transparency, WHOIS, DNS, initial intel | crt.sh, Subfinder, Amass, DNS, WHOIS |
| **2. Identity & cloud** | M365/Entra federation, AWS/GCP enumeration, email harvesting | Azure/M365 recon, AWS/GCP recon, Hunter, theHarvester |
| **2.5. Personal-identity pivot** | Bridge corporate identities to personal identities + breach credential exposure | personal_pivot, breach lookups (scope-gated) |
| **3. Code leakage** | Recursive subdomain on high-value hits, GitHub/code recon | github_recon, gitleaks, trufflehog, gitdorker |
| **4. Correlation** | Cross-source asset linking, hypothesis promotion | (LLM agent, no tools) |
| **5. Light active (T2)** | HTTP probing, tech fingerprint, threat-intel enrichment | httpx, Shodan, VirusTotal, GreyNoise, WAF/TLS detection |
| **6. Active (T3)** | Content fuzzing + alt-port probing (authorized runs only) | (OPSEC-routed direct probes) |
| **7. Vuln correlation** | CVE correlation against fingerprinted tech + pretext research | NVD, KEV, EPSS, ExploitDB, GH Advisory, nuclei |
| **7.5. Cred harvest** | Mask + hash creds from prior-phase intel (exposed `.env` / configs) | (extraction from prior intel, no tools) |
| **7.7. Pretext intelligence** | Per-target spear-phish dossier (relationship graph + scoring) | conference_speaker, news, business_partner, social |
| **8. Attack-surface rank** | `CVSS × EPSS × KEV × Metasploit` scoring | (scoring engine) |
| **9. Reporting** | LLM-synthesized narrative + 20+ deliverables + STIX export | (master_reporter agent) |

### Strategic + verification + safety layers

| Capability | Surface | What it does |
|------------|---------|--------------|
| **Living Graph** | `nexusrecon.core.entity_graph` | 17+ entity types, provenance records, confidence, relationships, hypotheses/leads/open-questions as first-class nodes, mutation events. |
| **Strategy + planner** _(partial)_ | `nexusrecon.strategy` | Planner + `Strategy` dataclass + `nexusrecon plan` exist. **Dispatch policies are real**; budgets / success+kill criteria are largely **unread** on the run path (ROADMAP demotion). |
| **Dispatch policies** | `LitePolicy` / `FullPolicy` / `OffPolicy` + plugin | Pluggable per-phase caps + eligibility — this is the durable Strategy surface. |
| **Simulation** _(demoted)_ | `simulate_dispatch_plan` | Forecast helper; often `$0.00` without `cost_per_run_usd`; abort not enforced by default. |
| **Bounded agency** _(demoted)_ | `route_plan_items` | Queue helpers exist; **no production approval resolver** on the default run. |
| **Strategic audit** | `AuditLog` decision methods | Hash-chained strategic event types when callers write them. |
| **Corroboration engine** _(experimental, not wired)_ | `CorroborationEngine` verifier | Confidence lift when multi-source independence-classes (passive_dns + cert + active_probe + …) agree on an entity. |
| **Contradiction detector** _(experimental, not wired)_ | `ContradictionDetector` verifier | Sticky-field + exclusive-relationship conflicts → bounded downgrade + queued for human review. |
| **Confidence propagation** _(experimental, not wired)_ | `ConfidencePropagator` verifier | Downgrades cascade through `cites` / `belongs_to` / `part_of` edges with depth decay + cycle protection. |
| **Adversarial self-check** _(experimental, not wired)_ | `AdversarialSelfCheck` | Heuristic graph audit: single-source high-confidence claims, citation cycles, disconnected islands, source monocultures. |
| **Adversarial defense** | `nexusrecon adversarial scan` / `scan-text` | `scan` runs three graph detectors (poisoned data, suspicious tool-call patterns, evidence inconsistency); `scan-text` runs the prompt-injection scanner on a text input (regex + structural, LLM classifier opt-in). |

The four verifier rows above (Corroboration engine, Contradiction detector,
Confidence propagation, Adversarial self-check) are **opt-in** via
`nexusrecon run --verify` or `NEXUS_ENABLE_VERIFY=1` (NEX-13). Off by default:
a normal `nexusrecon run` does not construct the orchestrator. When enabled,
`EntityGraph.from_state` attaches `VerificationOrchestrator` so multi-source
merges fire corroboration / contradiction / propagation, and phase boundaries
refresh `verification_health` / `weak_links`. See ARCHITECTURE.md section 14.
(`Adversarial defense` above is a separate CLI command and runs when invoked.)

### Interop + distribution

| Capability | Surface | What it does |
|------------|---------|--------------|
| **STIX 2.1 export** | `nexusrecon export … --format stix2` | EntityGraph → STIX Bundle. Stdlib-only serializer. Identity / Vulnerability / Infrastructure / Note SDOs; Domain / IP / Email / URL SCOs (spec-correct observable types). |
| **Signed bundles** | `nexusrecon sign / verify` + `nexusrecon-verify` | Ed25519, passphrase-encrypted PEM keys. Console entry `nexusrecon-verify` runs/extracts the packaged cryptography-only asset (also at `scripts/nexusrecon-verify.py`). |
| **Bidirectional import** | `nexusrecon ingest stix/nessus/nuclei/csv/bbot/amass` | Folds partner STIX, Nessus, Nuclei, CSV, BBOT NDJSON, and Amass enum JSON into the campaign graph (with provenance). |
| **Downstream emitters** | `--format jira / nuclei-targets / cobaltstrike-profile` | Jira REST NDJSON, Nuclei `-list` targets, Cobalt Strike Malleable C2 profile stub (with explicit "review before deploying" warning). |
| **Watch mode** _(snapshot-diff)_ | `nexusrecon watch` | Fingerprints frozen `state.json` via Entity/Scope/Timed sensors. Digests change only after a new campaign run. Tiered actions: low→alert, medium→notification, high→queued micro-campaign. Not live re-collection (F-006). |
| **Vision pipeline** | `nexusrecon vision scan` | Screenshots / PDFs / logos / QR codes → entities + narrative hypothesis. Multi-provider via langchain. Strategy-driven cost cap (`tool_budgets["vision_calls"]`). |

### Extensibility (Recon Pack format)

| Capability | Surface | What it does |
|------------|---------|--------------|
| **Pack format** _(experimental)_ | `~/.nexusrecon/packs/<name>/manifest.yaml` | Tools, agents, dispatch policies, report templates, custom entity/rel types. Manifest hash + unsigned trust model. **Not** a stable 1.0 marketplace. |
| **Pack distribution** _(experimental)_ | `nexusrecon packs install gh:owner/repo` | Git URL or local dir install. Marketplace search URL empty by default. |
| **Agent SDK** | `nexusrecon agent new` | Interactive Rich-prompted scaffolder. Prompt versioning + citation guardrails wired into the template. |
| **Tool SDK** | `nexusrecon tool new` | Interactive capability picker (category × tier × target_types). |
| **Policy SDK** | `nexusrecon policy new` | Phase-eligibility picker. Generated policy selectable via `--dispatch-mode <name>`. |
| **First-party pack** _(checkout dogfood)_ | `packs/burp/` | Burp XML handoff example. **Not** in the wheel and **not** on the default load path — symlink into `~/.nexusrecon/packs` to try (NEX-17). |

The tool registry spans subdomain enumeration, certificate
transparency, DNS / passive DNS, breach data, email / identity,
code-leakage scanners, cloud posture (AWS / Azure / GCP), threat intel
(Shodan / Censys / VT / GreyNoise / urlscan), vuln intel (NVD / KEV /
EPSS / ExploitDB / GH Advisory), mobile, social / SOCMINT, and HUMINT
/ pretext sources. New tools and packs land every release. Run
`nexusrecon tools` for the live catalogue or `nexusrecon packs list`
for installed community packs.

---

## Tier system

| Tier | Name | Contact with target | Examples |
|------|------|---------------------|----------|
| T0 | Pure passive | None, public datasets only | crt.sh, Shodan, GitHub, breach DBs, WHOIS |
| T1 | Semi-passive | DNS resolution, passive DNS | DNS sweep, SecurityTrails, urlscan |
| T2 | Light active | HTTP probes, tech fingerprint | httpx, favicon hashing, WAF/TLS detect |
| T3 | Active | Brute force, fuzzing | ffuf, gobuster, recursive amass |

**Default ceiling is T1.** T2 and T3 require explicit scope
authorization. Out-of-tier tools are dropped with an audit-log entry,
not executed silently. The Phase 1 simulator forecasts tier
escalations BEFORE execution so an LLM dispatcher proposing a T3 call
against a T1-ceiling scope flags visibly in the audit trail.

---

## Deliverables

Every campaign writes to `./campaigns/<client>/<engagement>/<campaign-id>/reports/`:

**Operator-facing**
- `master_report.md`, single cohesive narrative for the client
- `executive_summary.md`, one-page exec-level brief
- `top_threads.md`, top 10 ranked attack paths
- `attack_surface.md`, likelihood × impact matrix, PRE-ATT&CK mapped
- `findings.json`, every `Finding` with severity, confidence, MITRE,
  evidence
- `spear_phishing_intelligence.md`, per-target dossier (Phase 7.7)

**Client-facing**
- `phishing_package.md`, validated emails, pretext hooks, DMARC gaps
- `cloud_posture.md`, M365 federation, AWS account, public buckets
- `vulnerability_correlation.md`, CVE/KEV findings matched to
  fingerprinted tech
- `credential_exposure_paths.md`, personal-to-corporate credential
  punch list (Phase 2.5)
- `harvested_credentials.md`, masked + hashed exposed creds
- `asset_inventory.md` / `.json` / `.csv`, discovered assets
- `entity_graph.html`, interactive living-graph view
- `report.pdf`, full report as PDF (requires `weasyprint`; falls back to
  `report.html`)
- `master_report.obsidian.md`, parallel master report with
  `[[wikilinks]]` + Obsidian callouts (with `--obsidian`)

**Interop**
- `stix2-bundle.json` + `stix2-bundle.json.receipt.json` (with
  `nexusrecon export … --format stix2 && nexusrecon sign …`)
- Jira NDJSON, Nuclei target list, Cobalt Strike profile stub (with
  `nexusrecon export … --format jira / nuclei-targets /
  cobaltstrike-profile`)

**Provenance**
- `logs/audit.jsonl`, hash-chained record of every tool call, dispatch
  decision, strategic decision, simulation outcome, deep-pivot grant,
  human-approval queue add
- `adversarial_findings`, `verification_log`, `simulation_log` in
  `state.json`, each detector's verdicts time-ordered

Full index with content schemas:
[`nexusrecon/docs/REPORT_GUIDE.md`](nexusrecon/docs/REPORT_GUIDE.md).

---

## Configuration

NexusRecon reads secrets and toggles from a `.env` file in the project
root.

The fastest path is the TUI: launch `nexusrecon`, press `c`, and the
Configuration screen presents every editable variable in 11
categories (LLM provider, intel APIs, email/identity, vuln intel,
OPSEC, cloud, storage, debug, vault, etc.). Values are masked, saved
atomically, and the file is `chmod 0o600`'d on disk.

Manual edit is also fine:

```bash
cp .env.example .env
$EDITOR .env
```

Required for any meaningful run — one of:

- **Subscription login (recommended, no key):** install the provider's
  official CLI (`npm install -g @anthropic-ai/claude-code`,
  `npm install -g @openai/codex`, or `npm install -g @xai-official/grok`)
  and log in once — `nexusrecon auth login anthropic`,
  `nexusrecon auth login openai [--device]`, or
  `nexusrecon auth login xai [--device]`. Check readiness with
  `nexusrecon auth status --provider <provider>` (never prints tokens).
  NexusRecon then runs analysis through the official CLI against your
  existing subscription; subscription calls record zero metered USD in
  the campaign budget. OAuth inference is text-only in this release.
- **Codex feature-request path:** set `NEXUS_LLM_PROVIDER=openai-codex` and
  log in with `nexusrecon auth login openai-codex [--device]`. This public
  provider value is a thin alias to the existing OpenAI Codex OAuth adapter;
  it does not duplicate transport, token storage, or refresh logic.
- **API key:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `XAI_API_KEY`
  (xAI direct endpoint `https://api.x.ai/v1`) for direct metered
  billing.
- **Local model:** set `NEXUS_LLM_PROVIDER=ollama`.
- **Offline:** set `NEXUS_LLM_PROVIDER=mock` explicitly — the mock is
  never selected silently. A cloud provider with neither a login nor a
  key raises an actionable error.

Auth resolution follows `NEXUS_LLM_AUTH_MODE` (`auto` by default:
subscription login first, API-key fallback when set; `api_key` forces
the direct SDK client).

Recommended:

- `SHODAN_API_KEY`, `SECURITYTRAILS_API_KEY`, `HUNTER_API_KEY`,
  `HAVEIBEENPWNED_API_KEY`, `GITHUB_TOKEN`.

Optional environment variables for the post-0.5 features:

- `NEXUSRECON_PACK_DIR`. Override the recon-pack root (default
  `~/.nexusrecon/packs/`).
- `NEXUSRECON_KEY_DIR`. Override the signing-key root (default
  `~/.nexusrecon/keys/`).
- `NEXUSRECON_WATCH_DIR`. Override the watch state root (default
  `~/.nexusrecon/watch/`).
- `NEXUSRECON_MARKETPLACE_URL`. URL of a marketplace JSON index for
  `nexusrecon packs search`.

Per-key tool-unlock matrix:
[`CONFIGURATION_GUIDE.md`](CONFIGURATION_GUIDE.md).

---

## Documentation

| Doc | Audience | What's in it |
|-----|----------|--------------|
| [`README.md`](README.md) (this) | First-time visitor | What is it, how to start |
| [`MANUAL.md`](MANUAL.md) | Operator | Install, scope, CLI ref, tool inventory, troubleshooting |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Engineer / curious operator | Phase pipeline, agents, dispatcher, scoring, post-0.5 architecture additions (Living Graph, Strategy engine, Verification, Packs, Watch, Crypto, Adversarial, Vision) |
| [`CONFIGURATION_GUIDE.md`](CONFIGURATION_GUIDE.md) | Operator setting up keys | Every env var, which tools each unlocks |
| [`CHANGELOG.md`](CHANGELOG.md) | Anyone tracking releases | Version-by-version feature list |
| [`ROADMAP.md`](ROADMAP.md) | Anyone tracking what's next | Current state + path to 1.0 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contributor | Dev setup, adding tools / agents / packs |
| [`BETA_TESTING_GUIDE.md`](BETA_TESTING_GUIDE.md) | Beta tester | First campaign walkthrough |
| [`DISCLAIMER.md`](DISCLAIMER.md) | Everyone | Authorized-use policy, legal terms |
| [`nexusrecon/docs/AGENT_LOOP.md`](nexusrecon/docs/AGENT_LOOP.md) | Engineer | Dynamic dispatcher internals |
| [`nexusrecon/docs/REPORT_GUIDE.md`](nexusrecon/docs/REPORT_GUIDE.md) | Operator | Every output file and its schema |

---

## Status

**v0.8.0, beta.** Post-consultation reliability and asset-discovery
stack on top of the honesty-aligned ROADMAP baseline. The default
`nexusrecon run` story is the Living Graph + phase pipeline +
dispatch loop + ranked reports + signed STIX path.
Several post-0.5 packages remain in-tree and unit-tested but are
**demoted** from the 1.0 marquee until they are wired or redesigned
(see ROADMAP “Demoted out of the 1.0 story”).

**Test suite: full suite green** on the assurance baseline; live
collector coverage still depends on keys/binaries.

What's stable on the default path:

- 12-phase pipeline + credential harvest + pretext intelligence
- Living Intelligence Graph with confidence, edges, mutation events,
  and per-source provenance records on the default path (NEX-19)
- Reflection + dynamic dispatcher (lite/full/off policies + caps)
- STIX 2.1 export + Ed25519 signed receipts + packaged verifier
  asset
- Adversarial CLI scan (`nexusrecon adversarial`) when invoked
- Hash-chained audit log + scope gate

What's demoted / experimental (in-tree; not default-run product):

- Strategy framing beyond the real dispatch loop — planner no
  longer authors unread kill/success criteria (NEX-15); only
  dispatch policy + `vision_calls` budget are enforced; simulation
  abort / approval resolver remain demoted
- Recon Packs marketplace + Contribution SDK — empty marketplace
  URL; `packs/burp` checkout dogfood only (not in wheel / not
  default load path; NEX-17 decision)
- Watch Mode — snapshot-diff of frozen `state.json`, not live
  monitoring
- Vision pipeline — standalone CLI; default budget 0; campaign does
  not feed it
- Continuous Confidence Engine — opt-in via `--verify` / `NEXUS_ENABLE_VERIFY`; off by default
- Downstream emitters/importers — post-run manual; STIX path kept

What's still moving / design-only:

- Fleet-Level Learning (privacy-preserving cross-campaign patterns)
- TUI surfaces for Watch / Intent / Vision
- Auto-dispatch of high-severity micro-campaigns
- Curated marketplace content

If you want to help shape the 1.0, see
[`BETA_TESTING_GUIDE.md`](BETA_TESTING_GUIDE.md) or
[`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## License & legal

Licensed under [Apache 2.0](LICENSE). The license grants you broad
permission to use, modify, and redistribute. One ask in return:
**use it only against systems you have explicit written permission
to test.** Full responsible-use policy in
[`DISCLAIMER.md`](DISCLAIMER.md). Third-party components and the
authorized-use rider in [`NOTICE`](NOTICE).

Scope enforcement is built into the framework. Every tool invocation
is checked against the signed scope before execution, tagged with the
scope hash, and written to a hash-chained audit log. This is a
backstop, not a substitute for operator judgment.

---

<sub>NexusRecon is built and maintained by **d4rk pri0r** ·
[darkpriorlabs](https://github.com/d4rk-pri0r) · for defenders who
test like attackers, with permission.</sub>
