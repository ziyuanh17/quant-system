# Alpaca Paper Smoke Execution

This note records the first broker-connected Alpaca paper smoke run. It is
sanitized: do not add API keys, account numbers, raw broker payloads, or raw
local artifacts to this file.

## Run Summary

- Date: 2026-05-30 to 2026-05-31, America/Los_Angeles
- Broker environment: Alpaca paper
- Smoke symbol: AAPL
- Order size: 1 share
- Order type used by the adapter: paper market order
- Client order ID: `alpaca-paper-smoke-20260530-225538`
- Broker order ID: `c85c1322-f73f-416d-ba5e-82eef59992a5`
- Initial broker status after submission: `accepted`
- Final broker status after dashboard cancellation: `cancelled`
- Filled quantity: 0
- Final open matching broker orders: 0
- Final local open orders after refresh: 0
- Account cash impact observed: none
- Position impact observed: none

## What Happened

The smoke run submitted a tiny paper order through the system's safety-gated
Alpaca paper command. The order was accepted by Alpaca paper, then cancelled
manually from the Alpaca dashboard before any fill occurred.

The manual dashboard cancellation changed broker state outside the local audit
artifact flow. Before refreshing from broker truth, the local order artifact
still showed the earlier `accepted` status. That mismatch was expected once we
understood the sequence: the broker had newer state than the local JSON record.

After adding and running the local broker refresh command, the order artifact
was updated to `cancelled`. Reconciliation then passed with zero differences.

## Commands Used

Safety and snapshot commands were run with environment-backed credentials and
the live-mode guardrails enabled:

```bash
quant live alpaca-paper-snapshot --from-env
quant live alpaca-paper-order --from-env ...
quant live alpaca-paper-refresh-orders --from-env
quant live alpaca-paper-reconcile --from-env
```

The order command intentionally used an explicit one-share smoke order and a
client order ID unique to this run. The exact command should not be copied
blindly for future runs; use the smoke runbook instead so the reference price,
symbol, and client order ID are refreshed each time.

## Artifact Review

Reviewed artifact classes:

- order record under `data/live/orders/`
- account snapshot under `data/live/account_snapshots/`
- reconciliation report under `data/live/reconciliation/latest.json`

Observed checks:

- no API key or secret key was needed in committed documentation
- broker environment remained paper-only
- client order ID matched the intended smoke ID
- local order status matched broker status after refresh
- reconciliation status was `passed`
- reconciliation differences were `0`
- filled quantity remained `0`

The generated `data/live/` files are local operational artifacts and should
remain uncommitted.

## Operational Lesson

Broker dashboards and broker APIs are both sources of broker truth. If an order
is cancelled, replaced, or otherwise changed outside this codebase, local audit
artifacts must be refreshed before reconciliation:

```bash
quant live alpaca-paper-refresh-orders --from-env
quant live alpaca-paper-reconcile --from-env
```

This is not just cleanup. Without the refresh step, reconciliation can report
drift because the local artifact is stale, not because the broker cancellation
failed.

## Go/No-Go Note

Go for the next controlled step:

- the broker credential path worked against Alpaca paper
- the safety gate blocked accidental use unless explicitly enabled
- the tiny paper order was accepted by the broker
- manual cancellation was confirmed through broker truth
- local artifacts can now be refreshed after external broker changes
- reconciliation passed after refresh

Not yet go for unattended real-money trading:

- this run used paper trading only
- no real-money account path is enabled
- scheduled Alpaca paper runs should still begin cautiously
- fill behavior still needs observation during a market-open paper run
- cancellation, replacement, partial-fill, and rejected-order cases need more
  paper-account evidence before real trading is considered

## Next Recommendation

Use the Alpaca paper server wrapper in a controlled recurring mode only after
reviewing this note and the runbook. Start with paper-only runs, small sizing,
sanitized status publishing, and regular reconciliation review.
