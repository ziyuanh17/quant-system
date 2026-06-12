# Alpaca Paper Adapter Design v1

This document designs the first external broker adapter boundary for Alpaca
paper trading. It does not add `alpaca-py`, credentials, network calls, or
commands that can contact Alpaca.

The goal is to make the eventual Alpaca paper integration fit behind the same
live audit, safety, adapter, and reconciliation contracts already proven with
the no-network fake broker.

## Sources Checked

Checked on 2026-05-20:

- [Alpaca-py TradingClient](https://alpaca.markets/sdks/python/api_reference/trading/trading-client.html)
- [Alpaca-py Orders](https://alpaca.markets/sdks/python/api_reference/trading/orders.html)
- [Alpaca-py Account](https://alpaca.markets/sdks/python/api_reference/trading/account.html)
- [Alpaca-py Positions](https://alpaca.markets/sdks/python/api_reference/trading/positions.html)
- [Alpaca-py Trading Enums](https://alpaca.markets/sdks/python/api_reference/trading/enums.html)
- [Alpaca-py Trading guide](https://alpaca.markets/sdks/python/trading.html)

Relevant current docs:

- `TradingClient` supports paper and live mode and accepts `paper=True`.
- `TradingClient.submit_order(...)` creates an order.
- `TradingClient.get_orders(...)` returns orders and supports filters.
- `TradingClient.get_account()` returns account details such as buying power
  and account status.
- `TradingClient.get_all_positions()` returns open positions.
- Alpaca order statuses include `new`, `accepted`, `partially_filled`,
  `filled`, `canceled`, `expired`, `rejected`, and several pending states.

## Non-Goals

This milestone must not add:

- `alpaca-py` to project dependencies
- Alpaca API keys or `.env` secrets
- network calls
- Alpaca client construction in production code
- real live trading support
- CLI commands that contact Alpaca
- background jobs that contact Alpaca

## Target Architecture

The future integration should add a thin Alpaca client wrapper behind the
existing protocol:

```text
quant live/paper command or workflow
  -> TradingSafetyConfig
  -> TradingSafetyCheck
  -> AlpacaPaperBrokerClient
  -> LiveBrokerAdapter
  -> LiveOrderRecord / LiveFillRecord / LiveAccountSnapshot
  -> reconcile_live_state
```

The adapter should reuse:

- `LiveBrokerClient`
- `LiveBrokerAdapter`
- `LiveOrderRecord`
- `LiveFillRecord`
- `LiveAccountSnapshot`
- `LiveReconciliationReport`
- live artifact writers under `data/live/`

The Alpaca-specific code should translate Alpaca SDK objects into these internal
models and keep the rest of the system broker-neutral.

## Proposed Module Boundary

Add a future module:

```text
src/quant/execution/alpaca_paper.py
```

It should contain:

```text
AlpacaPaperConfig
AlpacaTradingClientProtocol
AlpacaPaperBrokerClient
map_alpaca_order_status
map_alpaca_order_record
map_alpaca_fill_records
map_alpaca_account_snapshot
```

`AlpacaTradingClientProtocol` should be a local protocol matching only the SDK
methods we call:

```text
submit_order(order_data)
get_orders(filter=None)
get_account()
get_all_positions()
```

This lets tests use fake Alpaca SDK objects without importing or installing
`alpaca-py`.

## Dependency Plan

Dependency should be added only after the design is reviewed.

When added, prefer an optional extra:

```text
pip install -e ".[alpaca]"
```

Possible `pyproject.toml` shape:

```toml
[project.optional-dependencies]
alpaca = ["alpaca-py>=..."]
```

Do not make Alpaca a core dependency yet. The default development/test path
should keep working without broker packages.

## Environment Variables

Future Alpaca paper variables should be explicit and separate from generic live
safety variables:

```text
QUANT_ALPACA_PAPER_API_KEY=
QUANT_ALPACA_PAPER_SECRET_KEY=
QUANT_ALPACA_PAPER_ACCOUNT_ID=
QUANT_ALPACA_PAPER_URL_OVERRIDE=
```

Rules:

- do not put real values in `.env.example`
- do not log API keys or secret keys
- do not write credentials into artifacts
- `QUANT_ALPACA_PAPER_ACCOUNT_ID` may be stored only if sanitized and useful for
  reconciliation
- missing credentials must fail before constructing the SDK client
- `url_override` should be reserved for tests/proxies and not required for
  ordinary paper use

Generic live safety variables still gate order submission:

```text
QUANT_TRADING_MODE=live
QUANT_LIVE_TRADING_ENABLED=true
QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
QUANT_MAX_ORDER_NOTIONAL=...
QUANT_BROKER=alpaca-paper
```

Even though Alpaca paper does not use real money, the adapter is shaped like a
live broker path. It should keep the same explicit gates to avoid normalizing
unsafe behavior before production trading exists.

## Order Request Mapping

First implementation scope:

- equities only
- market orders only
- whole-share quantity only
- `TimeInForce.DAY`
- no fractional shares
- no options
- no crypto
- no bracket/OCO/OTO orders
- no short selling until explicit risk policy exists

Internal `OrderRequest` maps to an Alpaca `MarketOrderRequest`:

| Internal | Alpaca |
| --- | --- |
| `symbol` | `symbol` |
| `side=buy` | `OrderSide.BUY` |
| `side=sell` | `OrderSide.SELL` |
| `quantity` | `qty` |
| `order_type=market` | `MarketOrderRequest` |
| client order ID | Alpaca client order ID field if supported by the request model |

If the SDK request model does not expose a client order ID in the expected way,
the first implementation should stop and document the mismatch instead of
submitting without idempotency.

## Order Status Mapping

Map Alpaca statuses into `LiveOrderStatus` conservatively:

| Alpaca status | Internal status |
| --- | --- |
| `filled` | `FILLED` |
| `partially_filled` | `PARTIALLY_FILLED` |
| `canceled` | `CANCELLED` |
| `rejected` | `REJECTED` |
| `expired` | `CANCELLED` |
| `new` | `ACCEPTED` |
| `accepted` | `ACCEPTED` |
| `pending_new` | `ACCEPTED` |
| `accepted_for_bidding` | `ACCEPTED` |
| `pending_cancel` | `ACCEPTED` |
| `pending_replace` | `ACCEPTED` |
| `done_for_day` | `UNKNOWN` |
| `replaced` | `UNKNOWN` |
| `stopped` | `UNKNOWN` |
| `suspended` | `UNKNOWN` |
| `calculated` | `UNKNOWN` |
| `held` | `UNKNOWN` |
| unrecognized | `UNKNOWN` |

Unknown should not mean success. Unknown statuses should trigger degraded or
failed reconciliation until explicitly handled.

## Fill Mapping

Alpaca order objects may contain filled quantity, average fill price, and status
fields, but the first implementation should not assume a complete execution
history from a single order response.

Initial approach:

- create a `LiveOrderRecord` from every submitted or queried Alpaca order
- create a `LiveFillRecord` only when status is `filled` or
  `partially_filled` and filled quantity/price are present
- use Alpaca order ID plus filled quantity/price to derive a deterministic fill
  key if no execution ID is available through the chosen endpoint
- do not invent fills for accepted/new/pending orders

Later improvement:

- evaluate whether Alpaca account activities or trade updates provide a better
  execution-level feed for fills
- add streaming trade updates only after the polling reconciliation path works

## Account And Position Mapping

`TradingClient.get_account()` should map to `LiveAccountSnapshot` fields:

| Alpaca account field | Internal |
| --- | --- |
| account ID | `account_id` |
| buying power | `buying_power` |
| cash or cash-like field | `cash` |
| paper environment | `broker_environment="paper"` |

`TradingClient.get_all_positions()` maps to internal `Position` records:

| Alpaca position field | Internal |
| --- | --- |
| symbol | `symbol` |
| quantity | `quantity` |
| average entry price | `average_price` |
| current price or market price | `last_price` |

All numeric fields should be parsed through explicit conversion helpers because
broker SDKs often expose decimal-like values as strings.

## Reconciliation Plan

The Alpaca paper adapter should use the existing `reconcile_live_state` shape.

Compare:

- local open live order artifacts vs `TradingClient.get_orders(...)` filtered
  for open/relevant orders
- local fill artifacts vs each known local order refreshed directly through
  `TradingClient.get_order_by_id(...)`
- local latest `LiveAccountSnapshot` vs `TradingClient.get_account()` and
  `get_all_positions()`

Direct broker-order-ID refresh keeps the fill comparison scope aligned with
the durable local order scope. It avoids treating Alpaca's default order-list
window as complete historical broker truth and avoids pulling unrelated broker
history into reconciliation.

Fill artifact persistence uses the broker execution ID as its idempotency key
across processes. Re-running order refresh must not create a second local fill
artifact for an execution that is already recorded.

The first reconciliation pass may be polling-based. Streaming trade updates are
out of scope until polling reconciliation is reliable.

## Test Plan Before SDK Install

Before adding `alpaca-py`, add tests with local fake Alpaca objects:

- status mapping for every known Alpaca status
- market-order request mapping for buy and sell
- order response mapping into `LiveOrderRecord`
- filled order mapping into `LiveFillRecord`
- account/position mapping into `LiveAccountSnapshot`
- missing credentials fail before client construction
- unrecognized statuses map to `UNKNOWN`
- numeric strings parse correctly

These tests should import no Alpaca package.

## Test Plan After SDK Install

After `alpaca-py` is added as an optional dependency:

- keep all mapping tests using fake SDK-shaped objects
- add import smoke tests behind the optional extra
- add no network tests by default
- add manually run integration tests only when Alpaca paper credentials are
  explicitly present

Default CI must not require Alpaca credentials.

Manual broker-connected checks should follow
[alpaca_paper_smoke_runbook.md](alpaca_paper_smoke_runbook.md) before any
scheduled Alpaca workflow is added.

## CLI Boundary

Future commands should stay separate from fake live commands:

```text
quant live alpaca-paper-order
quant live alpaca-paper-reconcile
```

Do not add:

```text
quant live order --broker alpaca --paper
```

The explicit command name makes the environment obvious during early
development. A generic broker selector can come later, after multiple broker
adapters exist.

## Implementation Order

Recommended implementation sequence:

1. **Alpaca Paper Mapping v1**: add broker-neutral mapping helpers and tests
   using fake Alpaca-shaped objects, with no SDK dependency. Implemented.
2. **Alpaca Optional Dependency v1**: add `alpaca-py` as an optional extra and
   verify import boundaries. Implemented.
3. **Alpaca Paper Client v1**: implement `AlpacaPaperBrokerClient` behind
   `LiveBrokerClient`, still with no default network tests. Implemented.
4. **Alpaca Paper CLI v1**: add explicit safety-gated paper commands.
   Implemented.
5. **Alpaca Paper Reconciliation v1**: reconcile local artifacts against Alpaca
   paper account state. Implemented.
6. **Alpaca Paper Manual Smoke Runbook v1**: document the human-run paper
   broker smoke test before scheduled Alpaca workflows. Implemented.

The mapping-only layer now exists in `src/quant/execution/alpaca_paper.py`,
and the lazy optional SDK boundary now exists in
`src/quant/execution/alpaca_sdk.py`. The Alpaca paper client wrapper now exists
behind the existing live broker protocol. Explicit Alpaca paper order and
snapshot commands now exist under `quant live`, and local artifacts can now be
reconciled against Alpaca paper state. The manual smoke runbook now documents
the careful broker-connected check that should pass before scheduled Alpaca
workflows are added.
