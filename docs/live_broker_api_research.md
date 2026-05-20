# Live Broker API Research Report

Research date: 2026-05-16

This report investigates broker APIs and Python packages that could support the
future live broker adapter described in
[live_broker_adapter.md](live_broker_adapter.md).

This is not financial advice and not a recommendation to trade real money. It
is an engineering decision report for choosing the safest first integration
path.

## Decision Summary

Recommended first target: **Alpaca via the official `alpaca-py` SDK, starting
with paper trading only**.

Why:

- official Python SDK
- simple REST-style trading client
- built-in paper environment
- active project with recent releases
- lower operational burden than desktop-gateway APIs
- good fit for the current system's staged paper -> dry-run -> live boundary

Recommended implementation sequence:

1. Keep the next milestone as **Live Audit Models v1**. Add typed live order,
   fill, account snapshot, and reconciliation models without a broker SDK.
2. Add append-only live artifact readers/writers.
3. Add a fake live broker client and tests.
4. Add an Alpaca paper-only adapter behind the fake-client-tested contract.
5. Add reconciliation against Alpaca paper account state.
6. Only after repeated paper/sandbox runs, consider enabling live credentials.

Secondary candidate: **Tradier**, especially if options support becomes central.

Defer:

- **Interactive Brokers / `ib_async`** until asset breadth matters more than
  simplicity.
- **Schwab / `schwab-py`** until access, OAuth, account behavior, and paper-like
  testing options are clearer.
- **CCXT** unless the project intentionally expands into crypto exchange
  trading.

## Evaluation Criteria

The system should favor APIs/packages with:

- clear paper or sandbox environment
- Python support that is actively maintained
- account, order, position, and fill APIs
- client order ID or equivalent idempotency support
- understandable authentication
- enough documentation to build reconciliation
- low operational burden for a solo maintainer
- no need to keep a desktop trading app open

## Candidate Matrix

| Candidate | Best Use | Paper/Sandbox | Python Package | Main Strength | Main Concern | Fit |
| --- | --- | --- | --- | --- | --- | --- |
| Alpaca | US equities/crypto/options API-first trading | Yes | `alpaca-py` official | Easiest first broker integration | Broker/product coverage narrower than IBKR | Best first target |
| Tradier | Equities/options with REST API | Yes | Direct REST, PyTradier ecosystem | Strong options-oriented API shape | SDK maturity less central than direct API | Good second target |
| Interactive Brokers | Broad global multi-asset trading | Paper account, TWS/Gateway | official TWS API, `ib_async` | Very broad market coverage | High operational complexity | Later |
| Schwab | Existing Schwab brokerage accounts | Unclear for paper-style testing | `schwab-py` unofficial | Useful for Schwab users | Access/OAuth/API quirks, unofficial client | Later |
| CCXT | Crypto exchange trading | Exchange-specific | `ccxt` | Unified crypto exchange API | Crypto-only, exchange inconsistencies | Only if crypto becomes a goal |

## Alpaca

Sources:

