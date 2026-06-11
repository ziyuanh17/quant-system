# Quant System Web App Design

This document designs a professional web console for understanding the live
state, research progress, architecture, and operating history of the quant
system. It is a design only. It does not authorize implementation, server
changes, broker access, or trading actions.

## Product Position

The web app is a read-only operations, research, and knowledge console:

```text
runtime and research artifacts
  -> sanitized read models
  -> authenticated read-only API
  -> web console
```

It replaces guessing from a static GitHub Pages snapshot with a current,
traceable view of the server. GitHub remains the source-code and review system;
the console becomes the place to answer:

- Is the system operating correctly?
- Which trading environments and accounts exist?
- What is each account allowed to do?
- What happened during the latest workflow?
- Are broker and local records reconciled?
- What strategies are being researched, evaluated, or promoted?
- Why does each system component exist?
- Which runbook or incident note explains this state?

The console must distinguish these concepts clearly:

```text
server online != workflow healthy != broker connected != trading enabled
paper account != real-money account
live-shaped execution != real-money execution
```

## Product Principles

1. **Read-only first.** The initial web app cannot submit, cancel, resize, or
   approve orders and cannot change scheduler or safety configuration.
2. **Freshness is visible.** Every status includes observed time, source time,
   expected cadence, and stale/unknown behavior.
3. **No false green.** Missing or stale evidence cannot silently appear
   healthy.
4. **Environment is explicit.** Every account and workflow displays
   `local-paper`, `dry-run`, `alpaca-paper`, or `real-money` precisely.
5. **Evidence is one click away.** Summary states link to sanitized workflow,
   reconciliation, research, incident, and documentation evidence.
6. **Operational and financial health are separate.** A process can run
   successfully while a strategy loses money; a profitable account can still
   have failed reconciliation.
7. **Progressive disclosure.** The landing page supports a ten-second health
   check; detail pages support investigation.
8. **Docs are part of the product.** Architecture, reasoning, incidents, and
   runbooks are browsable beside the status they explain.
9. **Safety state is more prominent than performance.** Trading permissions,
   open orders, reconciliation, and risk limits appear before P&L.
10. **Designed for mobile review.** Critical status and evidence remain usable
    from a phone, but order-capable actions remain outside the app.
11. **Automatic decisions are explainable.** Every scheduled evaluation links
    its trigger, inputs, signal, risk decision, intended action, broker result,
    account snapshot, and reconciliation outcome.

## Automatic Decision Visibility

The quant workflows make automatic decisions; the web app observes and
explains them. The initial web app does not make, approve, trigger, or override
those decisions.

Every automatic evaluation should produce one traceable decision story:

```text
scheduler or manual trigger
  -> data refresh and validation
  -> strategy evaluation
  -> signal decision
  -> portfolio/risk decision
  -> intended action
  -> broker submission or explicit skip/rejection
  -> order/fill terminal state
  -> account snapshot
  -> reconciliation
  -> health and alert result
```

This trace applies to each environment:

- `local-paper`: simulated broker action and local account-state change,
- `dry-run`: intended action recorded without submission,
- `alpaca-paper`: automatic paper-broker action when enabled and permitted,
- `real-money`: future automatic real-money action only when separately
  implemented, enabled, and permitted.

The decision trace must clearly display:

- trigger source and scheduled/manual status,
- strategy, version, parameters, source commit, and input data,
- latest signal and human-readable reason,
- intended side, quantity, price reference, and notional,
- every risk and safety gate with pass/fail evidence,
- whether submission was attempted and why it was attempted or skipped,
- order and fill terminal state,
- before/after account state,
- reconciliation result and unresolved differences.

Canonical outcomes include:

```text
hold
would_submit
blocked_by_safety
blocked_by_risk
skipped_duplicate
submitted
partially_filled
filled
rejected
cancelled
timed_out
reconciliation_failed
```

