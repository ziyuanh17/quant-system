# Roadmap

This document tracks the intended build order for the quant system.

It exists so we do not lose the thread as design questions branch into useful
side discussions.

## Status Legend

- `Done`: implemented and checked in
- `In Review`: implemented locally but not yet committed
- `Next`: recommended next implementation milestone
- `Planned`: not started

## Milestones

| Order | Milestone | Status | Purpose |
| --- | --- | --- | --- |
| 1 | Repo scaffold | Done | Establish Python project layout, typed domain models, CLI, tests, docs, and VectorBT-backed backtest path. |
| 2 | GitHub and CI foundation | Done | Add GitHub repo, CI, Makefile commands, `uv.lock`, and repeatable local checks. |
| 3 | Backtest artifacts | Done | Save durable backtest summaries and trade outputs under `data/results/`. |
| 4 | Multi-modal ingestion foundation | Done | Add provider interface, modality-aware raw dataset models, yfinance market-bar ingestion, normalized market-bar output, and news/text data model placeholders. |
| 5 | Data validation v1 | Done | Add market-bar validation checks and `quant data validate`. |
| 6 | Validation guardrails | Done | Run validation by default during ingestion and before CSV backtests; allow explicit `--skip-validation`. |
| 7 | Data lineage v1 | Done | Persist validation reports and dataset metadata that link raw data, normalized data, provider, symbol, timestamps, and normalization version. |
| 8 | Storage abstraction v1 | Done | Add a `MarketBarStore` boundary so CSV can later be swapped or complemented with Parquet. |
| 9 | Feature engineering v1 | Done | Compute and persist feature datasets from normalized/validated data. |
| 10 | Strategy feature interface | Done | Let strategies consume typed feature inputs instead of raw price frames only. |
| 11 | Provider reconciliation | Done | Add checks and policies for comparing or combining data from multiple providers. |
| 12 | Paper trading foundation | Done | Add paper broker, risk checks, order records, portfolio snapshots, and audit records. |
| 13 | Scheduler Loop v1 | Done | Add finite scheduled task runs with durable run records. |
| 14 | Paper Signal Execution v1 | Done | Connect strategy signals to scheduled paper-trading decisions. |
| 15 | Broker State Persistence v1 | Done | Persist paper account cash and positions across scheduled runs. |
| 16 | Idempotent Paper Signals v1 | Done | Prevent duplicate paper orders for repeated signal processing. |
| 17 | Service Deployment v1 | Done | Define local/server wrapper, environment config, logs, and deployment docs. |
| 18 | Operational Observability v1 | Done | Add a read-only health command that checks scheduler records, signal records, paper state, and logs. |
| 19 | Data Refresh Workflow v1 | Done | Refresh and validate provider data before running scheduled paper signal execution. |
| 20 | Concurrent Run Safety v1 | Done | Prevent overlapping refresh workflow runs from mutating the same paper state. |
| 21 | Atomic State Writes v1 | Done | Write paper broker state through durable temp files, atomic replacement, and backups. |
| 22 | Paper State Reconciliation v1 | Done | Replay paper signal audit records and compare them against persisted broker state. |
| 23 | Health Check Integration v1 | Done | Surface lock and paper-state reconciliation status in the operational health command. |
| 24 | Dashboard Alert Status v1 | Done | Publish sanitized operational health status to the GitHub Pages dashboard. |
| 25 | Broker Adapter Boundary v1 | Done | Define the paper-vs-real broker boundary before adding real-money trading logic. |
| 26 | Live Trading Safety Gates v1 | Done | Add explicit controls that keep real-money trading impossible by default. |
| 27 | Dry-Run Broker Adapter v1 | Done | Add a live-shaped broker adapter that records intended orders without submitting them. |
| 28 | Dry-Run Signal Execution v1 | Done | Route strategy signals into dry-run intended-order records. |
| 29 | Dry-Run Scheduler v1 | Done | Run dry-run signal execution on a scheduled loop with durable run records. |
| 30 | Paper vs Dry-Run Comparison v1 | Done | Compare scheduled paper decisions with scheduled dry-run intended orders. |
| 31 | Comparison Health Integration v1 | Done | Surface paper-vs-dry-run divergence in operational health and dashboard status. |
| 32 | Dry-Run Refresh Workflow v1 | Done | Refresh data, run dry-run signals, compare outputs, and publish health in one server workflow. |
| 33 | Dry-Run Server Wrapper v1 | Done | Add repeatable local/server wrapper configuration for the dry-run refresh workflow. |
| 34 | Live Broker Adapter Design v1 | Done | Design the real broker adapter, credential boundary, and account reconciliation contract before real orders are possible. |
| 35 | Live Audit Models v1 | Done | Add typed live order, fill, account snapshot, and reconciliation models without broker network access. |
| 36 | Fake Live Broker Client v1 | Done | Add a no-network fake broker client for live adapter tests before any real SDK integration. |
| 37 | Fake-Backed Live Adapter v1 | Done | Connect the live adapter boundary to the fake client before any real broker SDK integration. |
| 38 | Fake Live Reconciliation v1 | Done | Compare local live artifacts against fake broker account/order/fill state before any real SDK integration. |
| 39 | Fake Live CLI v1 | Done | Add safety-gated fake live commands for order submission and reconciliation without real broker SDKs. |
| 40 | Alpaca Paper Adapter Design v1 | Done | Design the first external paper-broker adapter and dependency boundary before adding the Alpaca SDK. |
| 41 | Alpaca Paper Mapping v1 | Done | Add Alpaca-shaped mapping helpers and tests without installing the Alpaca SDK. |
| 42 | Alpaca Optional Dependency v1 | Done | Add `alpaca-py` as an optional dependency and verify import boundaries without requiring credentials or network access in default CI. |
| 43 | Alpaca Paper Client v1 | Done | Wrap the optional SDK behind a paper client boundary without enabling real-money trading. |
| 44 | Alpaca Paper CLI v1 | Done | Add explicit safety-gated Alpaca paper commands without a generic live broker selector. |
| 45 | Alpaca Paper Reconciliation v1 | Done | Reconcile local live artifacts against Alpaca paper account/order/fill state. |
| 46 | Alpaca Paper Manual Smoke Runbook v1 | Done | Document the exact human-run paper broker smoke test before adding scheduled Alpaca workflows. |
| 47 | Alpaca Paper Workflow Design v1 | Done | Design the scheduled Alpaca paper workflow only after the manual smoke runbook is reviewed. |
| 48 | Alpaca Paper Refresh Workflow v1 | Done | Implement one finite lock-protected Alpaca paper refresh workflow with fake-driven tests. |
| 49 | Alpaca Paper Server Wrapper v1 | Done | Add an env-driven wrapper for running the Alpaca paper refresh workflow repeatedly on a server. |
| 50 | Alpaca Paper Operational Health v1 | Done | Surface Alpaca paper workflow/reconciliation health in the local health command and dashboard status. |
| 51 | Alpaca Paper Status Publishing Wrapper v1 | Done | Let the Alpaca paper server wrapper publish sanitized dashboard status after successful health checks. |
| 52 | Alpaca Paper Manual Smoke Execution v1 | Done | Ran and documented one tiny broker-connected Alpaca paper smoke test, including manual cancellation refresh and reconciliation. |
| 53 | Controlled Recurring Alpaca Paper Run v1 | Done | Add a no-order preflight mode and runbook guidance before enabling recurring Alpaca paper execution. |
| 54 | Controlled Full Alpaca Paper Wrapper Run v1 | Done | Ran and documented one full server-style Alpaca paper wrapper cycle with data refresh, broker snapshot, and reconciliation. |
| 55 | Workflow Decision Visibility v1 | Done | Add latest signal and broker-submission outcome fields to Alpaca paper workflow records. |
| 56 | Dashboard Decision Visibility v1 | Done | Publish sanitized Alpaca paper decision and broker-submission status to the dashboard. |
| 57 | Paper/Scheduler Status Cleanup v1 | Done | Let dashboard publishing disable inactive paper scheduler/signal checks so Alpaca paper status is not hidden by stale lanes. |
| 58 | Recurring Alpaca Paper Schedule Design v1 | Done | Document the first daily Alpaca paper schedule policy without enabling automation. |
| 59 | Alpaca Paper launchd Template v1 | Done | Add a disabled macOS launchd template for reviewed recurring Alpaca paper runs. |
| 60 | Launchd Localization Runbook v1 | Done | Document how to safely localize, validate, load, unload, and ignore machine-specific launchd plists. |
| 61 | Launchd Local Preflight v1 | Done | Created and validated a local untracked launchd plist copy, then ran preflight without loading the recurring job. |
| 62 | Launchd Manual Full Wrapper Review v1 | Done | Ran one manual full wrapper cycle and dashboard publish using the launchd-localized setup before loading launchd. |
| 63 | Launchd Disabled Load Rehearsal v1 | Done | Correct the launchd calendar shape and document the disabled bootstrap failure; no job was enabled, kickstarted, or left loaded. |
| 64 | Launchd Bootstrap Failure Diagnosis v1 | Done | Diagnose launchctl bootstrap error 5 and document that `Disabled=true` prevents bootstrap on this macOS setup. |
| 65 | Launchd Controlled Load Rehearsal v1 | Done | Loaded the actual Alpaca paper launchd label with `Disabled=false`, confirmed `runs = 0`, then unloaded and removed the installed plist. |
| 66 | Launchd Triggered Execution Rehearsal Design v1 | Done | Design a preflight-only launchd-triggered execution rehearsal before using `kickstart` on the real wrapper. |
| 67 | Launchd Preflight Kickstart Rehearsal v1 | Done | Attempted one preflight-only launchd `kickstart`; the Codex path failed under `Documents`, then the runtime clone succeeded with exit code 0. |
| 68 | Launchd Filesystem Permission Diagnosis v1 | Done | Create a launchd runtime clone outside `Documents`, rebuild local dependencies there, and verify preflight-only kickstart succeeds. |
| 69 | Launchd Full Wrapper Rehearsal Design v1 | Done | Design the first non-preflight launchd-triggered Alpaca paper wrapper run from the runtime clone before executing it. |
| 70 | Launchd Full Wrapper Rehearsal v1 | Done | Ran exactly one non-preflight launchd-triggered Alpaca paper wrapper cycle from the runtime clone, then unloaded and reviewed artifacts. |
| 71 | Launchd Recurring Schedule Activation Design v1 | Done | Design when and how to leave the Alpaca paper launchd schedule loaded for recurring runs, including monitoring and rollback. |
| 72 | Launchd Recurring Schedule Activation v1 | In Review | Activated the Alpaca paper launchd schedule from the runtime clone and left it loaded for the first natural scheduled run. |
| 73 | First Natural Scheduled Run Review v1 | Next | Review the first natural weekday 12:55 PM Alpaca paper launchd run, then decide whether to keep the schedule loaded. |