- [Alpaca Trading API](https://docs.alpaca.markets/us/docs/trading-api)
- [Alpaca Python SDK trading docs](https://alpaca.markets/sdks/python/trading.html)
- [alpaca-py GitHub](https://github.com/alpacahq/alpaca-py)

Public docs describe Alpaca as an API-first trading platform for stocks and
crypto, with paper trading available as a real-time simulation environment. The
Python SDK docs show paper trading is selected by constructing `TradingClient`
with `paper=True`, and the SDK exposes account details, assets, and orders.
The GitHub repo identifies `alpaca-py` as the official Python SDK.

Pros:

- official Python SDK
- clear paper/live split
- no local desktop gateway requirement
- account and order APIs fit the current adapter boundary
- active-looking repository and recent release cadence
- good first candidate for fake-client -> paper-client -> live-client staging

Cons:

- asset universe is not as broad as Interactive Brokers
- paper fills can still differ from real market execution
- market-data entitlements and feed differences still need separate policy
- live enablement must be gated very carefully because paper/live use the same
  conceptual SDK surface

Suggested role:

Use Alpaca as the first real external integration, but only after the offline
live audit models and fake broker adapter exist. The first Alpaca implementation
should target paper mode, not live mode.

See [alpaca_paper_adapter.md](alpaca_paper_adapter.md) for the first Alpaca
paper adapter design boundary.

## Tradier

Sources:

- [Tradier Trading API](https://docs.tradier.com/docs/trading)
- [Tradier Endpoints](https://docs.tradier.com/docs/endpoints)
- [Tradier developer API overview](https://trade.tradier.com/developer-api/)

Tradier documents production and sandbox environments. The sandbox is described
as a paper-trading account for testing API integrations, with a separate
sandbox base URL. The trading docs cover equity orders and more complex options
orders.

Pros:

- REST API shape is straightforward
- explicit live and sandbox URLs
- options workflow appears more central than Alpaca
- useful if the strategy roadmap expands into options
- possible to implement with `httpx` directly instead of depending heavily on a
  wrapper

Cons:

- Python wrapper ecosystem is less obviously the canonical path than Alpaca's
  official SDK
- account setup and token management still need careful testing
- sandbox uses delayed market data
- direct REST implementation means more local request/response modeling work

Suggested role:

Keep Tradier as a strong second candidate, especially for options. If selected,
prefer building a small internal `httpx` client over binding the whole system to
an unofficial wrapper.

## Interactive Brokers

Sources:

- [IBKR TWS API documentation](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/)
- [ib_async on PyPI](https://pypi.org/project/ib_async/)

IBKR's API is powerful and broad, but the operational model is different. The
TWS API uses a socket protocol through Trader Workstation or IB Gateway. IBKR's
docs note that the original `ib_insync` package is legacy and no longer
updated, and that users wanting that style should migrate to `ib_async`. The
`ib_async` PyPI page shows a maintained package with recent releases, Python
3.10+ support, order management, positions, account summary, P&L, and event
handling examples.

Pros:

- broad asset coverage
- mature broker for multi-asset strategies
- `ib_async` offers a more Pythonic interface than the raw official API
- supports account, positions, open orders, historical data, and event-driven
  order status workflows

Cons:

- requires TWS or IB Gateway running and configured
- more moving parts for a solo-maintained server
- event-driven order state requires more careful reconciliation
- official support is for the direct API, not third-party wrappers
- not the simplest first live adapter

Suggested role:

Defer until the system needs broad asset coverage. If we later choose IBKR,
prototype against `ib_async` in a separate adapter package boundary and add
extra process-health checks for gateway connectivity.

## Schwab

Sources:

- [schwab-py documentation](https://schwab-py.readthedocs.io/)
- [schwab-py HTTP client docs](https://schwab-py.readthedocs.io/en/stable/client.html)
- [Schwab Trader API references surfaced through third-party docs](https://developer.schwab.com/products/trader-api--individual)

Schwab has an individual Trader API, and `schwab-py` is a community Python
client. Its docs describe it as unofficial. The docs also highlight migration
differences from TD Ameritrade, shorter token lifetimes, endpoint changes, and
Python 3.10+ support.

Pros:

- useful if the account already lives at Schwab
- community Python client exists
- supports order templates and HTTP client patterns
- can be a good fit for manual brokerage users who want automation later

Cons:

- unofficial Python package
- OAuth/token behavior is more involved
- access and product approval can be a friction point
- paper/sandbox-style testing is less clear from public docs than Alpaca or
  Tradier
- not ideal as the first broker for a safety-first implementation

Suggested role:

Do not choose Schwab first unless the user's actual brokerage account must be
Schwab. If Schwab becomes necessary, build a tiny internal adapter around
`schwab-py` and require extensive fake-client tests before touching credentials.

## CCXT

Sources:

- [CCXT GitHub](https://github.com/ccxt/ccxt)
- [CCXT manual](https://github.com/ccxt/ccxt/wiki/manual)

CCXT is a unified crypto exchange library supporting many exchanges. Its manual
documents public market data, private authenticated APIs, balances, order
creation/cancellation, open orders, closed orders, and trade history. It is not
an equities broker API.

Pros:

- broad crypto exchange coverage
- unified interface across many exchanges
- useful public and private API methods
- active ecosystem

Cons:

- crypto-only for practical purposes
- exchange behavior varies behind the unified API
- some order/history capabilities can be exchange-specific or emulated
- market structure and risk controls differ sharply from equities
- API keys are exchange-specific and must be handled separately

Suggested role:

Ignore for now unless crypto trading becomes an explicit product goal. If crypto
is added later, treat it as a separate broker/exchange adapter family.

## Packages To Avoid As First Choices

Avoid `alpaca-trade-api-python` for new work. The Alpaca GitHub page for the
older package points users to the newer `alpaca-py` SDK.

Avoid building directly on `ib_insync` for new work. IBKR's docs identify the
original `ib_insync` package as no longer updated and point users toward
`ib_async` if they want that style.

Avoid choosing a community Schwab wrapper as the first implementation unless
Schwab is required by the user's brokerage choice.

## Recommended Architecture Impact

Do not let the first chosen broker leak through the codebase.

Add these internal boundaries before choosing a real SDK:

```text
LiveOrderRequest
LiveOrderRecord
LiveFillRecord
LiveAccountSnapshot
LiveBrokerClient protocol
LiveBrokerAdapter
LiveReconciliationReport
```

The adapter can then translate:

```text
internal typed request -> broker SDK request -> internal typed record
```

This keeps the system maintainable if we start with Alpaca and later add
Tradier, IBKR, Schwab, or CCXT.

## Recommended Decision

For the next several milestones:

1. Keep implementation broker-neutral.
2. Build typed live audit artifacts.
3. Build a fake live broker adapter.
4. Select **Alpaca paper** as the first external broker integration.

Decision checkpoint before adding Alpaca:

- Do we want equities only at first?
- Is paper trading through Alpaca acceptable as the first external rehearsal?
- Are we comfortable with a separate Alpaca account and API keys?
- Do we want to keep options out of scope until later?

If the answers are yes, Alpaca is the cleanest first integration.

If options are required early, compare Alpaca vs Tradier more deeply before
adding a package dependency.

If broad multi-asset global trading is required, revisit Interactive Brokers
and budget extra engineering time for gateway operation and reconciliation.
