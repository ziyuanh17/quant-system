# Tech Documentation — quant-system

## Language & Runtime

- **Python 3.12+** (enforced via `requires-python = ">=3.12"` in pyproject.toml)
- No other language dependencies

## Build System & Dependency Management

- **Build backend:** hatchling (`hatchling.build`)
- **Dependency resolver:** uv (with `uv.lock` for reproducible resolution)
- **Installation:**
  ```bash
  # Full setup with dev dependencies
  pip install -e ".[dev]"
  # Or with uv:
  uv sync --extra dev

  # Optional: Alpaca broker support
  pip install -e ".[broker-alpaca]"
  # Or with uv:
  uv sync --extra dev --extra broker-alpaca
  ```

## Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.115 | Web console API framework |
| `uvicorn` | >=0.34 | ASGI server for FastAPI |
| `typer` | >=0.12 | CLI framework (hierarchical subcommands) |
| `pydantic` | >=2.7 | Typed data models (all domain models inherit `FrozenModel`) |
| `pandas` | >=2.2 | Data manipulation (features, signals) |
| `numpy` | >=1.26 | Numerical computation |
| `vectorbt` | >=0.28 | Backtesting engine (vectorized signal portfolio simulation) |
| `yfinance` | >=0.2 | Market data provider (OHLCV from Yahoo Finance) |
| `jinja2` | >=3.1 | HTML templating for web console |
| `markdown2` | >=2.5 | Markdown processing for docs index |

## Optional Dependencies

| Package | Extra | Purpose |
|---------|-------|---------|
| `alpaca-py` | `broker-alpaca` | Alpaca paper trading API client |

## Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | >=8.2 — test runner |
| `ruff` | >=0.5 — linter |
| `pyright` | >=1.1 — static type checker |

## Linting & Type Checking Configuration

**Ruff** (`pyproject.toml`):
- Line length: 80 characters
- Target: Python 3.12
- Rules: E (pycodestyle), F (pyflakes), I (isort), UP (pyupgrade), B (bugbear), SIM (simplify), D100/D104 (docstrings for public modules/classes)

**Pyright** (`pyproject.toml`):
- Include: `src`, `tests`
- Python version: 3.12
- Mode: standard
- Missing type stubs: suppressed

## Project Structure

```
quant-system/
  pyproject.toml        # Project manifest (hatchling build)
  uv.lock               # Reproducible dependency lock file
  Makefile              # Local dev targets
  .env.example          # Environment variable template
  src/quant/            # Main Python package
    cli.py              # CLI entry point (Typer, ~3000 lines)
    api/                # FastAPI web console routes
    backtest/           # VectorBT backtesting
    data/               # Data ingestion, normalization, validation
    execution/          # Broker adapters, risk, safety, lifecycle
    features/           # Feature engineering
    models/             # Pydantic domain models
    research/           # Research simulation
    scheduler/          # Finite loop scheduler
    strategies/         # Strategy protocols & implementations
    workflows/          # Composed operational workflows
    web/                # Web console (app, templates, static)
    operations/         # Health checks, dashboard, locks
  tests/                # Pytest test suite (~64 test files)
  data/                 # Runtime data artifacts
  site/                 # Static dashboard
  scripts/              # Shell wrapper scripts
  configs/              # YAML configuration (dev.yaml)
  logs/                 # Runtime logs
  docs/                 # Documentation
  .github/workflows/    # CI (ci.yml) and GitHub Pages (pages.yml)
```

## Environment Variables

All configurable via `.env` (copy from `.env.example`):

### Trading Configuration
| Variable | Default | Purpose |
|----------|---------|---------|
| `QUANT_ENV` | `dev` | Environment identifier |
| `QUANT_TRADING_MODE` | `paper` | Trading mode (paper/dry-run/live) |
| `QUANT_LIVE_TRADING_ENABLED` | `false` | Master switch for live trading paths |
| `QUANT_LIVE_TRADING_CONFIRMATION` | — | Confirmation phrase required for live trading |
| `QUANT_MAX_ORDER_NOTIONAL` | — | Maximum dollar value per order |
| `QUANT_BROKER` | — | Broker identifier |
| `QUANT_SHORT_SELLING_ENABLED` | `false` | Enable short selling |
| `QUANT_MAX_SHORT_POSITION_NOTIONAL` | — | Max short position value |
| `QUANT_MAX_TOTAL_SHORT_EXPOSURE_PCT_EQUITY` | — | Max total short exposure as % of equity |
| `QUANT_MAX_GROSS_EXPOSURE_PCT_EQUITY` | — | Max gross exposure as % of equity |
| `QUANT_MIN_BUYING_POWER_BUFFER_PCT` | — | Minimum buying power buffer |