The Overview shows the latest automatic decision for each environment. The
Operations page shows decision history and timing. Account pages show resulting
orders, fills, and positions. An evidence drawer links the complete trace.

## Users

### Owner And Operator

Needs fast answers about current health, broker truth, scheduler ownership,
positions, open orders, incidents, and required next actions.

### Researcher

Needs strategy candidates, trial history, evaluation evidence, promotion gates,
data lineage, and comparisons without mixing research with operations.

### Learner Or Reviewer

Needs the software flow, component purposes, trading-stage explanations,
glossary, architecture decisions, and linked evidence.

## Information Architecture

Primary navigation:

```text
Overview
Operations
Accounts
Research
Knowledge
Incidents
Settings
```

`Settings` is informational in the first version. It shows resolved,
non-secret configuration and permissions but does not edit them.

FigJam information-architecture map:

<https://www.figma.com/board/VQ0eve49LM5pl6kshr56hA>

## Global Shell

The desktop layout uses:

- a compact left navigation rail,
- a persistent top status bar,
- a full-width main work area,
- an optional right-side evidence drawer.

The top status bar shows:

```text
overall status
server heartbeat freshness
active environment
trading permission
market state
open issue count
last refresh time
```

The active environment label must never simply say `live`. Examples:

```text
SERVER ONLINE / ALPACA PAPER / ORDER SUBMISSION DISABLED
SERVER ONLINE / DRY RUN / RECORD ONLY
SERVER ONLINE / REAL MONEY / TRADING ENABLED
```

The mobile layout uses a top bar, a bottom navigation strip for the five
highest-use areas, and full-screen detail drawers.

## Screen Designs

### 1. Overview

The first viewport is an operator briefing, not a marketing page.

Top row:

- overall system state,
- server heartbeat and host,
- current trading permission,
- most urgent issue or next action.

Account lane table:

| Environment | Connection | Permission | Reconciliation | Open Orders | Positions | Freshness |
| --- | --- | --- | --- | --- | --- | --- |
| Local paper | status | simulated | status | count | count | age |
| Dry run | status | record only | comparison status | intended count | n/a | age |
| Alpaca paper | status | paper orders | status | count | count | age |
| Real money | unavailable/gated/enabled | explicit state | status | count | count | age |

The real-money lane must remain visible even when unavailable so absence is not
mistaken for an unobserved state.

Below the account table:

- latest automatic decision per environment,
- latest workflow timeline,
- current issues and incidents,
- data freshness summary,
- research promotion queue,
- recent intended changes such as source commit or configuration version.

### 2. Operations

This page answers whether the machine is functioning correctly.

Sections:

- automatic decision history and complete decision traces,
- workflow run history and durations,
- scheduler/launchd ownership and next expected run,
- lock status and stale-lock detection,
- data ingestion and validation freshness,
- broker dependency status and latency,
- reconciliation history,
- structured event timeline,
- logs linked by workflow/run ID,
- deploy/source/configuration version history,
- alert and incident history.

Recommended charts:

- workflow success and duration over time,
- data freshness age by dataset,
- reconciliation difference count over time,
- broker/API latency and error counts,
- resource saturation such as disk, memory, and process health.

Every chart supports a time range and links to the underlying events. Avoid
decorative charts without an operational question.

### 3. Accounts

Accounts are organized by environment, not broker branding alone.

Each account page shows:

#### Identity And Permission

- environment and broker,
- sanitized account alias, never raw credentials,
- connection status,
- trading permission,
- safety-gate status,
- maximum order notional and configured risk boundaries,
- last broker snapshot time.

#### Broker Truth

- latest automatic decision and intended-versus-observed outcome,
- equity, cash, and buying power where authorized,
- positions with quantity, average price, last price, market value, and
  unrealized P&L,
- open orders and terminal recent orders,
- recent fills and commissions,
- reconciliation status and differences.

#### Risk And Exposure

