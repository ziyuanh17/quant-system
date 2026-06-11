# Quant System Web App Source Classification

This document completes the first data-governance step for the private quant
system web app. It inventories source classes, defines what the web app may
truthfully claim, and separates publishable knowledge from sensitive or
prohibited runtime data.

It is based on the development clone at:

```text
/Users/mochifufu/Code/quant-system
```

The development clone is not the runtime clone. This inventory does not claim
to observe current broker truth, runtime `.env`, or current launchd state.

## Classification Levels

| Level | Meaning | Web Use |
| --- | --- | --- |
| Public | Safe for the existing public GitHub Pages summary. | May be published without authentication after explicit sanitization. |
| Private | Appropriate for the authenticated owner console. | May be shown only through typed, sanitized read models. |
| Sensitive | Needed to derive a safe answer but unsafe to render directly. | Read only by a least-privilege server process; expose derived/redacted fields. |
| Prohibited | Must never be read or exposed by the web app. | Exclude from web-process permissions and API schemas. |

Classification is independent of Git tracking. An ignored file is not
automatically sensitive, and a tracked historical document is not
automatically current truth.

## Truth Labels

Every factual statement shown by the web app must carry one of these truth
labels internally:

| Label | Meaning | Example |
| --- | --- | --- |
| Declared default | A source-code, wrapper, template, or config default. It may be overridden at runtime. | `QUANT_SYMBOL` defaults to `AAPL` in `scripts/run_alpaca_paper_refresh.sh`. |
| Resolved runtime configuration | The non-secret configuration actually resolved by the runtime process. | Current strategy, symbol, output paths, and preflight mode from a sanitized runtime configuration snapshot. |
| Observed runtime state | A timestamped observation from the running system or broker. | Latest workflow status, open-order count, or reconciliation result. |
| Historical evidence | A statement that was true for a recorded past event. | The June 10 migration verification snapshot. |
| Design intent | A proposed or intended behavior that may not be implemented. | Future real-money account lane or web decision-trace model. |
| Unknown | Evidence is absent, stale, unreadable, or contradictory. | Current launchd ownership when no fresh scheduler observation exists. |

The UI must not silently convert a declared default, historical evidence, or
design intent into current observed truth.

## Truth Precedence

When sources disagree, prefer:

```text
fresh observed runtime state
  -> fresh sanitized resolved-runtime snapshot
  -> implemented code and typed schemas
  -> checked-in configuration defaults and templates
  -> canonical current documentation
  -> historical evidence
  -> design intent
```

A higher-precedence source may still be stale. Freshness and observed time must
always remain visible.

## Candid Current-System Facts

The knowledge center and status UI must state these facts plainly until newer
evidence changes them:

- The checked-in `configs/dev.yaml` declares a development configuration with
  `live_trading_enabled: false`. It is not proof of the runtime configuration.
- `configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example` is a
  disabled path-template. It is not proof that a launchd job is installed,
  loaded, enabled, or running.
- Runtime wrappers load `.env` when present. The development clone must not
  expose or interpret runtime secret values for the web.
- `scripts/run_alpaca_paper_refresh.sh` defaults to strategy `momentum`, symbol
  `AAPL`, quantity `1`, provider `yfinance`, and status publishing disabled.
  Runtime `.env` may override all of those values.
- The `data/live/` path name contains broker-shaped artifacts and currently
  supports Alpaca paper and fake-live workflows. The path name alone is not
  evidence of real-money trading.
- The codebase contains explicit Alpaca paper connectivity. It does not contain
  a reviewed generic real-money broker workflow.
- The current automatic Alpaca paper workflow supports the `momentum` strategy,
  one symbol, and one quantity configuration per run.
- The development clone currently contains only sample market data and a
  migration bootstrap log. Current account, workflow, order, fill, and
  reconciliation truth belongs to the runtime clone and broker observations.
- `site/status.json` is a heavily sanitized public snapshot generated at a
  point in time. It is not a live API and must be labeled stale when outside
  its expected freshness window.
- `site/progress.json` is a checked-in project-progress snapshot. No automatic
  generator for it is currently present in the codebase.
- Documents describing rehearsals, incidents, migrations, and past scheduled
  runs are historical evidence, not current operating configuration.
- Research evaluation models and artifacts are actively evolving in the
  working tree. The web must expose implemented, readable artifacts only and
  label unimplemented design sections as design intent.

## Source Inventory

### Source Code And Typed Schemas