## Current Recommendation

The current milestone is **First Natural Scheduled Run Review v1**. Review the
first natural weekday 12:55 PM Alpaca paper launchd run, then decide whether to
keep the schedule loaded.

## Status Convention

- `Planned`: not started yet.
- `In Review`: implemented or documented in the working tree, checks pass, and
  the change is waiting for human review or check-in.
- `Done`: reviewed and committed into the project history.

The server path now has data refresh, validation, paper execution, and health
checks, lock files that prevent overlapping workflow runs, atomic paper state
writes, read-only state reconciliation, an integrated health command, a
sanitized dashboard status file, a paper broker adapter boundary,
fail-closed trading safety gates, a live-shaped dry-run order adapter,
strategy-to-dry-run signal execution, scheduled dry-run signal runs, a
paper-vs-dry-run comparison report, health/dashboard visibility for comparison
failures, a composed dry-run refresh workflow, a server wrapper for running
that dry-run workflow repeatedly, a live broker adapter design boundary, typed
live audit models, a no-network fake live broker client, a fake-backed live
adapter, fake live reconciliation, safety-gated fake live CLI commands, and an
Alpaca paper adapter design boundary, Alpaca-shaped mapping helpers for order
requests, order statuses, order records, fill records, account snapshots, and
positions, an optional `alpaca-py` dependency boundary that does not load the
SDK during default imports, an Alpaca paper client wrapper that can submit
market orders through fake SDK/client objects in tests, explicit safety-gated
Alpaca paper order/snapshot CLI commands, Alpaca paper reconciliation against
local live artifacts, and a manual smoke runbook for the first broker-connected
check, a scheduled Alpaca paper workflow design, and a finite lock-protected
Alpaca paper refresh workflow with fake-driven tests and no default network or
credential requirements in CI, and an env-driven wrapper that runs
`quant workflow alpaca-paper-refresh` with timestamped logs, and Alpaca paper
workflow/reconciliation health in local checks and the static dashboard status.
The Alpaca paper wrapper can optionally publish sanitized dashboard status after
the workflow/health check. The next step should run and document one tiny
broker-connected Alpaca paper smoke test before relying on scheduled runs.

## Corrected Near-Term Order

```text
data ingestion
  -> data validation
  -> validation guardrails
  -> data lineage
  -> storage abstraction
  -> feature engineering
  -> strategy feature interface
  -> provider reconciliation
  -> paper trading foundation
  -> scheduler loop
  -> paper signal execution
  -> broker state persistence
  -> idempotent paper signals
  -> service deployment
  -> operational observability
  -> data refresh workflow
  -> concurrent run safety
  -> atomic state writes
  -> paper state reconciliation
  -> health check integration
  -> dashboard alert status
  -> broker adapter boundary
  -> live trading safety gates
  -> dry-run broker adapter
  -> dry-run signal execution
  -> dry-run scheduler
  -> paper vs dry-run comparison
  -> comparison health integration
  -> dry-run refresh workflow
  -> dry-run server wrapper
  -> live broker adapter design
  -> live audit models
  -> fake live broker client
  -> fake-backed live adapter
  -> fake live reconciliation
  -> fake live CLI
  -> Alpaca paper adapter design
  -> Alpaca paper mapping
  -> Alpaca optional dependency
  -> Alpaca paper client
  -> Alpaca paper CLI
  -> Alpaca paper reconciliation
  -> Alpaca paper manual smoke runbook
  -> Alpaca paper workflow design
  -> Alpaca paper refresh workflow
  -> Alpaca paper server wrapper
  -> Alpaca paper operational health
  -> Alpaca paper status publishing wrapper
  -> Alpaca paper manual smoke execution
  -> controlled recurring Alpaca paper run
  -> controlled full Alpaca paper wrapper run
  -> workflow decision visibility
  -> dashboard decision visibility
  -> paper/scheduler status cleanup
  -> recurring Alpaca paper schedule design
  -> Alpaca paper launchd template
  -> launchd localization runbook
  -> launchd local preflight
  -> launchd manual full wrapper review
  -> launchd disabled load rehearsal
  -> launchd bootstrap failure diagnosis
  -> launchd controlled load rehearsal
  -> launchd triggered execution rehearsal design
  -> launchd preflight kickstart rehearsal
  -> launchd filesystem permission diagnosis
  -> launchd full wrapper rehearsal design
  -> launchd full wrapper rehearsal
  -> launchd recurring schedule activation design
  -> launchd recurring schedule activation
  -> first natural scheduled run review
```

## Data Lineage v1 Scope

When implemented, each ingest run should produce:

```text
raw provider artifact
normalized dataset
validation report artifact
dataset metadata artifact
```

The metadata should link:

- provider
- modality
- symbol
- request start/end
- raw path
- normalized path
- validation report path
- ingestion timestamp
- normalization version
- validation status