- gross and net exposure,
- long and short exposure,
- concentration by symbol,
- buying-power buffer,
- configured versus observed limits,
- stale-price and unavailable-borrow warnings.

#### Performance

- equity curve,
- realized and unrealized P&L,
- daily return,
- drawdown,
- turnover and commissions,
- benchmark comparison when meaningful.

Performance must never override a failed safety or reconciliation state.

### 4. Research

This page is backed by the strategy evaluation harness rather than broker
artifacts.

Top-level views:

- research families,
- candidate strategies,
- trial ledger,
- evaluation runs,
- promotion recommendations,
- datasets and feature lineage.

Candidate detail:

- hypothesis and strategy version,
- parameters and simulation scenarios,
- data/input hashes and point-in-time policy,
- development/validation/holdout results,
- benchmark comparison,
- robustness and multiple-testing evidence,
- failed criteria,
- recommendation state,
- linked research documentation.

Recommended professional research indicators:

- total and distinct trials attempted,
- holdout isolation status,
- dataset and code reproducibility status,
- baseline-relative return and risk,
- drawdown and turnover,
- fee/slippage sensitivity,
- promotion-gate pass/fail,
- current champion/challenger relationship.

The UI may recommend `reject`, `revise`, or `recommend-for-paper-review`. It
cannot enable paper execution.

### 5. Knowledge Center

The `docs/` directory becomes a structured knowledge center rather than a flat
list of Markdown links.

Collections:

```text
Start Here
  system_design_notes.md
  architecture.md
  trading_stages.md

Operate
  operations.md
  runbook.md
  deployment.md
  workflows.md

Safety And Broker Design
  trading_safety.md
  short_selling_risk_policy.md
  broker_adapters.md
  live_broker_adapter.md
  alpaca_paper_adapter.md

Research And Data
  strategy_evaluation_harness.md
  data_quality.md
  dry_run_trading.md

Migration And Scheduling
  mac_studio_migration_roadmap.md
  launchd_*.md

Incidents And Rehearsals
  actionable_paper_order_incident_*.md
  *_rehearsal*.md
  *_smoke_*.md

Project Management
  roadmap.md
  codex_project_handoff.md
```

Each rendered document includes:

- collection and document type,
- summary and intended audience,
- last source commit and modified time,
- status such as canonical, design, runbook, incident, or historical evidence,
- table of contents,
- related system components,
- related live statuses and incidents,
- links to source Markdown and GitHub history.

Knowledge features:

- full-text search,
- glossary tooltips for terms such as reconciliation, dry run, and holdout,
- related-document graph,
- breadcrumbs and previous/next reading path,
- Mermaid rendering for software flows,
- syntax-highlighted commands,
- copyable but clearly labeled safe/read-only versus order-capable commands,
- warning banners on historical or superseded operational instructions.

Markdown should remain the source of truth. A small checked-in manifest should
provide taxonomy and metadata that filenames cannot reliably express.

### 6. System Explorer

The educational flow view explains both what the system does and why:

```text
provider
  -> raw data
  -> normalization
  -> validation and lineage
  -> features
  -> strategy
  -> research evaluation
  -> risk
  -> broker adapter
  -> reconciliation
  -> operations and alerts
```

Selecting a component opens:

- purpose,
- inputs and outputs,
- typed models,
- current implementation status,
- failure modes,
- safety boundary,
- linked docs,
- recent related runs and issues.

This view should use an interactive flow diagram and a detail panel, not a
large decorative architecture image.

### 7. Incidents

The incidents area separates operational learning from current health.

It shows:

- active incidents,
- resolved incident timeline,
- severity and impacted environments,
- detection, containment, remediation, and follow-up status,
- linked workflow/order/reconciliation evidence,
- linked incident Markdown,
- unresolved action items.

The June 9 actionable paper-order incident becomes the first complete example.

### 8. Settings And Safety

Read-only configuration inventory:

- source commit and dependency version,
- host/runtime identity,
- enabled workflows,
- scheduler ownership,
- account environments,
- trading mode and safety-gate state,
- configured risk limits,
- data-retention and freshness policies,
- API/UI authentication state.

Secrets, raw account IDs, tokens, and confirmation phrases must never be
rendered.

## Status Semantics

Each displayed status needs:

```text
state
severity
observed_at
source_updated_at
expected_freshness_seconds
is_stale
source_type
evidence_ref
message
```

Canonical states:

```text
healthy
degraded
failed
running
disabled
not_configured
unknown
stale
```

`disabled` and `not_configured` are neutral only when explicitly expected.
`unknown` and `stale` cannot display as healthy.

## Professional Quant Coverage

A professional-performing quant engineer typically needs visibility across
five distinct planes:

### Operational Plane

- process uptime and heartbeat,
- workflow success, duration, and next expected run,
- dependencies, latency, errors, and resource saturation,
- deploy/configuration versions,
- incidents, alerts, and runbooks.

### Data Plane

- freshness, completeness, validation, and provider reconciliation,
- lineage and point-in-time availability,
- corporate-action and universe-policy status,
- stale or missing feature behavior.

### Trading And Execution Plane

- environment and trading permission,
- signals, intended orders, submitted orders, fills, and rejects,
- open orders, duplicate prevention, and idempotency,
- slippage, commissions, latency, and execution quality,
- broker/local reconciliation.

### Portfolio And Risk Plane

- positions, equity, cash, and buying power,
- realized/unrealized P&L and drawdown,
- gross/net/long/short exposure,
- concentration, turnover, liquidity, and risk-limit utilization.

### Research And Governance Plane

- hypotheses, candidates, trial ledger, and datasets,
- reproducibility, holdout isolation, and robustness,
- baseline/champion/challenger comparisons,
- promotion gates and decision history.

The first release should show unavailable fields explicitly rather than invent
or approximate them.

## Data And API Design

Do not let the browser read arbitrary runtime files. Introduce explicit,
sanitized read models and a read-only API.

Suggested endpoints:

```text
GET /api/v1/overview
GET /api/v1/operations/runs
GET /api/v1/operations/events
GET /api/v1/accounts
GET /api/v1/accounts/{account-alias}
GET /api/v1/research/families
GET /api/v1/research/candidates/{candidate-id}
GET /api/v1/incidents
GET /api/v1/docs
GET /api/v1/docs/{slug}
GET /api/v1/system/components
```

The API layer should:

- map local artifacts into typed public/read-only schemas,
- redact account IDs, credentials, paths, and raw broker payload references,
- calculate freshness and status consistently,
- preserve evidence links through opaque identifiers,
- expose schema version and generated time,
- never accept order, scheduler, or configuration mutations in V1.

Start with polling and HTTP cache validation. Add server-sent events only when
there is a clear need for faster updates. WebSockets are unnecessary for the
current daily workflow cadence.

## Security Model

The existing public `site/status.json` is intentionally heavily sanitized. The
new console contains account, position, research, incident, and operational
details and must not be public.

Required controls:

- private network access such as Tailscale or an authenticated reverse proxy,
- strong authentication,
- read-only authorization in V1,
- least-privilege filesystem access for the API process,
- no `.env`, credential, token, or raw broker-response access,
- explicit redaction tests,
- audit logging for console access,
- CSRF protection if mutations are ever introduced,
- secure headers and dependency scanning,
- separate public-summary and private-console schemas.

Do not add trading actions merely because authentication exists. Order approval
requires a separate threat model and milestone.

## Visual Design

The console should feel quiet, precise, and work-focused.

### Palette

- neutral light or dark surfaces,
- green only for verified healthy/pass states,
- amber for degraded/running/review,
- red for failed, breached, or unreconciled,
- blue for informational and research states,
- gray for disabled or unavailable.

Color is never the only status indicator.

### Typography And Density

