# Architecture Documentation — quant-system

## System Overview

The system is a layered quantitative research and execution platform with **two parallel execution lanes**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         quant-system                                 │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  Data Layer  │    │ Feature Layer│    │  Strategy Layer      │   │
│  │ yfinance     │───▶│ MA, vol,    │───▶│ Signal strategies    │   │
│  │ CSV loader   │    │ momentum,   │    │ Target strategies    │   │
│  │ normalizers  │    │ drawdown    │    │                      │   │
│  └──────────────┘    └──────────────┘    └──────────┬───────────┘   │
│                                                      │              │
│                          ┌───────────┬──────────────┐│              │
│                          │  LEGACY  │ SEMANTIC     ││              │
│                          │  LANE   │   LANE       ││              │
│                          │         │              ││              │
│     ┌────────────────────┤  SIGNAL  │  TARGET      ││              │
│     │                    ┤---------│  -----------  ││              │
│     │                    │ entry/  │ strategy     ││              │
│     │                    │ exit    │ → portfolio  ││              │
│     │                    │ signals │ → risk →     ││              │
│     │                    │         │ → lifecycle  ││              │
│     │                    └────┬────┘              ││              │
│     │                         │                   ││              │
│     │                    ┌────▼────┐       ┌──────▼──────┐       │
│     │                    │PaperBroker│      │Execution    │       │
│     │                    │(legacy)  │      │Lifecycle     │       │
│     │                    └────┬────┘       └──────┬──────┘       │
│     │                         │                   │              │
│     │                    ┌────▼───────────────────▼──────┐       │
│     │                    │    Broker Abstraction Layer    │       │
│     │                    │  Paper  │ DryRun  │ Live      │       │
│     │                    │  (local)│ (local) │ (Alpaca)  │       │
│     │                    └─────────┴───────────┴──────────┘       │
│     │                                                            │
│  ┌──▼────────────────────────────────────────────────────┐       │
│  │              Scheduler & Workflows                    │       │
│  │  (finite loops, lock files, audit records)            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────────────┐     │
│  │  Health  │  │ Web Console│  │  Operations Dashboard    │     │
│  │  Checks  │  │ (FastAPI)  │  │  (static site / GitHub   │     │
│  │          │  │            │  │   Pages)                 │     │
│  └──────────┘  └────────────┘  └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

## Two Execution Lanes

### Lane 1: Legacy Signal-Oriented

Strategies produce boolean entry/exit signals. These are converted to BUY/SELL/HOLD actions and executed against a paper or dry-run broker.

```
PriceData → Strategy → SignalFrame → decide_latest_signal()
  → PaperSignalAction → execute_latest_signal()
  → PaperBroker/DryRunBroker → audit records
```

This lane is fully wired to the CLI, scheduler, and recurring workflows.

### Lane 2: Semantic-Target

Strategies produce signed decimal position targets (e.g., +5 = long 5 shares, -3 = short 3, 0 = flat). These go through a multi-stage pipeline:

```
StrategyTargetDecision → ContributorSet (portfolio aggregation)
  → RiskTargetDecision → ExecutionPlan claim
  → ExecutionLifecycle (planned → submitted → filled → satisfied)
  → broker reconciliation
```

This lane is API-only, not connected to CLI or scheduler.

## Layer-by-Layer Breakdown

### Data Layer

```
DataProvider (protocol)
  ├── YFinanceMarketBarProvider (concrete: fetches OHLCV from yfinance)
  └── [future: news, filing, social_post providers]

RawDataset → normalize_market_bars() → MarketBar

MarketBarStore (protocol)
  ├── CsvMarketBarStore (concrete: writes to CSV)
  └── [future: ParquetMarketBarStore]

data/raw/          ← raw provider output
data/normalized/   ← normalized modality datasets
data/validation/   ← validation reports
data/metadata/     ← dataset metadata
```

Key principle: **ingestion is modality-agnostic, normalization is modality-specific.** The system supports market_bars, news_article, filing, and social_post modalities, but only market_bars via yfinance is implemented.

### Feature Layer

```
NormalizedMarketBars → build_technical_features() → FeatureData
  → data/features/technical/SYMBOL.csv
```

Features computed: daily_return, log_return, MA_fast, MA_slow, volatility, momentum, drawdown.

### Strategy Layer

Two protocol families:

```
Strategy (protocol)          FeatureStrategy (protocol)
  → PriceData                   → FeatureData
  → generate_signals()          → generate_signals_from_features()
  → SignalFrame                 → SignalFrame

TargetStrategy (protocol)    FeatureTargetStrategy (protocol)
  → PriceData                   → FeatureData
  → generate_targets()          → generate_targets_from_features()
  → StrategyTargetFrame         → StrategyTargetFrame
```