## Storage Abstraction v1 Scope

Introduce:

```text
MarketBarStore
CsvMarketBarStore
```

Keep CSV as the first implementation. Add Parquet later without changing
strategy or ingestion logic deeply.

## Feature Engineering v1 Scope

Start with simple technical features:

- daily returns
- rolling volatility
- moving averages
- momentum
- drawdown

Feature outputs should be artifacts with lineage back to the normalized dataset
and validation report that produced them.

## Strategy Feature Interface Scope

Introduce:

```text
FeatureData
FeatureStrategy
FeatureMomentumStrategy
```

Keep price-based strategies working. Feature-based strategies should consume a
named feature artifact and explicitly declare which feature columns drive their
signals, so later debugging can trace a backtest from result to signal columns
to feature file to normalized input data.

## Provider Reconciliation Scope

Introduce:

```text
ProviderReconciliationReport
ReconciliationDifference
quant data reconcile
```

The first version compares two normalized market-bar CSVs for one symbol. It
checks date coverage, required columns, duplicate dates, close-price
differences, and volume differences. Close mismatches are treated as errors;
coverage and volume mismatches start as warnings so they are visible without
blocking every exploratory run.

## Paper Trading Foundation Scope

Introduce:

```text
PaperBroker
OrderRequest
Order
Fill
Position
PortfolioSnapshot
RiskCheckResult
PaperTradeRecord
quant paper order
```

The first version supports deterministic market-order simulation at a supplied
price. It rejects impossible buys and sells, updates cash and positions, and
writes JSON audit records. It is not a live broker integration and does not yet
run strategies automatically on a schedule.

## Known v1 Follow-Ups

The `v1` label means the boundary exists and is useful, not that the area is
complete. Keep these follow-ups visible when planning future milestones.

| Area | Current v1 Limitation | Future Improvement |
| --- | --- | --- |
| Data validation | Checks one normalized market-bar CSV for one symbol at a time. | Add exchange calendars, expected session coverage, adjusted/unadjusted policy checks, split/dividend sanity checks, and configurable warning/error severity. |
| Data lineage | Ingestion writes metadata, but feature and backtest artifacts do not yet fully reference upstream artifact IDs. | Add stable dataset IDs and make feature artifacts, backtest summaries, paper trade records, and future live orders reference exact input artifacts. |
| Storage abstraction | `MarketBarStore` supports CSV only. | Add Parquet storage, partitioning by provider/symbol/date, schema version metadata, and migration checks. |
| Feature engineering | Only simple technical market-bar features are implemented. | Add feature metadata, lineage links, point-in-time guards, feature registry, multi-symbol features, and non-price modalities such as news sentiment. |
| Strategy feature interface | Feature strategies consume a CSV artifact and named columns, but there is no feature registry or feature schema contract yet. | Add declared feature requirements, compatibility checks, strategy parameter serialization, and richer signal audit records. |
| Provider reconciliation | Compares two normalized market-bar CSVs for one symbol. | Add multi-provider policies, canonical-source selection, adjusted-price comparison rules, calendar-aware coverage checks, reconciliation history, and severity configuration. |
| Paper trading | Simulates deterministic market orders but still omits slippage, fees, partial fills, and broker-specific behavior. | Model slippage/fees/partial fills, add order idempotency, and separate paper broker adapters from real broker adapters. |
| Paper signal execution | Uses the latest row of one price-based momentum strategy and local CSV data. | Support feature-based strategies, persisted strategy configs, multi-symbol runs, and data refresh steps before signal generation. |
| Broker state persistence | Persists one JSON paper account state file with atomic replacement and one previous backup. | Add account IDs, state history, reconciliation against audit records, and restore tooling. |
| Idempotent paper signals | Uses simple strategy/symbol/date/action keys and local JSON state. | Add account-scoped idempotency, signal revision IDs, configurable reprocessing policy, and reconciliation between skipped records and trade records. |
| Service deployment | Provides local wrapper and cron/systemd documentation, but no managed process or alerting. | Add health checks, structured logs, alert hooks, deployment-specific configs, and safer concurrent-run handling. |
| Operational observability | Provides a local read-only health command, but no notifications or health history. | Add alert hooks, structured health history, data freshness checks, lock/concurrency checks, and dashboard summaries. |
| Data refresh workflow | Refreshes one symbol from one provider before one paper-signal workflow. | Add multi-symbol workflows, provider reconciliation before execution, feature refresh, configurable freshness windows, and workflow retries. |
| Concurrent run safety | Adds one lock file around the refresh workflow. | Add lock status to health checks, account-scoped lock naming, lock cleanup tooling, and broader locking around future multi-workflow operations. |
| Atomic state writes | Uses same-directory temp files, fsync, atomic replace, and one `.bak` copy. | Add state history, restore command, checksums, and reconciliation against paper audit records. |
| Paper state reconciliation | Replays local paper signal records against one state file. | Integrate with health checks, add account IDs, state history, restore workflows, and richer drift diagnostics. |
| Health check integration | Reports lock and reconciliation status from `quant ops health`, but does not notify anyone. | Add alert hooks, health history, dashboard summaries, and data freshness checks. |
| Dashboard alert status | Publishes a sanitized `site/status.json` for GitHub Pages, but does not push notifications. | Add external alert hooks after the real-money trading path and broker boundary are designed. |
| Broker adapter boundary | Strategy execution can target a broker protocol, but only the paper adapter exists. | Add safety gates, broker credential boundaries, live adapter contracts, and account reconciliation before real orders. |
| Live trading safety gates | Adds fail-closed mode checks, but no live broker adapter uses them yet. | Require the guard in every future live-capable CLI command and adapter before credentials or orders are touched. |
| Dry-run broker adapter | Records manual intended orders, but strategy signals do not route to dry-run records yet. | Add scheduled dry-run signal execution and compare intended orders with paper decisions before live broker work. |
| Dry-run signal execution | Routes one latest strategy signal into a dry-run record, but does not run on a schedule yet. | Add scheduled dry-run execution, run records, idempotency policy, and comparison against paper signal records. |
| Dry-run scheduler | Runs dry-run signals on a finite scheduler loop, but does not compare against paper execution yet. | Add paper-vs-dry-run comparison reports to catch divergence before live broker work. |
| Paper vs dry-run comparison | Compares the latest paper signal and dry-run order, but is not part of health checks yet. | Integrate comparison status into operational health, dashboard status, and future alert routing. |
| Comparison health integration | Health and dashboard can show comparison status, but generating the comparison is still a separate step. | Compose dry-run signal execution, comparison generation, and status publishing into a repeatable workflow. |
| Dry-run refresh workflow | Refreshes one symbol, runs one dry-run strategy loop, and compares against the latest paper signal when one exists. | Add local/server wrapper configuration, multi-symbol runs, retries, and deployment-specific health publishing. |
| Dry-run server wrapper | Provides an env-driven wrapper for the dry-run refresh workflow, but still relies on cron/systemd and local files. | Add stronger scheduling supervision, deployment templates, health publishing automation, and alert hooks after live-trading boundaries are designed. |
| Live broker adapter design | Defines the real broker boundary, but no typed live audit models or fake broker tests exist yet. | Add typed live order/fill/account/reconciliation models and append-only artifact writers before any broker SDK integration. |
| Live audit models | Defines broker-neutral live audit records and JSON writers, but no fake broker client produces them yet. | Add a no-network fake live broker client and adapter tests before any real broker SDK integration. |
| Fake live broker client | Simulates immediate-fill live broker behavior with no network calls, but is not yet behind a live adapter boundary. | Add a fake-backed live adapter that enforces safety checks and writes audit artifacts through the live adapter interface. |
| Fake-backed live adapter | Enforces live safety checks and writes live audit artifacts through a fake client, but does not reconcile local artifacts against broker truth yet. | Add fake live reconciliation before any real broker SDK integration. |
| Fake live reconciliation | Compares local live artifacts with fake broker truth, but has no user-facing CLI command yet. | Add safety-gated fake live order and reconciliation CLI commands before any real broker SDK integration. |
| Fake live CLI | Exposes fake live order and reconciliation commands, but still has no external broker dependency. | Design the Alpaca paper adapter dependency boundary before adding `alpaca-py`. |
| Alpaca paper adapter design | Defines the first external broker adapter boundary, but no Alpaca-shaped mapping code exists yet. | Add Alpaca order/account/position mapping helpers and tests without installing `alpaca-py`. |
| Alpaca paper mapping | Maps Alpaca-shaped objects without installing the SDK, but no optional dependency or client wrapper exists yet. | Add `alpaca-py` as an optional dependency and verify import boundaries without credentials or network calls. |
| Alpaca optional dependency | Adds a lazy optional SDK boundary, but no SDK-backed paper client exists yet. | Implement an Alpaca paper client wrapper behind the live broker client protocol without enabling real-money trading. |
| Alpaca paper client | Wraps the optional SDK behind the live broker client protocol, but has no user-facing command yet. | Add explicit safety-gated Alpaca paper CLI commands and keep generic live broker routing out of scope. |
| Alpaca paper CLI | Can submit explicit safety-gated paper orders and snapshots, but does not reconcile local artifacts against Alpaca paper state yet. | Add Alpaca paper reconciliation and keep any default tests credential-free and network-free. |
| Alpaca paper reconciliation | Reconciles local artifacts against Alpaca paper state, but no human smoke-test runbook exists yet. | Add a manual runbook for one tiny paper order, snapshot, reconciliation, and artifact review before scheduling Alpaca workflows. |
| Alpaca paper smoke runbook | Documents the human-run smoke test, but scheduled Alpaca workflows are not designed yet. | Design the scheduled Alpaca paper workflow only after the runbook is reviewed and at least one broker-connected smoke run is understood. |
| Alpaca paper workflow design | Defines the scheduled workflow contract, but no workflow command exists yet. | Implement a finite lock-protected workflow command with fake-driven tests and no default broker network access in CI. |
| Alpaca paper refresh workflow | Adds one finite workflow command, but it still needs an operational wrapper before it is convenient to run frequently. | Add an env-driven wrapper, logs, and docs for server-style recurring execution. |
| Alpaca paper server wrapper | Provides an env-driven wrapper and logs, but health checks still focus on paper/dry-run status. | Surface Alpaca paper workflow and reconciliation status in operational health and dashboard output. |
| Alpaca paper operational health | Health and dashboard status can include Alpaca paper workflow/reconciliation status, but the wrapper does not publish status automatically. | Add wrapper-controlled dashboard publishing for the Alpaca paper server path. |
| CLI workflow | Commands are useful but mostly single-step. | Add composed workflows for ingest, validate, reconcile, feature build, backtest, and paper execution with shared run IDs. |
| CI and dependency management | CI installs from broad dependency ranges even though `uv.lock` exists. | Make CI use the lockfile or otherwise pin critical tool versions to reduce dependency drift between local and GitHub runs. |
| Scheduler loop | Runs finite tasks and writes run records, but does not yet supervise a long-running process. | Add retries, idempotency keys, structured logs, failure notifications, and service/cron deployment docs. |
| Server operation | No service process, health checks, or alerting yet. | Add service supervision, heartbeat records, health checks, structured logs, and failure notifications. |

