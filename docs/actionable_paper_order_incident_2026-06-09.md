# Actionable Alpaca Paper Order Incident Review

This note records the first actionable order submitted by the recurring Alpaca
paper workflow and the resulting reconciliation failure.

## Summary

On June 9, 2026, the MacBook Air launchd job naturally ran the Alpaca paper
refresh workflow. The momentum strategy produced a `sell` signal for one AAPL
share while the Alpaca paper account held no AAPL position.

The workflow submitted and Alpaca filled the sell order, creating a short
position of one AAPL share. The workflow then captured an account snapshot
before the fill was reflected in that snapshot and immediately reconciled
local artifacts against newer broker truth. Reconciliation failed.

## Incident Timeline

```text
2026-06-09T19:59:06Z wrapper started
2026-06-09T19:59:10Z sell market order submitted
2026-06-09T19:59:10Z local order recorded as accepted
2026-06-09T19:59:11Z local account snapshot captured without AAPL position
2026-06-09T19:59:11Z broker reported short AAPL position
2026-06-09T19:59:11Z reconciliation failed
```

The workflow record is:

```text
data/workflows/alpaca-paper-refresh/23430105-8b39-4eaf-97f6-6a27cc3bd7b7.json
```

The order record is:

```text
data/live/orders/50e26168-a9f9-4ad4-bc07-05cc74456f53.json
```

## Order Outcome

```text
client_order_id=momentum:AAPL:2026-06-09:sell
side=sell
quantity=1
reference_price=291.00
broker_order_id=72e40adf-27ed-4c46-99db-57a7caf9baa0
final_status=filled
```

The resulting Alpaca paper account state includes a short AAPL position:

```text
symbol=AAPL
quantity=-1
average_price=290.75
```

No real-money order was submitted. This incident is limited to the Alpaca
paper account.

## Initial Reconciliation Failure

The initial reconciliation compared a stale local snapshot with newer broker
truth:

```text
local cash=100000.00
broker cash=100290.75
local AAPL position=None
broker AAPL position=-1
```

This produced differences in cash, buying power, and position presence.

## Containment and Recovery

The recurring MacBook Air launchd schedule was unloaded without deleting its
installed plist. A subsequent `launchctl print` confirmed the service is
absent.

Read-only recovery steps:

```text
refresh local Alpaca paper order artifacts
capture a current Alpaca paper account snapshot
reconcile refreshed local artifacts against broker truth
```

Recovery outcome:

```text
refreshed order status=filled
current positions=1
reconciliation status=passed
reconciliation differences=0
```

The short position remains open. Closing it requires a separate explicitly
approved buy order.

## Root Causes

### Short-Selling Policy Gap

The local simulated paper broker rejects sells greater than an owned position.
The Alpaca paper workflow does not apply an equivalent position-aware risk
check before external paper submission. Alpaca therefore accepted the sell as
a short order.

### Reconciliation Timing Gap

The workflow submits an asynchronous external broker order, immediately takes
one account snapshot, and immediately reconciles. It does not poll the order to
a terminal state or wait for account state to reflect the fill.

### Fill Artifact Refresh Gap

The standalone order-refresh command updates the local order artifact to
`filled`, but it does not persist the corresponding fill artifact. Current
reconciliation can still pass because local and broker fill counts are both
zero through this client path, but the append-only fill audit trail is
incomplete.

### Dashboard Failure Visibility Gap

The wrapper publishes dashboard status only after a successful workflow
command. When the workflow exits nonzero, the dashboard remains at the prior
healthy status instead of exposing the latest failure.

## Remediation Outcome

The required code controls and regression tests are implemented in the local
review bundle:

1. position-aware risk checks reject naked sells before submission,
2. any unsettled Alpaca broker order blocks a new strategy submission,
3. submitted orders are polled to terminal state before snapshot and
   reconciliation,
4. fills discovered during order refresh are persisted,
5. failed workflows still publish dashboard status and preserve a nonzero
   wrapper exit code.

The existing one-share AAPL paper short is intentionally left open at the
owner's request. No recovery order is required for this remediation.

See `docs/alpaca_paper_actionable_order_safety_remediation.md` for the control
details and schedule-reactivation gate. Do not reload the recurring schedule
until the remediation is reviewed and a controlled rehearsal is explicitly
approved.