- compact navigation and tables,
- tabular numerals for prices, quantities, and times,
- restrained headings,
- no oversized hero section,
- 8px or smaller card radius,
- charts with explicit units, time zones, freshness, and baselines.

### Interaction

- tables support filtering, sorting, column selection, and saved views,
- rows open evidence drawers without losing context,
- status badges include tooltips and observed time,
- dangerous or order-capable commands are never presented as executable UI
  controls,
- mobile prioritizes current state, alerts, accounts, and evidence.

## Recommended Technology Direction

This design does not choose a final framework, but the implementation should
favor:

- a typed Python read-only API that reuses Pydantic models,
- a frontend with robust routing, tables, charts, Markdown rendering, and
  accessibility,
- generated OpenAPI contracts,
- a docs build/index step from repository Markdown,
- a small local database only when historical querying exceeds artifact-file
  practicality,
- OpenTelemetry-compatible metrics, logs, and traces as the system grows.

Do not embed Grafana as the entire product. Grafana is useful for infrastructure
and time-series drill-down, while this console owns quant-specific accounts,
research governance, evidence links, and education.

## Delivery Phases

The finite implementation sequence and completion evidence are tracked in
[quant_system_web_app_roadmap.md](quant_system_web_app_roadmap.md).

### Phase 0: Contract And Security Design

- inventory every source artifact,
- classify public, private, sensitive, and prohibited fields,
- define typed read models and freshness semantics,
- choose authentication/private-network boundary,
- define docs taxonomy manifest.

### Phase 1: Read-Only Operations Console

- overview,
- account lanes and Alpaca paper account detail,
- latest automatic decision and evidence trace,
- latest workflows, reconciliation, issues, and data freshness,
- source/configuration version,
- responsive private web shell.

### Phase 2: Knowledge Center

- render and categorize `docs/`,
- full-text search,
- system explorer,
- incident and runbook linking.

### Phase 3: Research Console

- research families, candidates, trial ledger, evaluation evidence, and
  promotion recommendations,
- data lineage and reproducibility status,
- no paper-promotion mutation.

### Phase 4: Historical Observability

- status and reconciliation history,
- operational metrics, logs, and traces,
- alert routing and incident workflow,
- portfolio/risk/performance history.

### Deferred

- any order submission or cancellation,
- scheduler controls,
- configuration mutation,
- approval workflow,
- real-money trading controls,
- public exposure of private account data.

## Acceptance Criteria For The Design

Before implementation begins:

1. The owner can identify the server state, broker environment, and trading
   permission without ambiguity.
2. Every account status has freshness and reconciliation semantics.
3. The private/public data boundary is documented field by field.
4. Every summary can link to sanitized evidence.
5. Research status cannot accidentally enable execution.
6. Markdown remains the canonical documentation source.
7. The docs manifest categorizes canonical guidance, runbooks, designs,
   incidents, and historical evidence.
8. The UI has defined desktop and mobile information priorities.
9. The API is read-only and excludes secrets and raw broker payloads.
10. Implementation phases preserve the existing trading safety boundary.

## Research Basis

This design follows several professional operating principles:

- Google SRE guidance emphasizes purposeful metrics, prominent service-level
  indicators, dependency monitoring, intended-change/version visibility,
  resource saturation, and tested monitoring.
- OpenTelemetry separates traces, metrics, and logs as complementary
  observability signals.
- Experiment-tracking systems link runs, metrics, datasets, and artifacts and
  support comparison and traceability.
- Modular quant frameworks separate alpha, portfolio construction, risk, and
  execution concerns.

References:

- Google SRE Workbook, Monitoring:
  <https://sre.google/workbook/monitoring/>
- OpenTelemetry Signals:
  <https://opentelemetry.io/docs/concepts/signals/>
- MLflow Experiment Tracking:
  <https://mlflow.org/docs/latest/ml/tracking/>
- QuantConnect Algorithm Framework:
  <https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview>