## Scheduler Loop v1 Scope

Introduce:

```text
SchedulerRunner
ScheduledTaskResult
ScheduledRunRecord
quant schedule paper-order
```

The first scheduler runs a task once or for a finite number of iterations. It
writes one JSON run record per attempt and points each run record at task
artifacts, such as paper trade records. It is intentionally not a permanent
daemon yet.

## Paper Signal Execution v1 Scope

Introduce:

```text
PaperSignalDecision
PaperSignalRecord
decide_latest_signal
execute_latest_signal
quant schedule paper-signal
```

The first version converts the latest momentum strategy signal into a paper
decision. Entry signals buy, exit signals sell, and no signal records a hold.
It writes paper signal records and scheduler run records so the research-to-paper
path is auditable.

## Broker State Persistence v1 Scope

Introduce:

```text
PaperBrokerState
load_paper_broker_state
save_paper_broker_state
--state-path
```

The first version stores paper account cash and positions as JSON. Scheduled
paper signal runs load this state before generating orders and save the updated
state after each run, so separate process invocations can behave like one
continuous paper account.

## Idempotent Paper Signals v1 Scope

Introduce:

```text
PaperSignalDecision.idempotency_key
PaperBrokerState.processed_signal_keys
PaperSignalRecord.skipped
```

The first version prevents duplicate paper orders for the same strategy, symbol,
signal date, and action. Duplicate signals still produce paper signal records,
but those records are marked as skipped and do not change cash or positions.

## Service Deployment v1 Scope

Introduce:

```text
.env.example
scripts/run_paper_signal.sh
docs/deployment.md
logs/
```

The first version documents the operational contract for running the paper
signal loop as a recurring server job. It covers local runs, environment
configuration, log output, cron, and systemd-style deployment. It does not yet
include alerts, process supervision, locking, or cloud infrastructure.

## Operational Observability v1 Scope

Introduce:

```text
HealthReport
HealthIssue
quant ops health
docs/operations.md
```

The first version reads existing scheduler run records, paper signal records,
paper broker state, and wrapper logs. It reports `healthy`, `degraded`, or
`failed` without mutating account state or placing orders. It does not yet send
alerts, store health history, or check data freshness.

## Data Refresh Workflow v1 Scope

Introduce:

```text
DataRefreshWorkflowRecord
quant workflow paper-signal-refresh
scripts/run_paper_signal_refresh.sh
docs/workflows.md
```

The first version refreshes one market-bar dataset from one provider, writes raw
and normalized data, writes validation and metadata artifacts, stops if
validation fails, then runs the scheduled paper signal path. The workflow record
links data artifacts, scheduler run records, signal records, and state paths so
paper decisions can be traced back to their refreshed input data.

## Concurrent Run Safety v1 Scope

Introduce:

```text
RunLockRecord
FileLock
--lock-path
--lock-stale-after-seconds
```

The first version wraps the data-refresh paper-signal workflow with an atomic
lock file. If another run is active, the workflow fails before refreshing data
or touching paper state, and writes a failed workflow record. Stale locks can be
replaced after a configured timeout for crash recovery.

## Atomic State Writes v1 Scope

Introduce:

```text
same-directory temporary state file
fsync before replace
os.replace
state.json.bak
```

The first version writes paper broker state to a temporary file in the same
directory, flushes it to disk, atomically replaces the live state file, and keeps
one previous backup. If replacement fails, the previous live state file remains
intact and the temporary file is cleaned up.

## Paper State Reconciliation v1 Scope

Introduce:

```text
PaperStateReconciliationReport
PaperStateDifference
reconcile_paper_state
quant paper reconcile-state
```

The first version replays paper signal audit records from a known starting cash
and optional starting position. It compares expected cash, positions, and
processed signal keys against the persisted paper broker state, writes a JSON
report, and exits nonzero when drift is detected.

## Health Check Integration v1 Scope

Introduce:

```text
quant ops health --reconcile-state
lock status in HealthReport
reconciliation status in HealthReport
```

The first version keeps the basic health command read-only and adds optional
state reconciliation. It reports missing, active, stale, and invalid workflow
locks; active locks degrade health, stale or invalid locks fail health, and
failed paper-state reconciliation fails health.

## Dashboard Alert Status v1 Scope

Introduce:

```text
DashboardHealthStatus
quant ops publish-status
site/status.json
Operations Status dashboard panel
```