### Data Paths
| Variable | Default | Purpose |
|----------|---------|---------|
| `QUANT_DATA` | `data/sample_prices.csv` | Price data source |
| `QUANT_SYMBOL` | `AAPL` | Trading symbol |
| `QUANT_PROVIDER` | `yfinance` | Data provider |
| `QUANT_START` | `2024-01-01` | Start date for data ingestion |
| `QUANT_END` | — | End date (empty = present) |
| `QUANT_QUANTITY` | `1` | Default order quantity |
| `QUANT_INITIAL_CASH` | `100000` | Initial paper trading cash |
| `QUANT_ITERATIONS` | `1` | Number of scheduler loop iterations |
| `QUANT_INTERVAL_SECONDS` | `0` | Interval between scheduler iterations |
| `QUANT_MIN_ROWS` | `1` | Minimum rows for data validation |
| `QUANT_SKIP_VALIDATION` | `false` | Skip data validation |

### Paper Trading State
| Variable | Default | Purpose |
|----------|---------|---------|
| `QUANT_STATE_PATH` | `data/paper/state/default.json` | Paper account state file |
| `QUANT_SIGNAL_OUTPUT_DIR` | `data/paper/signals` | Signal audit records directory |
| `QUANT_RUN_OUTPUT_DIR` | `data/scheduler/latest` | Scheduler run records directory |
| `QUANT_RAW_DIR` | `data/raw` | Raw data output directory |
| `QUANT_NORMALIZED_DIR` | `data/normalized` | Normalized data directory |
| `QUANT_VALIDATION_DIR` | `data/validation` | Validation reports directory |
| `QUANT_METADATA_DIR` | `data/metadata` | Dataset metadata directory |
| `QUANT_WORKFLOW_OUTPUT_DIR` | `data/workflows/paper-signal-refresh` | Workflow output directory |
| `QUANT_LOCK_PATH` | `data/locks/paper-signal-refresh.lock` | Workflow lock file |
| `QUANT_LOCK_STALE_AFTER_SECONDS` | `7200` | Lock staleness threshold (2 hours) |
| `QUANT_LOG_DIR` | `logs` | Log directory |

### Dry-Run Configuration
| Variable | Default | Purpose |
|----------|---------|---------|
| `QUANT_DRY_RUN_OUTPUT_DIR` | `data/dry_run/orders` | Dry-run order records |
| `QUANT_DRY_RUN_RUN_OUTPUT_DIR` | `data/scheduler/dry-run` | Dry-run scheduler records |
| `QUANT_DRY_RUN_WORKFLOW_OUTPUT_DIR` | `data/workflows/dry-run-refresh` | Dry-run workflow records |
| `QUANT_DRY_RUN_LOCK_PATH` | `data/locks/dry-run-refresh.lock` | Dry-run lock file |
| `QUANT_DRY_RUN_COMPARISON_OUTPUT_PATH` | `data/dry_run/comparison/latest.json` | Paper vs dry-run comparison |
| `QUANT_DRY_RUN_BROKER_NAME` | `dry-run` | Dry-run broker identifier |

### Alpaca Paper Configuration
| Variable | Default | Purpose |
|----------|---------|---------|
| `QUANT_ALPACA_PAPER_API_KEY` | — | Alpaca API key (paper) |
| `QUANT_ALPACA_PAPER_SECRET_KEY` | — | Alpaca secret key (paper) |
| `QUANT_ALPACA_PAPER_ACCOUNT_ID` | — | Alpaca account ID (paper) |
| `QUANT_ALPACA_PAPER_URL_OVERRIDE` | — | Alpaca API URL override |
| `QUANT_ALPACA_PAPER_WORKFLOW_OUTPUT_DIR` | `data/workflows/alpaca-paper-refresh` | Alpaca workflow records |
| `QUANT_ALPACA_PAPER_LOCK_PATH` | `data/locks/alpaca-paper-refresh.lock` | Alpaca lock file |
| `QUANT_ALPACA_PAPER_ORDER_OUTPUT_DIR` | `data/live/orders` | Live order artifacts |
| `QUANT_ALPACA_PAPER_FILL_OUTPUT_DIR` | `data/live/fills` | Live fill artifacts |
| `QUANT_ALPACA_PAPER_SNAPSHOT_OUTPUT_DIR` | `data/live/account_snapshots` | Account snapshot artifacts |
| `QUANT_ALPACA_PAPER_RECONCILIATION_OUTPUT_PATH` | `data/live/reconciliation/latest.json` | Reconciliation report |
| `QUANT_ALPACA_PAPER_CASH_TOLERANCE` | `0.01` | Cash tolerance for reconciliation |

