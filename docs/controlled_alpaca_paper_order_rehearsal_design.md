# Controlled Alpaca Paper Order-Capable Rehearsal Design

This design defines the first order-capable Alpaca paper rehearsal after the
June 9 actionable-order incident. It does not authorize execution.

## Objective

Prove that the remediated runtime can safely submit one deliberately tiny paper
order, observe its terminal fill, persist complete audit artifacts, and
reconcile against Alpaca without changing the intentionally retained AAPL
short.

## Approaches Considered

### Run The Strategy Workflow

Rejected. The strategy can produce a buy or sell signal for AAPL. A buy could
cover the retained short, while a sell could attempt to increase it. The exact
broker action is not fixed before execution.

### Submit And Cancel A Non-Marketable Limit Order

Deferred. The current broker-neutral order model supports only market orders
and has no local cancel command. Adding limit and cancel support would expand
the rehearsal scope, and cancellation before fill is not guaranteed.

### Submit One Tiny Buy On A Different Symbol

Selected. The order behavior is fixed before execution and cannot directly
change the retained AAPL short. A dedicated command can enforce the protected
position and all other rehearsal invariants before submission.

## Dedicated Command

Implement a separate command rather than extending or reusing the permissive
manual smoke-order command:

```text
quant live alpaca-paper-rehearsal-order
```

The command must not accept a sell side. Its only supported order is:

```text
one whole-share market buy
```

The symbol and current reference price must be explicitly provided immediately
before execution. The rehearsal symbol must be different from every protected
symbol and absent from current broker positions.

## Required Explicit Inputs

```text
--symbol <reviewed rehearsal symbol>
--reference-price <current reviewed price>
--client-order-id <unique rehearsal ID>
--protected-position AAPL=-1
--rehearsal-confirmation CONFIRM_ALPACA_PAPER_REHEARSAL_ORDER
```

The existing environment-backed safety gates remain required:

```text
QUANT_TRADING_MODE=live
QUANT_LIVE_TRADING_ENABLED=true
QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
QUANT_BROKER=alpaca-paper
QUANT_MAX_ORDER_NOTIONAL=<small reviewed cap>
```

The new confirmation phrase is deliberately separate from the general live
safety phrase. It proves that the operator approved this exact paper rehearsal,
not merely broker access.

## Pre-Submission Invariants

The command must fetch current broker truth and fail before submission unless
all checks pass:

1. Alpaca paper credentials and safety gates are valid.
2. The broker reports no open orders.
3. The protected AAPL position exists with signed quantity exactly `-1`.
4. The rehearsal symbol is not AAPL or any other protected symbol.
5. The rehearsal symbol is absent from current positions.
6. The rehearsal symbol is currently tradable.
7. Quantity is exactly one share.
8. Side is fixed to buy.
9. Reference price is positive.
10. One-share reference notional is within `QUANT_MAX_ORDER_NOTIONAL`.
11. Projected buying power remains non-negative.
12. The client order ID has not appeared in local order artifacts.

Any mismatch requires a new review. The command must not attempt to repair
positions, cancel orders, resize the order, or choose another symbol
automatically.

## Execution Flow

```text
load explicit configuration
  -> fetch pre-order account snapshot
  -> verify protected position and rehearsal invariants
  -> fetch rehearsal-symbol asset metadata
  -> submit exactly one-share buy
  -> poll submitted order to terminal state
  -> require final status filled
  -> persist order and fill artifacts
  -> fetch post-order account snapshot
  -> verify protected AAPL quantity remains -1
  -> verify rehearsal-symbol quantity is +1
  -> reconcile local artifacts with Alpaca
  -> require zero unexplained differences
  -> write dedicated rehearsal result artifact
```

The command must fail if the order is rejected, canceled, partially filled, or
does not reach terminal state within the configured polling boundary.

## Position Outcome

The expected broker position change is:

```text
AAPL: unchanged at -1
rehearsal symbol: new position at +1
```

The command must not automatically sell the rehearsal position afterward.
Automatic cleanup would introduce an unreviewed second order and make the
rehearsal harder to audit. A later cleanup decision is a separate explicitly
approved action.

## Artifacts

The rehearsal must write:

```text
data/live/orders/<id>.json
data/live/fills/<id>.json
data/live/account_snapshots/<before-id>.json
data/live/account_snapshots/<after-id>.json
data/live/reconciliation/latest.json
data/live/rehearsals/<rehearsal-id>.json
```