The first version converts the local health report into a public-safe status
artifact for the static GitHub Pages dashboard. It includes high-level run,
signal, lock, reconciliation, and issue status, but intentionally omits cash,
positions, order details, and sensitive strategy state.

By default, `quant ops publish-status` exits successfully even when the health
status is `failed`, so a server job can still publish a visible red dashboard
state. Use `--fail-on-failed` only when the publishing wrapper should stop on
failed health.

## Broker Adapter Boundary v1 Scope

Introduce:

```text
BrokerAdapter
SignalExecutionBroker
PaperBrokerAdapter
BrokerAccountSnapshot
docs/broker_adapters.md
```

The first version keeps the existing paper broker behavior and state format,
but routes scheduled signal execution through an adapter protocol. This gives
future live broker work a defined integration point without letting broker API
details leak into strategy code, scheduler code, or workflow orchestration.

This milestone does not add real broker connectivity. Real-money execution
should remain impossible until explicit safety gates, credential rules,
order-size limits, and live adapter tests exist.

## Live Trading Safety Gates v1 Scope

Introduce:

```text
TradingMode
TradingSafetyConfig
TradingSafetyCheck
assert_trading_allowed
quant safety check
docs/trading_safety.md
```

The first version fails closed by default. Paper and dry-run modes are allowed,
but live mode requires an explicit enable flag, exact confirmation phrase,
positive maximum order notional, and broker name. Environment variables use the
`QUANT_` prefix and missing variables never imply live-trading permission.

This milestone still does not add live broker connectivity. Its purpose is to
make future live-capable code call one central guard before it can construct a
broker client or submit an order.

## Dry-Run Broker Adapter v1 Scope

Introduce:

```text
DryRunBrokerAdapter
DryRunOrderRecord
DryRunOrderStatus
quant dry-run order
docs/dry_run_trading.md
```

The first version records manual would-submit market orders under
`data/dry_run/orders/`. It captures the intended order request, market price,
notional, broker name, and safety check result. It does not create fills, mutate
cash, mutate positions, or call any external broker API.

This milestone is a rehearsal of the broker submission shape. Strategy-to-dry
run execution belongs in the next milestone.

## Dry-Run Signal Execution v1 Scope

Introduce:

```text
execute_latest_signal_dry_run
quant dry-run signal
```

The first version reuses the same latest-signal decision logic as paper signal
execution. Buy and sell signals write `DryRunOrderRecord` artifacts under
`data/dry_run/orders/`; hold signals print that no dry-run order was intended
and do not write an order artifact.

This milestone does not mutate paper state, create fills, or call any external
broker API.

## Dry-Run Scheduler v1 Scope

Introduce:

```text
quant schedule dry-run-signal
data/scheduler/dry-run/
```

The first version runs latest-signal dry-run execution inside the existing
finite scheduler loop. Buy and sell signals write dry-run intended-order
artifacts and scheduler run records. Hold signals write scheduler run records
with no order artifacts.

This milestone still does not mutate paper state, create fills, or call any
external broker API.

## Paper vs Dry-Run Comparison v1 Scope

Introduce:

```text
PaperDryRunComparisonReport
PaperDryRunDifference
quant dry-run compare-paper
data/dry_run/comparison/latest.json
```

The first version compares one paper signal artifact with one dry-run order
artifact. It checks whether an order should exist, then compares side, symbol,
quantity, and market price within a tolerance. Paper hold or skipped signals
should not have a dry-run order.

The command writes a report and exits nonzero when divergence is found. It is
read-only and does not execute orders, mutate paper state, or call any external
broker API.

## Comparison Health Integration v1 Scope

Introduce:

```text
quant ops health --check-comparison
comparison status in HealthReport
comparison status in DashboardHealthStatus
dashboard Comparison panel field
```

The first version reads an existing paper-vs-dry-run comparison report and
surfaces its status in operational health and the static dashboard status JSON.
Failed comparison reports fail health. Missing comparison reports are warnings
when comparison checking is explicitly requested.

This milestone does not generate comparison reports automatically. It only makes
existing comparison artifacts visible in the same operational channel as
scheduler status, workflow locks, and paper-state reconciliation.

## Dry-Run Refresh Workflow v1 Scope

Introduce:

```text
run_dry_run_refresh_workflow
quant workflow dry-run-refresh
data/workflows/dry-run-refresh/
```

The first version composes the dry-run server path into one command. It
refreshes and validates provider market data, runs scheduled dry-run signal
execution, writes a paper-vs-dry-run comparison report when paper signal
artifacts exist, and can publish a sanitized dashboard status file.

The workflow writes a durable record that links the ingest artifacts, scheduler
run records, dry-run order records, comparison report, and optional dashboard
status file. It fails fast when data validation fails or when the comparison
detects divergence.

This milestone does not submit broker orders, create fills, mutate paper broker
state, or define the server wrapper that will run the workflow repeatedly.

## Dry-Run Server Wrapper v1 Scope

Introduce:

```text
scripts/run_dry_run_refresh.sh
QUANT_DRY_RUN_* environment settings
dry-run cron/systemd deployment notes
```

The first version gives the dry-run refresh workflow the same deployment shape
as the paper refresh workflow. The wrapper loads `.env`, runs
`quant workflow dry-run-refresh`, writes a timestamped log, and keeps dry-run
orders, dry-run scheduler records, comparison reports, workflow records, and
lock files in separate default paths.

This milestone still does not submit broker orders. It is an operational
rehearsal layer for running the live-shaped path frequently before credentials
or real order APIs are introduced.

## Live Broker Adapter Design v1 Scope

Introduce:

```text
docs/live_broker_adapter.md
docs/live_broker_api_research.md
live adapter credential boundary
live adapter audit and reconciliation requirements
```

The first version defines what a future real broker adapter must do before any
broker SDK or credential path is added. It covers the adapter contract,
credential rules, safety gates, idempotency, audit artifacts, account
reconciliation, CLI boundaries, and a conservative implementation order.

This milestone does not add credentials, broker dependencies, network calls,
live order submission, live fills, or any command that can place a real order.

The companion research report recommends keeping the next implementation
broker-neutral, then using Alpaca paper trading as the first external broker
integration candidate after fake-client and audit-artifact tests exist.

## Live Audit Models v1 Scope

Introduce:

```text
LiveOrderRecord
LiveFillRecord
LiveAccountSnapshot
LiveReconciliationReport
data/live/orders/
data/live/fills/
data/live/account_snapshots/
data/live/reconciliation/
```

The first version adds broker-neutral typed records for future live order
attempts, broker fills, sanitized account snapshots, and reconciliation reports.
It also adds append-only JSON artifact writers so every future live adapter can
write the same local audit trail before any broker-specific behavior leaks into
the rest of the system.

This milestone does not add credentials, broker dependencies, broker clients,
network calls, live order submission, live fills, or any command that can place
a real order.

## Fake Live Broker Client v1 Scope

Introduce:

```text
LiveBrokerClient
FakeLiveBrokerClient
```

The first version adds a no-network fake broker client that returns the live
audit records expected from future broker integrations. It simulates immediate
market-order fills, rejected buys with insufficient buying power, rejected sells
with insufficient position, sanitized account snapshots, broker order IDs,
execution IDs, and idempotent client order IDs.

This milestone does not add credentials, broker dependencies, network calls,
CLI commands, live order submission, or any real broker adapter.

## Fake-Backed Live Adapter v1 Scope

Introduce:

```text
LiveBrokerAdapter
LiveBrokerClient-backed submit_market_order
optional live order/fill/snapshot artifact writing
```

The first version wraps the no-network fake broker client behind the same
adapter boundary future broker integrations should use. It enforces an allowed
`TradingMode.LIVE` safety check before client submission, delegates market
orders to the client, exposes snapshots/open orders/fills, and can write live
order, fill, and account snapshot artifacts.

This milestone does not add credentials, broker dependencies, network calls,
CLI commands, live order submission, or a real broker SDK adapter.

