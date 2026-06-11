# Market-Hours Live Reconciliation Policy

This document defines which Alpaca paper reconciliation comparisons represent
hard broker-state drift and which represent expected market-hours movement.

## Motivation

On June 11, 2026, controlled rehearsal readiness passed every read-only
pre-order gate except reconciliation. Two immediate snapshot/reconciliation
attempts failed because values changed between consecutive broker reads:

```text
buying_power
positions.AAPL.last_price
```

Cash, open orders, fills, position presence, and position quantity did not
change. The market was open, so buying power and the current AAPL mark moved
while the two API calls were in flight.

Treating those volatile values as hard drift makes correct market-hours
reconciliation nearly impossible and could incorrectly fail a successfully
completed controlled rehearsal.

## Hard Differences

The following comparisons remain fail-causing reconciliation differences:

- open-order presence and status,
- fill presence, symbol, side, quantity, price, and commission,
- account cash,
- position presence,
- position quantity,
- position average price.

These values represent durable order, fill, or account state. An unexplained
mismatch means local evidence and broker truth disagree.

## Volatile Observations

The following comparisons are preserved as non-failing observations:

- account buying power,
- position last price.

These values can legitimately change between sequential API reads while the
market is open. A value outside the configured numeric tolerance is written to
`LiveReconciliationReport.observations` with both local and broker values.

Observations remain visible evidence. They are not silently discarded, but
they do not make reconciliation fail when all hard state agrees.

## Safety Boundary

This policy does not:

- widen or bypass hard reconciliation tolerances,
- ignore cash or position-quantity drift,
- ignore missing or inconsistent orders and fills,
- change pre-trade buying-power checks,
- submit, cancel, replace, or recover any order,
- authorize the controlled Alpaca paper rehearsal.

The controlled rehearsal remains blocked until this remediation is reviewed,
committed, promoted to the runtime clone, and a fresh read-only reconciliation
passes under the reviewed policy.