Concrete strategies:
- `MomentumStrategy` — moving average crossover (legacy, price-based)
- `FeatureMomentumStrategy` — moving average crossover using precomputed features

### Execution Layer

The execution layer is the most complex part. It uses the **adapter pattern** extensively:

```
BrokerAdapter (protocol)          SignalExecutionBroker (extends BrokerAdapter)
  ├── PaperBrokerAdapter           ├── PaperBrokerAdapter
  ├── DryRunBrokerAdapter          └── DryRunBrokerAdapter
  └── LiveBrokerAdapter

LiveBrokerClient (protocol)
  ├── FakeLiveBrokerClient (test double, no network)
  ├── AlpacaPaperBrokerClient (real Alpaca paper API)
  └── SemanticPaperBrokerClient (durable local paper broker)

ExecutionLifecycleBroker (protocol) — for semantic-target lane
ExecutionLifecycleStateReader (read-only variant)
```

**PaperBroker** — deterministic in-memory broker. Tracks cash, positions, processed signals. State persisted atomically with `.bak` backup.

**DryRunBrokerAdapter** — records intended orders without submission. Pure local simulation.

**LiveBrokerAdapter** — wraps any `LiveBrokerClient` and adds artifact writing (order records, fill records, account snapshots).

**SemanticPaperBrokerClient** — separate from legacy PaperBroker. Supports signed positions (long and short), covers, reversals. Durable with file locking and restart-safe recovery.

### Scheduler & Workflow Layer

```
SchedulerRunner (finite loop, not a daemon)
  → ScheduledRunRecord
  → task artifacts

Workflows (composable operational paths):
  ├── paper-signal-refresh: data refresh → validation → paper signal → workflow record
  ├── dry-run-refresh: data refresh → dry-run signal → comparison → workflow record
  └── alpaca-paper-refresh: data refresh → validation → momentum signal → target position → broker submit → reconcile → workflow record
```

Lock files prevent overlapping runs:
- `data/locks/paper-signal-refresh.lock`
- `data/locks/dry-run-refresh.lock`
- `data/locks/alpaca-paper-refresh.lock`

Stale locks (default: 7200 seconds) are recoverable via `os.kill(pid, 0)` check.

### Operations Layer

```
HealthReport ← reads from:
  ├── data/scheduler/latest/     (scheduler run records)
  ├── data/paper/signals/        (paper signal records)
  ├── data/paper/state/          (persisted paper state)
  ├── logs/                       (wrapper logs)
  └── data/locks/                 (lock status)

HealthStatus: healthy | degraded | failed
```

Publishes sanitized status to `site/status.json` for the static dashboard.

### Web Console

```
FastAPI app (read-only)
  ├── Authentication: Tailscale identity (recommended) or API key
  ├── /api/v1/overview       — sanitized system overview
  ├── /api/v1/accounts       — account data (all lanes)
  ├── /api/v1/decisions      — automatic decisions
  ├── /api/v1/incidents      — incident list
  ├── /api/v1/research/*     — research families and candidates
  ├── /api/v1/docs/*         — documentation index
  └── /api/v1/operations/*   — run history and event timeline

Pages: Overview, Accounts, Operations, Decisions, Knowledge, System, Incidents, Research, History
```

## Design Patterns

### 1. Protocol-Based Abstraction (Go-Style Interfaces)

Python `Protocol` classes define interfaces; concrete classes implement them. This keeps components interchangeable:

- `DataProvider` → `YFinanceMarketBarProvider`
- `MarketBarStore` → `CsvMarketBarStore`
- `BrokerAdapter` → `PaperBrokerAdapter`, `DryRunBrokerAdapter`, `LiveBrokerAdapter`
- `LiveBrokerClient` → `FakeLiveBrokerClient`, `AlpacaPaperBrokerClient`, `SemanticPaperBrokerClient`
- `Strategy` / `FeatureStrategy` / `TargetStrategy` / `FeatureTargetStrategy`

### 2. Adapter Pattern

Adapters wrap concrete implementations behind a shared interface:

- `PaperBrokerAdapter` wraps `PaperBroker` through `SignalExecutionBroker`
- `LiveBrokerAdapter` wraps any `LiveBrokerClient` and adds audit artifact writing
- `DryRunBrokerAdapter` records intended orders without submission

### 3. Fail-Closed Safety Gates

Every path that could interact with a real broker requires:
- Explicit `--live-trading-enabled` flag
- Confirmation phrase: `I_UNDERSTAND_LIVE_TRADING_RISK`
- Bounded risk limits (max notional, short exposure, gross exposure, buying power buffer)
- `TradingSafetyConfig` → `evaluate_trading_safety()` → `TradingSafetyCheck`