## Fake Live Reconciliation v1 Scope

Introduce:

```text
reconcile_live_state
load_live_order_records
load_live_fill_records
latest_live_account_snapshot
```

The first version compares local live audit artifacts against the no-network
fake broker client's open orders, fills, and account snapshot. It reports
missing fills, cash drift, buying-power drift, and position drift through a
`LiveReconciliationReport`, and it can write that report under
`data/live/reconciliation/latest.json`.

This milestone is read-only. It does not add credentials, broker dependencies,
network calls, CLI commands, live order submission, cancellation, or account
mutation.

## Fake Live CLI v1 Scope

Introduce:

```text
quant live fake-order
quant live fake-reconcile
```

The first version exposes the fake live path through explicit `live`
subcommands. `fake-order` requires live safety gates, uses the no-network fake
broker client through `LiveBrokerAdapter`, and writes live order, fill, and
account snapshot artifacts. `fake-reconcile` rebuilds deterministic fake broker
truth from the same command inputs, compares local artifacts with
`reconcile_live_state`, writes a reconciliation report, and exits nonzero on
drift.

This milestone does not add credentials, broker dependencies, network calls,
real live order submission, or an external broker SDK adapter.

## Alpaca Paper Adapter Design v1 Scope

Introduce:

```text
docs/alpaca_paper_adapter.md
AlpacaPaperConfig design
AlpacaTradingClientProtocol design
Alpaca status/order/account mapping plan
```

The first version designs how Alpaca paper trading should fit behind the
existing `LiveBrokerClient`, `LiveBrokerAdapter`, live audit artifact, and live
reconciliation boundaries. It defines environment variables, dependency
boundaries, order/status/fill/account mapping rules, test requirements, and an
implementation order.

This milestone does not add `alpaca-py`, credentials, broker network calls, CLI
commands that contact Alpaca, or a real broker adapter.

## Alpaca Paper Mapping v1 Scope

Introduce:

```text
src/quant/execution/alpaca_paper.py
AlpacaPaperConfig
AlpacaTradingClientProtocol
AlpacaMarketOrderRequest
map_order_request_to_alpaca_market_order
map_alpaca_order_status
map_alpaca_order_record
map_alpaca_fill_records
map_alpaca_account_snapshot
map_alpaca_position
```

The first version uses fake Alpaca-shaped objects in tests instead of importing
the Alpaca SDK. It maps internal order requests to a market-order request
shape, normalizes broker order statuses, converts Alpaca-shaped order objects
into broker-neutral live order records, derives fill records when filled order
data is present, and converts account and position objects into internal
snapshots.

This milestone intentionally does not add SDK installation, credential loading,
network calls, CLI commands, or a constructed Alpaca client. Those belong in
the next milestones after the translation layer is stable.

## Alpaca Optional Dependency v1 Scope

Introduce:

```text
pyproject.toml broker-alpaca extra
uv.lock optional alpaca-py resolution
src/quant/execution/alpaca_sdk.py
AlpacaTradingSdk
load_alpaca_trading_sdk
build_alpaca_sdk_market_order_request
```

The first version adds `alpaca-py` as an optional dependency only. Default
installation, default CI, and default imports should continue to work without
Alpaca credentials, network access, or the optional SDK installed.

The SDK boundary is intentionally lazy. Normal imports such as
`import quant.execution` must not import any `alpaca.*` modules. Alpaca SDK
classes are loaded only through `load_alpaca_trading_sdk`, which gives a clear
install hint when the optional extra is missing.

This milestone does not construct a `TradingClient`, read credentials, submit
orders, fetch account state, add CLI commands, or call Alpaca over the network.
Those belong in the Alpaca paper client milestone.

## Alpaca Paper Client v1 Scope

Introduce:

```text
AlpacaPaperBrokerClient
trading_client_for_testing
SDK-backed TradingClient construction with paper=True
submit_market_order
account_snapshot
open_orders
fills
```

The first version wraps the optional Alpaca SDK behind the existing
`LiveBrokerClient` protocol. It constructs `TradingClient` with `paper=True`
when no test client is injected, translates internal order requests into SDK
market-order request objects, maps submitted orders into broker-neutral live
order records, remembers fill records returned from order responses, maps
account snapshots and positions, and maps known open orders by client order ID.

Tests use fake SDK and fake trading-client objects only. Default CI should not
need Alpaca credentials, an installed optional extra, network access, or an
Alpaca account.

This milestone does not add environment credential loading, CLI commands,
scheduled Alpaca workflows, broker reconciliation against Alpaca, streaming
trade updates, or any real-money trading path.

## Alpaca Paper CLI v1 Scope

Introduce:

```text
quant live alpaca-paper-order
quant live alpaca-paper-snapshot
QUANT_ALPACA_PAPER_API_KEY
QUANT_ALPACA_PAPER_SECRET_KEY
QUANT_ALPACA_PAPER_ACCOUNT_ID
QUANT_ALPACA_PAPER_URL_OVERRIDE
```

The first version exposes the Alpaca paper client through explicit `live`
subcommands. `alpaca-paper-order` requires the existing live safety gates,
loads explicit paper-only credentials from environment variables, validates
order notional against the configured safety limit, submits a market order
through `AlpacaPaperBrokerClient`, and writes live order, fill, and account
snapshot artifacts. `alpaca-paper-snapshot` uses the same safety gate and
credential boundary to fetch and persist a sanitized account snapshot.

Missing safety approval or missing Alpaca paper credentials must fail before
constructing the Alpaca paper client. Tests use fake clients only; default CI
does not need Alpaca credentials, an installed optional extra, network access,
or an Alpaca account.

This milestone does not add a generic broker selector, scheduled Alpaca
workflows, broker reconciliation against Alpaca, streaming trade updates, or
any real-money trading path.

## Alpaca Paper Reconciliation v1 Scope

Introduce:

```text
quant live alpaca-paper-reconcile
AlpacaPaperBrokerClient.remember_order_record
AlpacaPaperBrokerClient.fills polling refresh
```

The first version reconciles local live order, fill, and account snapshot
artifacts against current Alpaca paper broker truth through the existing
`reconcile_live_state` contract. The CLI command uses the same live safety
gates and paper-only Alpaca environment variables as the order and snapshot
commands, writes `data/live/reconciliation/latest.json` by default, prints all
differences, and exits nonzero when drift is detected.

Because reconciliation usually runs in a fresh process, the Alpaca paper client
can remember local order-record context before polling Alpaca orders. That
context lets filled Alpaca orders be mapped back into broker-neutral fill
records for comparison.

Tests use fake clients only. Default CI does not need Alpaca credentials, an
installed optional extra, network access, or an Alpaca account.

This milestone does not add scheduled Alpaca workflows, streaming trade
updates, automated recovery, or any real-money trading path.

## Alpaca Paper Manual Smoke Runbook v1 Scope

Introduce:

```text
docs/alpaca_paper_smoke_runbook.md
```

The first version documents a human-run broker-connected smoke test before any
scheduled Alpaca workflow is designed. It covers optional SDK installation,
paper-only credential environment variables, live safety environment variables,
a blocked safety check, a baseline snapshot, one tiny Alpaca paper order,
reconciliation, artifact review, cleanup, and stop criteria.

The runbook is intentionally manual. It should be reviewed and, ideally, run
once against an Alpaca paper account before adding scheduled Alpaca workflows.

This milestone does not add scheduled Alpaca workflows, automation wrappers,
new broker behavior, or any real-money trading path.

## Alpaca Paper Workflow Design v1 Scope

Introduce:

```text
docs/alpaca_paper_workflow.md
```

The first version designs a future finite, lock-protected
`quant workflow alpaca-paper-refresh` command. It defines the preconditions,
execution order, safety policy, deterministic client order ID policy, artifact
contract, dashboard publishing policy, non-goals, and the next implementation
milestone.

