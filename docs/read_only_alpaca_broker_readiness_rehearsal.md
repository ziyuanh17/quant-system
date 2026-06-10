# Read-Only Alpaca Broker Readiness Rehearsal

This note records the broker-connected read-only rehearsal performed after the
actionable-order safety remediation and no-order wrapper preflight.

## Safety Boundary

The rehearsal did not:

- run the strategy,
- submit, cancel, or replace an order,
- refresh an order,
- recover or increase the retained AAPL paper short,
- load or enable launchd.

It used Alpaca read APIs and wrote only local snapshot and reconciliation
artifacts.

## Account Readiness

The current Alpaca paper account snapshot succeeded:

```text
cash=100290.75
buying_power=399647.20
positions=1
```

The snapshot artifact is:

```text
/Users/ziyuan/Code/quant-system-runtime/data/live/account_snapshots/6aad1a77-d1e2-4e02-bcd4-d540ebf9771a.json
```

The existing paper position remains intentionally unchanged.

## Asset and Order Readiness

Alpaca reported current AAPL metadata:

```text
tradable=true
shortable=true
easy_to_borrow=true
```

Alpaca reported:

```text
has_open_orders=false
```

Borrow availability is time-sensitive. These values demonstrate that the
readiness API path works; they do not authorize a later short order without a
fresh check.

## Reconciliation

Read-only reconciliation outcome:

```text
status=passed
differences=0
```

The report is:

```text
/Users/ziyuan/Code/quant-system-runtime/data/live/reconciliation/latest.json
```

## Outcome

The runtime can authenticate to Alpaca, read current account and asset state,
detect open orders, and reconcile local state with broker truth.

The recurring launchd service remains unloaded. No order-capable workflow is
authorized by this outcome.

## Next Gate

Before an order-capable rehearsal:

1. review and commit the preparation and read-only evidence,
2. review `docs/controlled_alpaca_paper_order_rehearsal_design.md`,
3. define the exact expected order behavior and rollback boundary,
4. obtain explicit approval immediately before any order-capable command.
