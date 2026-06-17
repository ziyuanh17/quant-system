# Product Documentation — quant-system

## Why This Project Exists

This is a **solo-maintainable quantitative research and paper-execution system**. It was built for a single developer who wants to research trading strategies and progressively validate them through increasingly realistic stages before ever touching real money.

The core problem it solves: **how do you safely go from "this strategy looks good on historical data" to "this strategy works in live markets" without blowing up?**

The answer is a staged progression with explicit safety boundaries at each stage.

## The Three Stages

The project is organized around three distinct stages, each answering a different question:

### 1. Backtesting — "Would this strategy have worked in the past?"

Backtesting runs a strategy over historical price data using VectorBT for fast vectorized simulation. It produces performance metrics (returns, drawdown, trade count, Sharpe ratio, etc.) to evaluate whether a strategy idea has merit.

**What it is:** A research tool for strategy evaluation.
**What it isn't:** Proof that the strategy will work going forward. It doesn't model real-world frictions like slippage, partial fills, or execution latency.

### 2. Paper Trading — "Can the system trade correctly now without using real money?"

Paper trading is a **live rehearsal**. The system behaves as if it's trading with real money, but orders never leave the machine. There are two paper mechanisms:

- **Legacy signal-oriented paper:** Strategies produce boolean entry/exit signals, which get converted to BUY/SELL/HOLD actions and executed against a deterministic in-memory broker.
- **Semantic-target paper:** A newer, more expressive approach where strategies produce signed position targets (e.g., "hold 5 shares" or "short 3 shares"). This goes through portfolio aggregation, risk approval, and a full execution lifecycle before reaching the broker.

**What it is:** A way to test the entire machine — data refresh, signal generation, risk checks, order execution, position tracking, audit logging — while time is actually moving.
**What it isn't:** A guarantee that real trading will work. It doesn't model slippage, partial fills, broker outages, or market impact.

### 3. Real Trading — "Can the system trade correctly against reality?"

Real trading sends orders to an actual broker with real money. This stage adds risks that paper trading cannot simulate: slippage, partial fills, rejected orders, fees, borrow costs, broker outages, exchange halts, latency, market impact, and emotional pressure.

**Current status:** Not implemented. The project has connectivity to Alpaca's paper trading API (which is a real broker API but uses fake money), but real-money execution does not exist.

## The Safety Philosophy

The project follows a **fail-closed** design principle: when in doubt, block the trade rather than allow it. Key safety mechanisms:

- **Explicit enablement:** Every path that could interact with a real broker requires an explicit `--live-trading-enabled` flag and a confirmation phrase (`I_UNDERSTAND_LIVE_TRADING_RISK`).
- **Safety gates:** Configurable limits on order notional, short selling exposure, gross exposure, and buying power buffer.
- **Rehearsals:** Before any code path that could submit real orders is enabled, it must pass a matrix of no-network test scenarios that verify edge cases (restart idempotency, expired authorization, working-order blocking, etc.).
- **Reconciliation:** Every execution path ends with verification against broker truth. Local state is never assumed correct.
- **File locking:** Workflow runs use atomic file-based locks to prevent overlapping executions.

## Intended User Experience

The primary user is a solo quant developer. The workflow looks like:

1. **Research:** Run a backtest on historical data to evaluate a strategy idea.
   ```
   quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL
   ```

2. **Feature engineering:** Build technical indicators from normalized market data.
   ```
   quant features build --data data/normalized/market_bars/AAPL.csv --symbol AAPL
   ```

3. **Paper trading:** Run the strategy against live data in simulation.
   ```
   quant workflow paper-signal-refresh --symbol AAPL --start 2024-01-01
   ```

4. **Dry-run:** Record intended orders without submitting them, as an intermediate validation step.
   ```
   quant dry-run order --symbol AAPL --side buy --quantity 1 --price 100
   ```

5. **Alpaca paper (future):** Once reviewed and authorized, submit orders to Alpaca's paper trading API.
   ```
   quant workflow alpaca-paper-refresh --symbol AAPL --start 2024-01-01 --from-env
   ```

6. **Monitoring:** Check operational health and view the dashboard.
   ```
   quant ops health
   quant web serve  # opens read-only web console at http://127.0.0.1:8000
   ```

## Key Design Decisions

- **JSON-on-disk as primary store:** All state (orders, fills, signals, broker state) is persisted as JSON files. This makes the system trivially inspectable, debuggable, and replayable without a database. The tradeoff is no concurrent access beyond file locks.
- **VectorBT boundary:** VectorBT is used only for fast vectorized backtesting and analytics. The application owns data contracts, strategy interfaces, risk models, broker/execution models, scheduling, and audit logs.
- **Static dashboard:** A static HTML dashboard (`site/`) can be deployed on GitHub Pages for read-only monitoring. It omits sensitive account details.
- **Read-only web console:** A FastAPI-based web console provides real-time observation with Tailscale identity authentication (recommended) or API-key fallback. No mutation endpoints exist.

## Glossary of Domain Terms

| Term | Meaning |
|------|---------|
| **Signal** | A legacy-format boolean entry/exit decision from a strategy (true = buy/sell, false = hold). |
| **Target** | A newer-format signed decimal position target (e.g., +5 = long 5 shares, -3 = short 3 shares, 0 = flat). |
| **Paper trading** | In-memory simulated broker with persistent state. Tracks cash, positions, and processed signals. |
| **Dry-run** | Records intended orders without submitting them anywhere. Pure local simulation. |
| **Semantic paper** | A separate durable local paper broker for the semantic-target lane. Supports signed positions and restart-safe lifecycle. |
| **Live** | Real broker integration (currently only Alpaca paper). Requires explicit safety gates. |
| **Reconciliation** | Comparing local artifacts against broker truth to detect drift. |
| **Rehearsal** | No-network test scenarios that verify safety-critical code paths before they run operationally. |
| **Activation** | Human authorization that gates which operational capabilities are permitted. |
| **Execution plan** | An immutable claim over one approved risk-target revision, tracking the full lifecycle from planned to satisfied. |
| **Notional** | quantity × price — the dollar value of a trade. |
| **Fail-closed** | Design principle: when in doubt, block the trade. |