This milestone is design-only. It does not add a workflow command, scheduled
Alpaca execution, automation wrappers, broker retries, or any real-money
trading path.

## Alpaca Paper Refresh Workflow v1 Scope

Introduce:

```text
run_alpaca_paper_refresh_workflow
quant workflow alpaca-paper-refresh
data/workflows/alpaca-paper-refresh/
data/locks/alpaca-paper-refresh.lock
```

The first version refreshes and validates one symbol, derives the latest
momentum signal, submits one actionable signal through the explicit Alpaca
paper client boundary, writes live order/fill/account snapshot artifacts, then
reconciles local artifacts against broker truth. The workflow is finite and
lock-protected, so a future scheduler can call it repeatedly without embedding
daemon behavior inside the trading logic.

Tests use fake provider and fake broker clients only. Default CI should not
need Alpaca credentials, an installed optional extra, network access, or an
Alpaca account.

This milestone does not add a server wrapper, automatic broker retries,
dashboard publishing for Alpaca paper health, generic broker selection, or any
real-money trading path.

## Alpaca Paper Server Wrapper v1 Scope

Introduce:

```text
scripts/run_alpaca_paper_refresh.sh
QUANT_ALPACA_PAPER_* workflow path variables
logs/alpaca-paper-refresh-*.log
```

The first version mirrors the dry-run server wrapper: load `.env`, run
`quant workflow alpaca-paper-refresh --from-env`, keep paths configurable from
environment variables, and write timestamped logs. It remains a wrapper around
a finite workflow, not a retrying broker daemon.

This milestone does not add broker retries, generic broker selection, alert
hooks, or any real-money trading path.

## Alpaca Paper Operational Health v1 Scope

Introduce:

```text
Alpaca paper workflow health inputs
Alpaca paper reconciliation health inputs
dashboard status fields for broker-paper health
```

The first version should let local health checks and the static dashboard show
whether the latest Alpaca paper workflow completed, whether reconciliation
passed, and where the latest safe artifacts live. It should not publish account
secrets, raw broker payloads, or full account details.

## Alpaca Paper Status Publishing Wrapper v1 Scope

Introduce:

```text
QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH
QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN
```

The first version should let `scripts/run_alpaca_paper_refresh.sh` optionally
run `quant ops publish-status --check-alpaca-paper` after the workflow finishes,
so the GitHub Pages dashboard can show the broker-paper lane without a separate
manual command. Publishing should remain sanitized and should not send external
alerts.

This milestone does not enable publishing by default, send external alerts,
retry broker submissions, or add any real-money trading path.

## Alpaca Paper Manual Smoke Execution v1 Scope

Introduce:

```text
docs/alpaca_paper_smoke_execution.md
artifact review checklist results
go/no-go note for recurring Alpaca paper scheduling
```

The first version should execute the existing manual smoke runbook against the
intended Alpaca paper account, review the generated order/fill/snapshot/
reconciliation/workflow/status artifacts, and record what happened without
committing secrets or raw broker payloads.

The first execution submitted one tiny Alpaca paper order, observed manual
dashboard cancellation before any fill, added a broker-state refresh command
for externally changed orders, and confirmed reconciliation passes after local
artifacts are refreshed from broker truth.

## Controlled Recurring Alpaca Paper Run v1 Scope

Introduce:

```text
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY
preflight wrapper log
controlled recurring run guidance
```

The first version should let the Alpaca paper server wrapper prove its resolved
configuration without contacting Alpaca or submitting a paper order. The
preflight command is intended for cron/systemd/path changes, server moves, and
first-run checks before enabling broker-connected paper execution.

This milestone does not enable recurring execution automatically, increase
order size, retry broker submissions, or add real-money trading.

## Controlled Full Alpaca Paper Wrapper Run v1 Scope

Introduce:

```text
docs/alpaca_paper_wrapper_run.md
full wrapper log review
workflow/reconciliation artifact review
```

The first full wrapper run should execute `scripts/run_alpaca_paper_refresh.sh`
without preflight, inspect generated logs and artifacts, and record what
happened without committing local operational data. The first recorded run
refreshed yfinance market data, wrote an Alpaca paper account snapshot, and
reconciled successfully with zero differences. No new order or fill artifact was
created by that run, which means an actionable broker submission still needs to
be observed in a later controlled wrapper run.

This milestone does not enable recurring execution automatically, increase
order size, force a trade, retry broker submissions, or add real-money trading.

## Workflow Decision Visibility v1 Scope

Introduce:

```text
latest_signal_action
latest_signal_reason
latest_signal_market_price
broker_submission_attempted
broker_submission_skipped_reason
order/fill/snapshot artifact path groups
reconciliation_report_path
```

The first version should make Alpaca paper workflow records self-explanatory.
A successful workflow can now show whether it held without submitting an order
or attempted broker submission and reconciled the resulting artifacts. This
removes the need to infer trading behavior from missing order or fill files.

## Dashboard Decision Visibility v1 Scope

Introduce:

```text
alpaca_paper_latest_signal_action
alpaca_paper_latest_signal_reason
alpaca_paper_latest_signal_market_price
alpaca_paper_broker_submission_attempted
alpaca_paper_broker_submission_skipped_reason
alpaca_paper_order/fill/snapshot artifact counts
```

The first version should copy sanitized Alpaca paper decision fields from the
latest workflow record into `site/status.json` and render them on the static
dashboard. It should publish counts and decision status, not account IDs,
secrets, cash, positions, raw broker payloads, or raw order details.

## Paper/Scheduler Status Cleanup v1 Scope

Introduce:

```text
check_paper_service
--no-check-paper-service
Alpaca-only dashboard publishing mode
```

The first version should let `quant ops publish-status` intentionally skip the
older local paper scheduler/signal/state lane when it is not the active
operational path. This keeps inactive or stale fixtures from making the
dashboard look failed while Alpaca paper workflow and reconciliation checks are
healthy.

## Recurring Alpaca Paper Schedule Design v1 Scope

Introduce:

```text
docs/alpaca_paper_schedule.md
daily paper rehearsal policy
pre-enable checklist
cron/launchd drafts
```

The first version should document when and how the Alpaca paper wrapper may be
scheduled without enabling any recurring job. The recommended first policy is
one paper-only run per market weekday near the end of the regular US market
session, with dashboard publishing enabled and tiny order sizing.

## Alpaca Paper launchd Template v1 Scope

Introduce:

```text
configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example
launchd template validation test
template review instructions
```

The first version should provide a disabled macOS launchd plist template that
uses placeholder absolute paths and the reviewed weekday 12:55 PM local policy.
It must not install, load, or enable the recurring job.

## Launchd Localization Runbook v1 Scope

Introduce:

```text
docs/launchd_localization.md
configs/launchd/*.local.plist gitignore rule
launchd load/unload safety commands
```

The first version should document how to copy the disabled launchd example to a
local untracked plist, replace machine-specific paths, validate with `plutil`,
run wrapper preflight, and later load or unload launchd only after explicit
review.

## Launchd Local Preflight v1 Scope

Introduce:

```text
local untracked launchd plist copy
plutil validation output
wrapper preflight output
no launchd load or enable action
docs/launchd_local_preflight.md
```

The first version should create the local machine-specific plist from the
checked-in example, verify that git ignores it, validate it with `plutil`, and
run `QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true bash scripts/run_alpaca_paper_refresh.sh`.
It must not load, enable, or kickstart launchd.

## Launchd Manual Full Wrapper Review v1 Scope

Introduce:

```text
manual full wrapper output
fresh Alpaca-only dashboard status
local launchd plist remains disabled and unloaded
docs/launchd_manual_wrapper_review.md
```

The first version should run `bash scripts/run_alpaca_paper_refresh.sh` from
the localized repo environment, publish dashboard status with
`--no-check-paper-service --no-check-comparison --check-alpaca-paper`, and
review the generated workflow/reconciliation/status artifacts. It must not
load, enable, or kickstart launchd.