The dedicated rehearsal result should contain typed fields for:

- rehearsal ID and client order ID,
- protected-position expectations and observed before/after quantities,
- rehearsal symbol and observed before/after quantities,
- asset tradability result,
- order and fill artifact paths,
- snapshot artifact paths,
- reconciliation path and status,
- final rehearsal status and failure reason.

It must not contain secrets or raw broker payloads.

## Stop And Rollback Boundary

Stop immediately if:

- AAPL is not exactly `-1` before submission,
- any open order exists,
- the selected symbol already has a position,
- the symbol is not tradable,
- the order does not fill exactly one share,
- AAPL changes after submission,
- reconciliation reports any unexplained difference.

Rollback means:

```text
do not submit another order
keep launchd unloaded
capture current broker truth
persist and review evidence
```

Rollback does not mean automatically closing the rehearsal long or the
retained AAPL short.

## Execution Approval Gate

Implementation of the dedicated command may proceed after this design is
reviewed. Actual execution requires a separate explicit approval immediately
before the order-capable command, including the reviewed symbol, reference
price, maximum notional, and expected protected-position quantity.

## Implementation Outcome

The dedicated command is implemented as:

```text
quant live alpaca-paper-rehearsal-order
```

It requires both the existing live-access safety confirmation and the separate
rehearsal confirmation. It parses explicit protected-position invariants and
constructs the network-capable Alpaca client only after locally checkable gates
pass.

The service enforces the approved one-share buy shape, paper-only broker
environment, no-open-order condition, unique local client order ID, exact
protected positions, case-normalized symbol isolation, absent rehearsal-symbol
position, tradable asset, sufficient buying power, and maximum order notional.
After submission it never issues an automatic cleanup order. It writes passed
or failed typed rehearsal evidence after observing broker state and
reconciliation.

Automated tests cover protected-position drift, an existing rehearsal-symbol
position, a non-paper broker environment, successful complete evidence,
failed-order evidence with no cleanup submission, case-insensitive protected
symbols, the separate CLI confirmation, and the complete CLI path through an
in-memory Alpaca-shaped fake.

The full repository check passed with 212 tests. No command was executed
against Alpaca, no paper order was submitted, and the recurring launchd service
remains intended to stay unloaded until the controlled execution is separately
approved.

## June 10 Execution Preparation

Read-only preparation for milestone 87 completed on June 10, 2026:

- source commit `01ea29e` is on `main` and matches `origin/main`,
- the recurring launchd service remains unloaded,
- the safety environment resolves to Alpaca paper with a `$400` maximum order
  notional,
- a fresh account snapshot reported cash of `$100,290.73`, buying power of
  `$399,646.08`, and exactly one position: `AAPL = -1`,
- fresh reconciliation passed with zero differences,
- Alpaca reported no open orders,
- provisional rehearsal candidate `F` is absent from positions and reported
  as tradable, shortable, and easy to borrow, and
- the latest available `F` price was `$14.30`.

Execution stopped because Alpaca reported the market closed at
`June 10, 2026 11:16 PM ET`. The next open is `June 11, 2026 9:30 AM ET`
(`6:30 AM PT`). After the market opens, refresh broker truth and the current
`F` reference price, then request immediate explicit approval containing:

```text
symbol=F
reference price=<fresh price>
maximum order notional=400
protected position=AAPL=-1
```

Do not reuse the `$14.30` closed-market price as the execution reference
without refreshing it.

## June 11 Market-Hours Readiness Outcome

Read-only readiness was repeated on June 11, 2026 while the market was open:

```text
protected position=AAPL:-1
F position present=false
open orders=0
F tradable=true
fresh F price=$14.36
scheduler=unloaded
```

The order-capable rehearsal did not proceed because reconciliation failed
twice on values that moved between sequential market-hours reads:

```text
buying_power
positions.AAPL.last_price
```

Cash, open orders, fills, position presence, and position quantity remained
consistent. This exposed a reconciliation-policy gap rather than authorizing a
tolerance bypass. The rehearsal remains blocked until the reviewed
market-hours reconciliation policy is committed, promoted to the runtime
clone, and verified read-only.

See `docs/market_hours_live_reconciliation_policy.md`.
