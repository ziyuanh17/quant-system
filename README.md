# Quant System

A small, typed, solo-maintainable quant system.

The first milestone is intentionally narrow:

1. Load historical prices from CSV.
2. Generate entries and exits from a typed strategy.
3. Run a VectorBT-backed signal backtest.
4. Return typed performance results.
5. Keep production code explicit enough that dictionary key tracing does not become a daily tax.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

If you prefer `uv` later:

```bash
uv sync --extra dev
```

The repository includes `uv.lock` so dependency resolution is reproducible
when using `uv`.

## First Backtest

```bash
quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL
```

The command writes durable artifacts by default:

```text
data/results/latest/summary.json
data/results/latest/trades.csv
```

## Data Ingestion

The ingestion layer separates raw provider data from normalized data:

```bash
quant data ingest --provider yfinance --symbol AAPL --start 2024-01-01 --end 2024-02-01
```

This writes:

```text
data/raw/provider=yfinance/modality=market_bars/symbol=AAPL/...
data/normalized/market_bars/AAPL.csv
data/validation/market_bars/AAPL.json
data/metadata/market_bars/AAPL.json
```

Validate normalized data before backtesting it:

```bash
quant data validate --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

Validation also runs by default during ingestion and before CSV backtests. Use
`--skip-validation` only when intentionally debugging bad data.

Compare two normalized market-bar datasets before trusting a merged or
provider-swapped research run:

```bash
quant data reconcile --left path/to/provider_a.csv --right path/to/provider_b.csv --symbol AAPL
```

This writes a report under:

```text
data/reconciliation/AAPL.json
```

## Feature Engineering

Build technical features from normalized market bars:

```bash
quant features build --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

This writes:

```text
data/features/technical/AAPL.csv
```

Run a backtest that consumes a persisted feature artifact:

```bash
quant backtest --strategy feature-momentum --features-data data/features/technical/AAPL.csv --symbol AAPL
```

Use `--fast-feature` and `--slow-feature` to point the strategy at different
moving-average columns.

## Paper Trading

Submit a deterministic paper market order at a supplied price:

```bash
quant paper order --symbol AAPL --side buy --quantity 10 --price 100
```

This writes an audit record under:

```text
data/paper/latest/
```

See [docs/trading_stages.md](docs/trading_stages.md) for the distinction
between backtesting, paper trading, and real trading.

See [docs/broker_adapters.md](docs/broker_adapters.md) for the broker adapter
boundary that keeps paper execution separate from any future real broker
integration.

Check the current trading safety gates:

```bash
quant safety check
```

See [docs/trading_safety.md](docs/trading_safety.md) for the fail-closed live
trading rules.

See [docs/live_broker_adapter.md](docs/live_broker_adapter.md) for the live
broker adapter design boundary. The project still has no real broker
connectivity.

See [docs/live_broker_api_research.md](docs/live_broker_api_research.md) for
the broker API/package research behind the first integration decision.

See [docs/alpaca_paper_adapter.md](docs/alpaca_paper_adapter.md) for the
Alpaca paper adapter design. The SDK is optional and is not needed for default
development or CI checks.

Install Alpaca support only when working on the Alpaca adapter path:

```bash
python -m pip install -e ".[broker-alpaca]"
```

With `uv`:

```bash
uv sync --extra dev --extra broker-alpaca
```

Record a live-shaped dry-run order without submitting it:

```bash
quant dry-run order --symbol AAPL --side buy --quantity 1 --price 100
```

Route the latest strategy signal into the dry-run path:

```bash
quant dry-run signal --strategy momentum --data data/sample_prices.csv --symbol AAPL --quantity 1
```

Run dry-run signal execution through the scheduler:

```bash
quant schedule dry-run-signal --strategy momentum --data data/sample_prices.csv --symbol AAPL --quantity 1
```

Compare the latest paper signal with the latest dry-run intended order:

```bash
quant dry-run compare-paper
```

Refresh market data, run the scheduled dry-run signal path, compare outputs,
and optionally publish dashboard health from one workflow:

```bash
quant workflow dry-run-refresh --symbol AAPL --start 2024-01-01 --quantity 1
```

Run the dry-run workflow through the local/server wrapper:

```bash
bash scripts/run_dry_run_refresh.sh
```

See [docs/dry_run_trading.md](docs/dry_run_trading.md) for the difference
between paper trading and dry-run trading.

## Scheduled Runs

Run a finite scheduled paper-order loop:

```bash
quant schedule paper-order --symbol AAPL --side buy --quantity 1 --price 100 --iterations 1
```

This writes scheduler run records under:

```text
data/scheduler/latest/
```

Run a scheduled strategy-to-paper loop:

```bash
quant schedule paper-signal --strategy momentum --data data/sample_prices.csv --symbol AAPL --quantity 1 --iterations 1
```

By default, this persists paper account state under:

```text
data/paper/state/default.json
```

Repeated runs skip duplicate trade execution for the same strategy, symbol,
signal date, and action.

See [docs/deployment.md](docs/deployment.md) for running the paper signal loop
as a recurring server job.

Refresh data before running the paper signal path:

```bash
quant workflow paper-signal-refresh --symbol AAPL --start 2024-01-01
```

See [docs/workflows.md](docs/workflows.md) for the workflow record and server
wrapper details, including the lock file that prevents overlapping runs.

Check the local service artifacts:

```bash
quant ops health
```

Run the fuller operational check with paper state reconciliation:

```bash
quant ops health --reconcile-state --initial-cash 100000
```

Publish a sanitized health snapshot for the static dashboard:

```bash
quant ops publish-status --initial-cash 100000
```

See [docs/operations.md](docs/operations.md) for health status meanings and
current observability limits.

Reconcile paper state against the signal audit trail:

```bash
quant paper reconcile-state --initial-cash 100000
```

## Progress Dashboard

The repo includes a static dashboard under `site/`. It can be deployed for free
with GitHub Pages after enabling Pages from GitHub Actions in the repository
settings.

Local files:

```text
site/index.html
site/progress.json
site/status.json
```

## Local Checks

```bash
make check
```

Or run the pieces separately:

```bash
make lint
make typecheck
make test
make backtest
```

## Design Rule

Dictionaries are allowed at system edges. Core domain logic uses typed models:

- market bars
- signals
- strategy configuration
- backtest metrics
- orders and fills

See [docs/code_style.md](docs/code_style.md).