### 4. Append-Only Event Lifecycle (Semantic-Target Lane)

Execution plans follow a strict state machine:

```
PLANNED → SUBMISSION_PENDING → SUBMITTED → FILLED → SATISFIED
                              → REJECTED
                              → CANCELLED
                              → AMBIGUOUS → (recovery: lookup broker by client_order_id)
```

Each transition is an append-only `ExecutionEvent`. Satisfaction requires:
- Broker position equals approved target
- No unsettled orders exist
- Account-wide reconciliation passed

### 5. Rehearsal Pattern

Before any safety-critical code path is enabled operationally, it must pass a matrix of no-network test scenarios:

- `SemanticTargetRehearsalScenario` — 8 scenarios (eligible dry-run, restart idempotency, stale target blocking, working order blocking, risk rejection, fractional target blocking, local paper restart, reconciliation failure)
- `AutonomousDryRunRehearsalScenario` — 5 scenarios (repeated runs, restart, expiry, target limit, halt-after-block)
- `SupervisedDryRunRehearsalScenario` — 8 scenarios (healthy continuation, degraded/failed health stop, shutdown, blocked run, provider error, runtime bound, restart continuation)
- `ActivationConsumptionRehearsalScenario` — 5 scenarios (restart idempotency, expired auth blocking, scope mismatch, single consumption)
- `SupervisedProviderAssemblyRehearsalScenario` — 7 scenarios
- `SupervisedProviderOperatorRehearsalScenario` — 4 scenarios

Each produces an immutable `*RehearsalReport` with evidence-verified scenario results.

### 6. Activation Gate Pattern

Separates human authorization from capability exposure:

```
SemanticTargetActivationAuthorization (immutable, time-bounded)
  → binds: allowed scope, validity interval, policy versions,
            rehearsal evidence (SHA-256), operator identity
  → SemanticTargetActivationEvaluation (per-request)
    → allowed: proceeds to orchestration
    → blocked: durable evidence, stops
```

### 7. File-Based Persistence

All state is JSON-on-disk:
- Orders, fills, positions → `data/paper/`, `data/live/`, `data/dry_run/`
- Scheduler records → `data/scheduler/`
- Workflow records → `data/workflows/`
- Research artifacts → `data/research/`
- Execution lifecycle → `plans/`, `events/`, `recovery-evidence/`, `drift-observations/`

State writes use atomic replace (write to temp, rename) with `.bak` backup.

## Data Flow

```
yfinance → RawDataset → normalize → MarketBar → FeatureData
                                              → Strategy → SignalFrame/TargetFrame
                                              → Risk Check → Broker → Audit Records
                                                              → Reconciliation
```

## Directory Structure

```
src/quant/
  cli.py                    # Typer CLI (2988 lines)
  api/                      # FastAPI web console routes
  backtest/                 # VectorBT backtesting engine
  data/                     # Data ingestion, normalization, validation
    providers/               # DataProvider implementations
    stores/                  # MarketBarStore implementations
  execution/                # Broker adapters, risk checks, safety gates, lifecycle
  features/                 # Technical feature engineering
  models/                   # Pydantic domain models
  research/                 # Research simulation and target evaluation
  scheduler/                # Finite loop scheduler
  strategies/               # Strategy protocols and implementations
  workflows/                # Composed operational workflows
  web/                      # FastAPI app, templates, static files
  operations/               # Health checks, dashboard, lock management

data/
  raw/                      # Raw provider output
  normalized/               # Normalized market bars
  validation/               # Validation reports
  metadata/                 # Dataset metadata
  features/                 # Feature artifacts
  paper/                    # Paper trading state and audit records
  dry_run/                  # Dry-run order records
  live/                     # Live broker artifacts (Alpaca paper)
  workflows/                # Workflow execution records
  scheduler/                # Scheduler run records
  reconciliation/           # Provider reconciliation reports
  locks/                    # Workflow lock files
  results/                  # Backtest results

site/                       # Static dashboard (HTML/CSS/JS)
configs/                    # YAML configuration
scripts/                    # Shell wrapper scripts
logs/                       # Runtime logs
docs/                       # Architecture and operations documentation
```

## External Dependencies

| Component | Role | Boundary |
|-----------|------|----------|
| **VectorBT** | Fast vectorized backtesting, signal portfolio simulation | Research/analysis only — does not own application logic |
| **yfinance** | Market data provider (OHLCV) | Data ingestion layer only |
| **Alpaca (alpaca-py)** | Paper trading broker API | Optional dependency — separate install, explicit safety gates |
| **FastAPI + uvicorn** | Web console API server | Read-only observation, no mutation |
| **Jinja2** | HTML templating | Web console pages only |