### Web Console Configuration
| Variable | Default | Purpose |
|----------|---------|---------|
| `QUANT_CONSOLE_AUTH_MODE` | `tailscale` | Auth mode (tailscale / api-key) |
| `QUANT_CONSOLE_TAILSCALE_USERS` | — | Allowed Tailscale users |
| `QUANT_CONSOLE_API_KEY` | — | API key for auth fallback |
| `QUANT_CONSOLE_HOST` | `127.0.0.1` | Bind host |
| `QUANT_CONSOLE_PORT` | `8000` | Bind port |

## CLI Commands

```
quant backtest                  # Run VectorBT backtest
quant data ingest               # Ingest market data from provider
quant data validate             # Validate normalized market bars
quant data reconcile            # Compare two normalized datasets
quant features build            # Build technical features
quant paper order               # Submit paper market order
quant paper reconcile-state     # Reconcile paper state
quant schedule paper-order      # Finite paper order loop
quant schedule paper-signal     # Finite paper signal loop
quant schedule dry-run-signal   # Finite dry-run signal loop
quant workflow paper-signal-refresh   # Data refresh + paper signal
quant workflow dry-run-refresh        # Data refresh + dry-run signal
quant workflow alpaca-paper-refresh   # Data refresh + Alpaca paper
quant ops health                # Check operational health
quant ops publish-status        # Publish health to dashboard
quant ops publish-knowledge     # Publish knowledge index
quant safety check              # Evaluate trading safety gates
quant dry-run order             # Record intended dry-run order
quant dry-run signal            # Route strategy signal to dry-run
quant dry-run compare-paper     # Compare paper vs dry-run
quant dry-run activated-target  # Consume reviewed request for dry-run
quant dry-run inspect-activated-target  # Read-only inspection
quant dry-run autonomous-finite-loop  # Finite autonomous dry-run loop
quant dry-run supervised-provider       # Supervised dry-run cycle
quant live fake-order                  # Fake live order (test)
quant live fake-reconcile              # Fake live reconcile (test)
quant live alpaca-paper-order          # Alpaca paper order
quant live alpaca-paper-rehearsal-order # Alpaca paper rehearsal
quant live alpaca-paper-snapshot       # Alpaca paper snapshot
quant live alpaca-paper-reconcile      # Alpaca paper reconciliation
quant live alpaca-paper-refresh-orders # Alpaca paper refresh
quant web serve                    # Start web console
```

## Testing

- **Framework:** pytest 8.2+
- **Location:** `tests/` (64 test files)
- **Coverage:** broker adapters, execution lifecycle, reconciliation, workflows, CLI validation, data ingestion, features, backtest artifacts, web console security, live rehearsal, audit models
- **Run:** `make test` or `.venv/bin/python -m pytest`

## CI/CD

- **GitHub Actions CI** (`.github/workflows/ci.yml`): runs lint, typecheck, test
- **GitHub Pages** (`.github/workflows/pages.yml`): deploys static dashboard

## Operational Scripts

```bash
bash scripts/run_paper_signal_refresh.sh    # Legacy paper signal workflow
bash scripts/run_dry_run_refresh.sh         # Dry-run refresh workflow
bash scripts/run_alpaca_paper_refresh.sh    # Alpaca paper workflow
```

Each loads `.env`, runs the corresponding workflow, and writes timestamped logs.

## Key Technical Decisions

1. **JSON-on-disk persistence** — All state is JSON files, not a database. Simple, inspectable, but no concurrent access beyond file locks.
2. **Protocol-based interfaces** — Python `Protocol` classes define contracts; no inheritance hierarchy for types. Makes components swappable.
3. **Fail-closed by default** — Every live path requires explicit enablement. Paper/dry-run are the defaults.
4. **Atomic state writes** — Write to temp file, then rename. `.bak` backup of previous state. Prevents corruption from interrupted writes.
5. **File-based locks** — Atomic `O_CREAT | O_EXCL` with stale detection via `os.kill(pid, 0)`.
6. **Schema versioning** — All models have `schema_version: Literal[N]` for future migration compatibility.
7. **Idempotent orders** — Deterministic `client_order_id` prevents duplicate submissions.
8. **Append-only lifecycle events** — Execution lifecycle transitions are never overwritten, only appended.