| Source | Classification | Truth Type | Allowed Web Use |
| --- | --- | --- | --- |
| `src/quant/models/` | Public | Implemented code | Explain implemented concepts and derive API schema metadata. Do not claim model presence means a workflow is enabled. |
| `src/quant/strategies/` | Public | Implemented code | List implemented strategy classes and declared defaults. |
| `src/quant/workflows/` | Public | Implemented code | Explain supported workflows and trace shapes. |
| `src/quant/execution/` | Public | Implemented code | Explain broker, risk, reconciliation, and safety boundaries. Never expose sensitive runtime artifacts derived from these models. |
| `src/quant/operations/` | Public | Implemented code | Explain current health/status behavior and sanitization. |
| `src/quant/research/` | Public | Implemented code | Explain only checked-in and implemented research capabilities. |
| `src/quant/cli.py` | Public | Implemented code | Derive supported commands and declared path defaults; do not present commands as runtime activity. |

The knowledge center should link to code identity such as source commit and
schema version. It should not parse Python source in the browser.

### Checked-In Configuration And Wrappers

| Source | Classification | Truth Type | Allowed Web Use |
| --- | --- | --- | --- |
| `configs/dev.yaml` | Public | Declared default | Show as development defaults with an explicit override warning. |
| `configs/launchd/*.plist.example` | Public | Template/design intent | Explain intended schedule shape and disabled-template status only. |
| `configs/launchd/*.local.plist` | Sensitive | Resolved machine-local configuration | Derive sanitized schedule/path status server-side; never publish raw local paths publicly. |
| `scripts/run_*.sh` | Public | Implemented wrapper defaults | Explain wrapper flow and default values. |
| `.env` | Prohibited | Runtime secret/config source | Never read or expose through the web app. A separate sanitized runtime snapshot must be produced by the runtime process. |

The web app must not read `.env` and then attempt to redact it. The runtime
should explicitly emit a typed allowlisted configuration snapshot containing
only approved non-secret fields.

### Operational Artifacts

| Source | Classification | Allowed Web Use |
| --- | --- | --- |
| `data/scheduler/**` | Private | Run status, task name, duration, artifact references, and freshness through typed models. |
| `data/workflows/**` | Private | Workflow status, timing, signal decision, submission outcome, and sanitized evidence links. |
| `data/locks/**` | Private/Sensitive | Derive active/stale/missing status. Do not expose host PID or raw owner identifiers unless explicitly approved. |
| `logs/**` | Sensitive | Derive health, counts, and sanitized event excerpts. Do not expose arbitrary raw logs by default. |
| `data/validation/**` | Private | Validation status, issue count, and sanitized issue details. |
| `data/metadata/**` | Private | Provider, modality, symbol, request range, version, and lineage after path sanitization. |
| `data/reconciliation/**` | Private | Status and sanitized differences. |
| `site/status.json` | Public | Existing high-level sanitized summary, always with generated time and freshness label. |
| `site/progress.json` | Public | Project-progress snapshot, labeled manual/checked-in until a generator exists. |

Raw filesystem paths should be converted to stable opaque evidence IDs or
repository-relative safe paths before reaching the browser.

### Account And Trading Artifacts

| Source | Classification | Allowed Web Use |
| --- | --- | --- |
| `data/paper/state/**` | Private | Sanitized cash, positions, equity, and processed-signal summary for local paper accounts. |
| `data/paper/signals/**` | Private | Signal action, reason, skip/duplicate state, and decision evidence. |
| `data/dry_run/orders/**` | Private | Intended orders explicitly labeled `record only / not submitted`. |
| `data/dry_run/comparison/**` | Private | Paper-versus-dry-run comparison status and sanitized differences. |
| `data/live/orders/**` | Sensitive | Derived order status and sanitized fields; redact account ID and raw response reference. |
| `data/live/fills/**` | Sensitive | Derived fills, price, quantity, commissions, and timing; redact account ID and raw response reference. |
| `data/live/account_snapshots/**` | Sensitive | Derive authorized private account views; redact account ID and raw response reference. |
| `data/live/reconciliation/**` | Sensitive | Derive private reconciliation status and sanitized differences; redact account ID. |
| `data/live/rehearsals/**` | Sensitive | Show sanitized rehearsal evidence privately; protect exact operational identifiers and paths. |

The UI must label each artifact by broker environment. `data/live/**` must not
be labeled real-money merely because of the directory name.

### Data And Research Artifacts

