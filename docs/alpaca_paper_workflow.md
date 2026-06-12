# Alpaca Paper Workflow Design

This document records the design for the scheduled Alpaca paper workflow. It is
not an implementation plan for real-money trading.

The workflow should be implemented only after
[alpaca_paper_smoke_runbook.md](alpaca_paper_smoke_runbook.md) has been
reviewed and, ideally, run once against the intended Alpaca paper account.

## Goal

Build one finite, lock-protected workflow that can:

```text
refresh market data
  -> validate refreshed data
  -> generate the latest strategy signal
  -> translate signal intent into a target position
  -> submit only the order required to reach that target
  -> write live audit artifacts
  -> reconcile against Alpaca paper broker state
  -> publish sanitized health only after reconciliation
  -> write a workflow record
```

The workflow should be boring, explicit, and auditable. It should prefer a
missed paper trade over a duplicated or unexplained broker-connected action.

## Preconditions

Before implementation:

- the manual smoke runbook has been reviewed
- at least one manual smoke run has passed, if credentials are available
- `make check` passes
- the optional Alpaca extra is installed only on machines that need it
- Alpaca paper credentials are supplied through environment variables only
- live safety variables are explicit
- no real-money account is connected to this path

Required environment variables:

```text
QUANT_TRADING_MODE=live
QUANT_LIVE_TRADING_ENABLED=true
QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
QUANT_MAX_ORDER_NOTIONAL=...
QUANT_BROKER=alpaca-paper
QUANT_ALPACA_PAPER_API_KEY=...
QUANT_ALPACA_PAPER_SECRET_KEY=...
QUANT_ALPACA_PAPER_ACCOUNT_ID=...
```

Optional:

```text
QUANT_ALPACA_PAPER_URL_OVERRIDE=...
```

## Proposed Command

Use an explicit workflow command:

```bash
quant workflow alpaca-paper-refresh
```

Do not add a generic command such as:

```text
quant workflow live-refresh --broker alpaca --paper
```

The explicit command keeps the broker and environment visible while this path
is young.

This command now exists as Alpaca Paper Refresh Workflow v1. It remains a
finite workflow command; recurring execution belongs in the next server-wrapper
milestone.

## Proposed Options

The command should mirror the existing refresh workflows where possible:

```text
--strategy momentum
--provider yfinance
--symbol AAPL
--start 2024-01-01
--end optional
--quantity 1
--data data/normalized/market_bars/AAPL.csv
--skip-validation false
--min-rows 1
--client-order-id optional
--lock-path data/locks/alpaca-paper-refresh.lock
--lock-stale-after-seconds 7200
--workflow-output-dir data/workflows/alpaca-paper-refresh
--order-output-dir data/live/orders
--fill-output-dir data/live/fills
--snapshot-output-dir data/live/account_snapshots
--reconciliation-output-path data/live/reconciliation/latest.json
--publish-status-path optional
```

For the current long-only momentum workflow, `--quantity` is the desired long
position size, not an incremental order size:

```text
entry -> target position = +quantity
exit  -> target position = 0
hold  -> leave current position unchanged
```

The workflow reads current broker inventory and calculates:

```text
required order quantity = target position - current position
```

For example, an entry with `--quantity 1` while the broker position is `-1`
requires `BUY 2` to reach the `+1` target. The full transition order must pass
the configured order-notional and projected-portfolio risk checks. If the
broker position already equals the target, the workflow records a successful
target-satisfied skip without submitting an order.

## Execution Order

The implementation should run these steps in order:

1. Acquire workflow lock.
2. Load live safety config from environment.
3. Fail if safety config is not allowed.
4. Load Alpaca paper config from environment.
5. Refresh provider market data.
6. Write raw, normalized, validation, and metadata artifacts.
7. Fail if validation fails.
8. Load the validated normalized market-bar data.
9. Generate the latest strategy signal.
10. Read current broker inventory and derive the long-only target position.
11. If signal is `hold` or the target is already satisfied, stop without
    broker submission.
12. Build a deterministic client order ID.
13. Check the full transition order against notional and projected-portfolio
    risk limits.
14. Submit one market order to Alpaca paper.
15. Write live order, fill, and account snapshot artifacts.
16. Reconcile local artifacts against Alpaca paper broker state.
17. Fail if reconciliation status is not `passed`.
18. Publish sanitized health/dashboard status only after reconciliation passes.
19. Write a workflow record.
20. Release workflow lock.

## Safety Policy

The workflow must fail closed when:

- the lock is already held
- safety config is missing or disallowed
- Alpaca paper credentials are missing
- `QUANT_BROKER` is not `alpaca-paper`
- `QUANT_MAX_ORDER_NOTIONAL` is missing
- the full target-position transition exceeds `QUANT_MAX_ORDER_NOTIONAL`
- provider refresh fails
- validation fails
- strategy configuration is unsupported
- idempotency detects an already-processed actionable signal
- broker submission raises
- no account snapshot is written after broker submission
- reconciliation fails

The workflow must not retry broker submission automatically. Retrying a broker
order requires a human decision until idempotency and broker-side order lookup
are stronger.

## Client Order ID Policy

Default client order IDs should be deterministic and account-aware:

```text
alpaca-paper:{strategy}:{symbol}:{signal_date}:{action}:{signal_revision}
```

The first implementation may use a simple revision such as the signal record
ID or feature/data artifact ID. It should not use only wall-clock time because
that makes duplicate signal detection harder.

If Alpaca rejects a duplicate client order ID, the workflow should reconcile
and stop instead of inventing a new ID.

## Artifact Contract

The workflow should write or reference:

```text
data/raw/...
data/normalized/market_bars/{symbol}.csv
data/validation/market_bars/{symbol}.json
data/metadata/market_bars/{symbol}.json
data/live/orders/*.json
data/live/fills/*.json
data/live/account_snapshots/*.json
data/live/reconciliation/latest.json
data/workflows/alpaca-paper-refresh/*.json
site/status.json optional
```

The workflow record should include:

- workflow ID
- symbol
- strategy
- provider
- requested date range
- normalized data path
- validation report path
- metadata path
- signal action
- signal date
- broker position quantity before target planning
- strategy target quantity
- planned order side and quantity, if required
- client order ID, if submitted
- live order artifact paths
- live fill artifact paths
- account snapshot artifact path
- reconciliation report path
- dashboard status path, if written
- lock path
- status
- failure reason, if any

## Dashboard Policy

Dashboard status may be published only after:

- data refresh succeeds
- validation passes
- broker action is skipped safely or submitted successfully
- reconciliation passes

Dashboard output must remain sanitized. It should not include API keys, secret
keys, full account details, or raw broker payloads.

## Non-Goals

This workflow design does not add:

- real-money trading
- generic broker selection
- automatic broker retries
- order cancellation
- streaming trade updates
- multi-symbol portfolio execution
- position sizing beyond fixed quantity
- cloud deployment
- alert hooks

Those belong after the first scheduled Alpaca paper workflow is implemented,
observed, and reconciled reliably.

## Implementation Milestone

The implementation milestone after this design was:

```text
Alpaca Paper Refresh Workflow v1
```

It implemented one finite command with fake-driven tests and no default network
or credential requirements in CI.

The next implementation milestone should be:

```text
Alpaca Paper Server Wrapper v1
```

That milestone should add an env-driven shell wrapper, timestamped logs, and
docs for recurring server-style runs.
