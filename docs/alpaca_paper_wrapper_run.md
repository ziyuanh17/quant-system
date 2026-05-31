# Alpaca Paper Wrapper Run

This note records the first controlled full run of the Alpaca paper server
wrapper after preflight mode was added. It is sanitized: do not add API keys,
account numbers, raw broker payloads, or raw local artifacts to this file.

## Run Summary

- Date: 2026-05-31, America/Los_Angeles
- Wrapper: `scripts/run_alpaca_paper_refresh.sh`
- Mode: full wrapper run, not preflight
- Preflight flag: `QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=false`
- Broker environment: Alpaca paper
- Symbol: AAPL
- Provider: yfinance
- Data refresh start: 2024-01-01
- Workflow status: `succeeded`
- Workflow message: `data refreshed and Alpaca paper workflow completed`
- Reconciliation status: `passed`
- Reconciliation differences: 0
- New order artifact created by this run: no
- New fill artifact created by this run: no
- New account snapshot created by this run: yes
- Open local orders after run: 0
- Open broker orders after run: 0
- Account cash observed: unchanged at the configured paper account baseline
- Position count observed: 0

## What This Run Proved

The wrapper can execute the server-style Alpaca paper workflow end to end:

```text
load .env
resolve wrapper defaults
write timestamped log
refresh yfinance market data
validate normalized market bars
evaluate the configured strategy
write an Alpaca paper account snapshot
reconcile local artifacts against Alpaca paper broker state
write a workflow record
```

No new order or fill artifact was produced. In this workflow, the broker adapter
submits an order only when the latest strategy decision is actionable. Because
the run succeeded, wrote a snapshot, and reconciled with no new order/fill
artifacts, this run exercised the wrapper and broker-read path without opening a
new paper position.

## Artifact Review

Reviewed artifact classes:

- wrapper log under `logs/`
- workflow record under `data/workflows/alpaca-paper-refresh/`
- normalized market bars under `data/normalized/market_bars/`
- validation report under `data/validation/market_bars/`
- account snapshot under `data/live/account_snapshots/`
- reconciliation report under `data/live/reconciliation/latest.json`

Observed checks:

- wrapper log recorded `preflight_only=false`
- workflow status was `succeeded`
- validation completed without reported issues
- reconciliation status was `passed`
- reconciliation differences were `0`
- no matching local or broker open order remained after the run
- no fill artifact was produced by this run

The generated `data/` and `logs/` files are local operational artifacts and
should remain uncommitted.

## Operational Lesson

Preflight and full wrapper runs now cover different parts of the server
process:

- preflight checks the launcher configuration without side effects
- the full wrapper run checks data refresh, strategy evaluation, broker reads,
  artifact writing, and reconciliation
- an actionable paper-order case still needs to be observed through the wrapper
  during a later controlled run

## Next Recommendation

Keep the wrapper in manual review mode for the next few runs. The next
improvement should make workflow records expose the latest strategy decision
and whether broker submission was skipped, so future reviews do not have to
infer a hold/no-order outcome from missing order artifacts.
