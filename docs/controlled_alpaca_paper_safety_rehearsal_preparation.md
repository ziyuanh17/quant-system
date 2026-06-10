# Controlled Alpaca Paper Safety Rehearsal Preparation

This note records the no-order preparation completed before any
broker-connected Alpaca paper safety rehearsal.

## Scope

This preparation intentionally did not:

- access Alpaca,
- refresh market data,
- run the strategy,
- submit or cancel an order,
- alter the existing AAPL paper short,
- load or enable launchd.

## Runtime Sync

The runtime clone was fast-forwarded from:

```text
e0191d259eefcdce8e40a1a7c9b12273fac612e0
```

to the reviewed source commit:

```text
6d83c2fc2030fa9afce44697bdd6b736dae3a124
```

The existing generated `site/status.json` modification was preserved. Runtime
dependencies were refreshed from the committed lockfile with the `dev` and
`broker-alpaca` extras.

Runtime verification passed:

```text
ruff: passed
pyright: passed
pytest: 204 passed
```

## Preflight-Only Run

The wrapper was run with an explicit process-level override:

```text
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true
```

The resulting log is:

```text
/Users/ziyuan/Code/quant-system-runtime/logs/alpaca-paper-refresh-20260610T060950Z.log
```

The log records:

```text
preflight_only=true
preflight completed without broker submission
```

## Artifact Comparison

Before and after preflight:

| Artifact | Before | After |
| --- | ---: | ---: |
| Order records | 1 | 1 |
| Fill records | 0 | 0 |
| Account snapshots | 6 | 6 |
| Alpaca paper workflow records | 5 | 5 |

Only the expected wrapper log was added. The recurring launchd service remains
unloaded.

## Runtime Short Policy

The runtime `.env` does not currently define the bounded short-selling policy
variables. This resolves to the fail-closed default:

```text
short selling disabled
```

Do not enable short selling or choose production limits as part of the first
rehearsal. Limit selection requires a separate review.

## Newly Identified Stop Gate

The current paper account intentionally retains a one-share AAPL short. A full
strategy workflow can produce:

- a `sell` signal, which the disabled short policy would reject before
  increasing the short, or
- a `buy` signal, which could submit an order that covers the existing short.

Because the owner explicitly requested that the short not be recovered, do not
run an order-capable strategy rehearsal yet.

## Next Rehearsal

The next step is a broker-connected **read-only readiness rehearsal**. It
should verify current credentials, account state, open orders, AAPL asset
metadata, and local reconciliation without submitting, canceling, or modifying
an order.

Only after reviewing that evidence should an order-capable rehearsal be
designed and explicitly approved.