| Source | Classification | Allowed Web Use |
| --- | --- | --- |
| `data/raw/**` | Sensitive | Derive provider/fetch/coverage metadata only. Do not expose arbitrary provider payloads. |
| `data/normalized/**` | Private | Coverage, symbol, freshness, and lineage; avoid serving full datasets in V1. |
| `data/features/**` | Private | Feature schema, freshness, lineage, and candidate use; avoid full dataset download in V1. |
| `data/results/**` | Private | Backtest metrics and sanitized trades with clear historical/research labels. |
| `data/research/**` | Private | Candidate, trial, evaluation, reproducibility, and recommendation evidence. |
| `data/sample_prices.csv` | Public | Educational/sample content only, never current-market truth. |

### Documentation And Knowledge

| Source Type | Classification | Truth Type | Web Treatment |
| --- | --- | --- | --- |
| Architecture, system-design, data-quality, and trading-stage docs | Public | Canonical guidance unless marked otherwise | Render as current educational guidance with source commit. |
| Runbooks and operations docs | Private by default | Canonical operational guidance | Render privately with applicability and last-reviewed metadata. |
| Roadmaps and designs | Public/private by audience | Design intent and project status | Clearly label as planned, in review, or done; never imply implementation. |
| Incident documents | Private | Historical evidence | Show incident date, resolved/current state, and linked remediation. |
| Rehearsal, smoke, migration, and scheduled-run documents | Private | Historical evidence | Display as past evidence with exact event date; never as current status. |
| `codex_project_handoff.md` | Private | Current collaboration/operational boundary mixed with historical facts | Render privately and flag facts that require fresh runtime verification. |

Markdown remains the knowledge source, but each web-rendered document needs
metadata that states:

```text
document type
truth type
audience
canonical or historical status
applicable environments
related components
source commit
last reviewed date
superseded-by link when applicable
```

## Prohibited Fields

These fields and sources must never appear in public or private web responses:

- Alpaca API keys and secret keys,
- `.env` contents,
- live-trading and rehearsal confirmation phrases,
- authentication tokens and session secrets,
- raw broker payloads,
- `raw_response_ref`,
- unredacted broker account IDs,
- private keys,
- arbitrary absolute filesystem paths,
- raw command environment dumps.

Private console schemas may expose an account alias generated from an
allowlisted mapping. They must not derive or display partial account IDs unless
that policy is explicitly reviewed.

## Required Redactions And Transformations

Before an allowed private source reaches the browser:

- replace account IDs with stable aliases,
- replace filesystem paths with evidence IDs or safe repository-relative paths,
- remove raw response references,
- remove credentials and confirmation phrases by construction,
- label broker environment explicitly,
- attach source and observed timestamps,
- attach freshness and stale state,
- attach schema version,
- preserve unknown/unavailable states instead of filling guesses.

## Knowledge Accuracy Contract

The knowledge center must be candid about implementation status:

1. **Code-backed claims** must link to the source commit and implemented
   component.
2. **Configuration claims** must say whether they are defaults, resolved
   runtime values, or unknown.
3. **Operational claims** must come from timestamped observed evidence.
4. **Historical documents** must show their event date and cannot populate
   current-status fields.
5. **Design documents** must be labeled design intent until their roadmap
   milestone is `Done`.
6. **Unavailable evidence** must render as unavailable or unknown, never as
   healthy or disabled.
7. **Contradictions** must be surfaced as an issue instead of selecting a
   convenient source silently.

## First Read-Model Inputs

The next milestone should define typed sanitized contracts from these initial
sources:

```text
public summary:
  site/status.json
  site/progress.json

private overview:
  latest workflow records
  latest reconciliation report
  sanitized resolved-runtime configuration snapshot
  sanitized scheduler observation

automatic decisions:
  workflow record
  signal record
  risk/safety result
  order/fill records
  before/after account snapshots
  reconciliation report

knowledge:
  checked-in Markdown
  docs metadata manifest
  source commit and roadmap status
```

## Deferred Publication Refresh

Automatic or manual web refresh is intentionally not implemented in this
classification step.

Future implementation should support:

- scheduled publication after reviewed software, docs, or sanitized
  configuration changes,
- scheduled runtime-status refresh at a moderate interval,
- manual owner-triggered CLI/job or deployment refresh without adding a
  mutable web control,
- source commit and generation timestamps on every snapshot,
- idempotent generation and atomic publication,
- failed/stale publication visibility,
- no automatic publication of secrets or newly added fields without explicit
  allowlisting.