## Launchd Disabled Load Rehearsal v1 Scope

Introduce:

```text
launchctl bootstrap with Disabled=true
launchctl print inspection
launchctl bootout cleanup
no enable action
no scheduled run
docs/launchd_disabled_load_rehearsal.md
```

The first version should confirm that launchd can parse and register the local
plist while it remains disabled. It should inspect launchctl state, unload the
job, and record the outcome. It must not enable the job or leave it loaded.

Current outcome: launchd returned bootstrap error 5 for both the repo-local
plist and the copy installed under `~/Library/LaunchAgents`. The service was
not loaded, the installed copy was removed, and the recurring schedule remains
disabled.

## Launchd Bootstrap Failure Diagnosis v1 Scope

Introduce:

```text
minimal launchd control plist
wrapper-free launchd command probe
launchd stderr/stdout path validation
background task management diagnostics
documented root cause or narrowed blocker
```

The first version should isolate whether bootstrap error 5 comes from the plist
shape, the wrapper path, log path permissions, macOS Background Task Management,
or another launchd requirement. It must keep the Alpaca paper job disabled and
must not submit orders through launchd.

Current outcome: the root cause was `Disabled=true`. Minimal and real-shaped
diagnostic plists loaded when `Disabled` was absent or set to `false`, and
reported `runs = 0` before being unloaded.

## Launchd Controlled Load Rehearsal v1 Scope

Introduce:

```text
installed launchd plist with Disabled=false
launchctl bootstrap actual label
launchctl print inspection
launchctl bootout cleanup
no kickstart action
no immediate order submission
docs/launchd_controlled_load_rehearsal.md
```

The first version should prove the actual Alpaca paper launchd label can be
registered once the plist is intentionally made loadable. It should inspect
the registered calendar triggers and unload the job before the schedule is
left active. It must not call `launchctl kickstart`.

Current outcome: the actual label loaded successfully from
`~/Library/LaunchAgents`, launchd reported `state = not running`, `runs = 0`,
and five weekday calendar triggers. The job was unloaded and the installed
plist was removed.

## Launchd Triggered Execution Rehearsal Design v1 Scope

Introduce:

```text
launchd-triggered execution risk review
preflight-only launchd execution option
manual kickstart guardrails
artifact and dashboard review checklist
explicit no-real-money boundary
docs/launchd_triggered_execution_rehearsal_design.md
```

The first version should decide how to test execution through launchd without
surprising order submission. It should likely prefer a preflight-only launchd
environment first, then require a separate review before any real wrapper
`kickstart`.

Current outcome: the design selects a preflight-only `kickstart` using
`EnvironmentVariables:QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true` in the installed
plist. The expected result is one wrapper log and no data refresh, broker
access, order artifacts, reconciliation artifacts, or dashboard publish.

## Launchd Preflight Kickstart Rehearsal v1 Scope

Introduce:

```text
installed launchd plist with Disabled=false
launchd EnvironmentVariables preflight guard
launchctl bootstrap actual label
launchctl kickstart actual label
launchctl print inspection after run
preflight log review
launchctl bootout cleanup
no full workflow execution
docs/launchd_preflight_kickstart_rehearsal.md
```

The first version should run launchd through the wrapper process boundary with
`QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true`. It should verify the log contains
`preflight completed without broker submission`, confirm no order or workflow
artifacts were created, then unload and remove the installed plist.

Current outcome: launchd executed one `kickstart`, but `/bin/bash` exited with
code `126` before the wrapper ran because macOS returned `Operation not
permitted` for the repo path under `Documents`. No wrapper log or trading
artifacts were created.

## Launchd Filesystem Permission Diagnosis v1 Scope

Introduce:

```text
macOS protected-folder access diagnosis
minimal launchd script execution probe
repo path relocation or permission options
preflight-only retry plan
no full workflow execution
```

The first version should determine whether macOS privacy controls for
`Documents`, launchd's execution context, or another filesystem permission is
blocking `/bin/bash` from reading the wrapper script. It should recommend the
least surprising fix before retrying launchd execution.

Current outcome: a runtime clone at `/Users/ziyuan/Code/quant-system-runtime`
was created with its own Git remote, `.env`, localized launchd plist, and fresh
virtualenv. Launchd preflight kickstart from that runtime clone succeeded with
`runs = 1`, `last exit code = 0`, and no trading artifacts.

## Launchd Full Wrapper Rehearsal Design v1 Scope

Introduce:

```text
non-preflight launchd risk review
runtime clone readiness checklist
artifact baseline checklist
Alpaca paper-only boundary
post-run reconciliation and dashboard review
bootout cleanup plan
docs/launchd_full_wrapper_rehearsal_design.md
```

The first version should decide how to run one launchd-triggered full wrapper
cycle from `/Users/ziyuan/Code/quant-system-runtime` without leaving a schedule
loaded. It must remain Alpaca paper only and require review before the actual
non-preflight `kickstart`.

Current outcome: the design requires a runtime-clone readiness check, paper-only
environment review, artifact baselines, exactly one `kickstart`, reconciliation
review, and immediate unload/removal of the installed plist.

## Launchd Full Wrapper Rehearsal v1 Scope

Introduce:

```text
runtime clone readiness check
artifact baseline before launchd run
installed plist with Disabled=false
no preflight environment override
exactly one launchctl kickstart
workflow and reconciliation review
launchctl bootout cleanup
docs/launchd_full_wrapper_rehearsal.md
```

The first version should execute the reviewed full-wrapper design once from
`/Users/ziyuan/Code/quant-system-runtime`. It should remain Alpaca paper only,
record the launchd and artifact outcome, unload the job, and remove the
installed plist.

Current outcome: the launchd-triggered full wrapper run succeeded with
`runs = 1`, `last exit code = 0`, `preflight_only=false`, workflow status
`succeeded`, latest signal `hold`, no broker submission, one account snapshot,
and reconciliation `passed` with zero differences. The job was unloaded and the
installed plist removed.

## Launchd Recurring Schedule Activation Design v1 Scope

Introduce:

```text
recurring schedule activation risk review
runtime clone update policy
installed plist ownership and rollback rules
post-run monitoring checklist
dashboard/status publication decision
missed-run and failed-run response plan
```

The first version should decide the exact conditions for leaving the launchd
job loaded so the weekday 12:55 schedule can run unattended. It should remain
Alpaca paper only and require a separate review before activation.

Current outcome: the activation design defines runtime-clone update policy,
paper-only preconditions, activation commands, first scheduled-run review,
monitoring checklist, rollback commands, stop conditions, dashboard publishing
policy, and missed-run handling.

## Launchd Recurring Schedule Activation v1 Scope

Introduce:

```text
runtime clone readiness check
installed plist with Disabled=false
launchctl bootstrap without kickstart
launchctl print activation inspection
first scheduled-run review plan
rollback commands ready
docs/launchd_recurring_schedule_activation.md
```

The first version should activate the schedule from
`/Users/ziyuan/Code/quant-system-runtime` and leave it loaded for the next
natural weekday 12:55 PM run. It must not call `kickstart` during activation.

Current outcome: launchd loaded the runtime-clone plist successfully and is
waiting idle with `runs = 0`, `last exit code = (never exited)`, and weekday
12:55 calendar triggers. No `kickstart` was run.

## First Natural Scheduled Run Review v1 Scope

Introduce:

```text
launchctl state after natural run
launchd stdout/stderr review
latest wrapper log review
workflow record review
reconciliation review
dashboard status review
keep-loaded or rollback decision
```

The first version should inspect the first scheduled launchd run after
activation. It should verify launchd exit code, workflow status,
reconciliation status, broker submission outcome, and dashboard status before
deciding whether to keep the schedule loaded.
