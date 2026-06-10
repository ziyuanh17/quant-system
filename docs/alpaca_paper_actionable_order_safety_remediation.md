# Alpaca Paper Actionable-Order Safety Remediation

This note records the controls added after the first scheduled actionable
Alpaca paper order exposed differences between local guard behavior and Alpaca
paper behavior.

## Safety Boundary

The recurring schedule remains unloaded. The remediation changes are verified
locally, but they do not authorize a broker-connected rehearsal or schedule
reactivation.

The existing one-share AAPL paper short is intentionally left open at the
owner's request. This remediation prevents new accidental shorts while
allowing future explicitly authorized, bounded strategy shorts. It does not
recover or alter existing broker positions.

## Root Causes and Controls

### External Orders Bypassed Position-Aware Risk Checks

Before submitting an actionable Alpaca paper order, the workflow now:

1. fails closed when Alpaca reports any unsettled broker order, including an
   order created by a previous process,
2. captures current broker cash and positions,
3. runs a projected-position order-risk check using explicit short, gross
   exposure, and buying-power-buffer limits.

A sell that would open or increase a short is rejected before broker
submission unless short selling and every required limit are explicit. See
`docs/short_selling_risk_policy.md`.

### Reconciliation Ran Before Broker Settlement

After submission, the workflow now refreshes the order until it reaches a
terminal state or the configured polling limit is exhausted. It captures the
account snapshot and reconciles only after terminal settlement.

The wrapper exposes:

```text
QUANT_ALPACA_PAPER_ORDER_POLL_ATTEMPTS
QUANT_ALPACA_PAPER_ORDER_POLL_INTERVAL_SECONDS
```

The defaults are five refresh attempts and one second between later attempts.
If the order remains unsettled, the workflow fails instead of reconciling
against an account state known to be in transition.

An actionable order must finish as `filled`. A terminal `cancelled` or
`rejected` order also fails the workflow, because broker settlement without
execution is not a successful strategy action.

### Refreshed Fills Were Not Persisted

Order refresh now goes through `LiveBrokerAdapter`. The adapter persists the
refreshed order artifact and any fills discovered during refresh. This applies
both inside the workflow and to:

```text
quant live alpaca-paper-refresh-orders
```

### Failed Workflow Status Was Not Published

The server wrapper now preserves a failed workflow exit code while still
running dashboard status publication. The wrapper exits nonzero after
publication, so launchd and the dashboard both receive the failure signal.

## Regression Coverage

Automated tests cover:

- rejecting an unauthorized Alpaca paper short before submission,
- allowing an explicitly bounded strategy short,
- rejecting submission while any broker order remains open,
- polling an accepted order to terminal state before reconciliation,
- failing when an actionable order settles without filling,
- persisting fills discovered by workflow and standalone refresh,
- publishing dashboard status after a failed workflow,
- preserving the failed wrapper exit code.

## Reactivation Gate

Do not reload the recurring schedule until:

1. the remediation changes are reviewed and committed,
2. a preflight-only wrapper run passes,
3. a controlled broker-connected paper rehearsal is explicitly approved,
4. order, fill, snapshot, reconciliation, wrapper log, and dashboard artifacts
   are reviewed,
5. the paper account is reconciled with zero unexplained differences.
