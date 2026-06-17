# Context Documentation — quant-system

## Current Status

**Version:** 0.1.0
**Branch:** main
**Primary developer:** ziyuanh17

The repository contains two parallel execution architectures:

1. **Legacy signal-oriented workflows** — fully wired to CLI, scheduler, and recurring workflows. This is the operational lane currently available through `quant` commands.
2. **Semantic-target architecture** — a newer, more expressive approach where strategies produce signed position targets instead of boolean signals. This is **API-only** and not yet connected to the CLI or recurring scheduler.

## What's Implemented

### Legacy Signal Lane (CLI-accessible)
- VectorBT backtesting with momentum and feature-momentum strategies
- Data ingestion from yfinance with normalization and validation
- Technical feature engineering (moving averages, volatility, momentum, drawdown)
- Deterministic in-memory paper broker with persistent state
- Dry-run order recording (intended orders without submission)
- Alpaca paper trading integration (safety-gated, API-key based)
- Finite loop schedulers for paper-order and dry-run-signal runs
- Composed workflows: `paper-signal-refresh`, `dry-run-refresh`, `alpaca-paper-refresh`
- Operational health checks and dashboard status publishing
- Read-only FastAPI web console with Jinja2/HTMX pages
- File-based lock management for concurrent run safety

### Semantic-Target Lane (API-only, not CLI-connected)
- Native target strategies and VectorBT target-amount backtests
- Immutable strategy, portfolio, risk, and evaluation artifacts
- Multi-strategy aggregation with contributor-set ownership
- Whole-share operational validation (fractional targets rejected without rounding)
- Restart-safe execution lifecycle with append-only events
- Durable blocked and ambiguous outcomes
- Semantic dry-run evaluation (read-only observation)
- Durable local semantic-paper execution
- Controlled API-only orchestration composing strategy → portfolio → risk → execution
- No-network orchestration rehearsal with evidence-verified scenarios
- Explicit local reconciliation-failure injection proving fills can't become satisfied when reconciliation fails
- Immutable, time-bounded activation authorizations binding rehearsal evidence
- API-only activated dry-run and local semantic-paper wrappers
- Second-layer activation-consumption rehearsal
- Bounded autonomous dry-run authorization with atomic run claims
- Finite autonomous dry-run operator loop
- Supervised autonomous dry-run service with per-cycle health/shutdown checks
- Versioned provider contracts (health snapshots + request envelopes)
- Local supervised provider assembly with content-hashed manifests
- Supervised provider operator and finite supervised-provider boundaries

## Recent Changes

Based on the git history:
- **Supervised provider operator** — New CLI command `quant dry-run supervised-provider` that consumes a content-bound reviewed request, assembles local provider inputs, and runs one supervised dry-run cycle.
- **Supervised provider assembly** — Local provider assembly that validates file hashes and required identity before writing health snapshots and request envelopes.
- **Supervised autonomous dry-run rehearsal** — No-network rehearsal with 8 scenarios, 10 cycle events, 8 health checks, 5 autonomous dry-run records, zero order/fill directories.
- **Autonomous dry-run finite loop** — Processes exact content-hashed request lists, stops on first block.
- **Activated dry-run operator** — Consumes reviewed requests for activated dry-run path only.
- **Activation-consumption rehearsal** — Verifies authorization gating with evidence-verified scenarios.

## Next Steps (From Roadmap / Current Review Boundary)

Before connecting semantic targets to recurring operations, the following reviews are recommended:

1. Review the checked-in lifecycle and Alpaca integration as one safety boundary.
2. Review the controlled orchestration and reconciliation-failure rehearsal evidence.
3. Review the activated dry-run operator boundary.
4. Review the API-only supervised dry-run service and its no-network rehearsal.
5. Review the supervised health and fresh-request provider contracts.
6. Review the local supervised provider assembly and its no-network rehearsal.
7. Review the manually started supervised-provider dry-run operator boundary.
8. Review its evidence-verified actual-command rehearsal.
9. Review the finite fresh supervised-provider operator boundary.
10. Review any runtime-clone or recurring scheduler exposure.
11. Obtain explicit approval before every broker order-capable rehearsal.

## Known Limitations

- Data Refresh Workflow v1 refreshes only one symbol with one provider and runs one strategy. No multi-provider reconciliation, no feature artifact refresh, no multi-symbol portfolio support.
- Operational observability v1 does not send notifications, track historical health, or inspect data freshness.
- Health monitoring doesn't yet cover semantic-target decisions and execution lifecycle artifacts.
- Drift policy is detect-only — the system does not automatically repair diverged broker positions.
- Fractional shares are valid in research but rejected by operational target validation without silent rounding.
- Real-money trading is not implemented.
- The semantic-target lane is not connected to the CLI or recurring scheduler.

## Development Workflow

```bash
# Setup
make install          # Creates .venv and installs dependencies
make check           # Runs lint + typecheck + test (before pushing)
make backtest        # Smoke test: runs momentum backtest on sample data
make validate        # Validates sample_prices.csv

# Run individually
make lint            # ruff check
make typecheck       # pyright
make test            # pytest
```

## Environment

- Copy `.env.example` to `.env` for local/server runs.
- Alpaca paper requires: `QUANT_ALPACA_PAPER_API_KEY`, `QUANT_ALPACA_PAPER_SECRET_KEY`, `QUANT_ALPACA_PAPER_ACCOUNT_ID`.
- Install Alpaca support separately: `pip install -e ".[broker-alpaca]"`.
