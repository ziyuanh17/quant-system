# Momentum Semantic-Paper Nonzero Request Rehearsal

This document records a generated-request rehearsal that deliberately produced
a nonzero local semantic-paper target and exercised the local order/fill path.

## Scope

The rehearsal used temporary local market-bar data under `/tmp` and the real
`quant semantic-paper` CLI commands. It did not contact Alpaca, load a
scheduler, touch the runtime clone, submit broker-network orders, or change
project data.

## Inputs

- Data:
  `/tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/input/AAPL.csv`
- Symbol: `AAPL`
- Quantity for a buy signal: `2`
- Fast window: `2`
- Slow window: `3`
- Initial local-paper position: `0`
- Initial local-paper cash: `1000`
- Temporary output root:
  `/tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626`

The input prices were intentionally small and deterministic: three closes at
`10`, followed by a close at `20`, so the latest legacy momentum signal is a
buy.

## Commands

The request was prepared with:

```bash
.venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id reviewed-momentum-nonzero-request \
  --data /tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/input/AAPL.csv \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 2 \
  --slow-window 3 \
  --min-rows 4 \
  --initial-cash 1000 \
  --output-root /tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/requests
```

The generated request was inspected without writing execution artifacts:

```bash
.venv/bin/quant semantic-paper inspect-activated-target \
  --request-path /tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/requests/inputs/requests/reviewed-momentum-nonzero-request.json
```

The same request was then run twice through local semantic paper:

```bash
.venv/bin/quant semantic-paper activated-target \
  --request-path /tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/requests/inputs/requests/reviewed-momentum-nonzero-request.json \
  --activation-root /tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/activation \
  --output-root /tmp/quant-semantic-paper-nonzero-request-rehearsal-20260626/output
```

## Result

The request generator produced:

- signal: `buy`
- signal date: `2026-01-04`
- reference price: `20.00`
- target quantity: `2`

Inspection reported:

- request valid now
- current position `0` shares
- approved target `2` shares
- intended order `BUY 2 AAPL`
- intended notional `$40.00`
- base rehearsal passed
- activation-consumption rehearsal passed

Both local semantic-paper command runs reused the same orchestration and reached:

- workflow status: `execution_completed`
- execution status: `satisfied`
- reconciliation report: `818e3a9e-239a-4446-8b74-65e6ea45e114`

The final local-paper state had:

- cash: `960.0`
- position: `AAPL +2` at average price `20.0`
- orders: `1`
- fills: `1`
- order status: `filled`
- fill quantity: `2`
- lifecycle event files: `4`

## Interpretation

This rehearsal proves that a generated semantic-paper request can move from a
legacy momentum buy signal to one local paper order and one fill, and that
rerunning the same command reuses the satisfied orchestration instead of
submitting a duplicate local-paper order.

The result is still local-only infrastructure evidence. It does not authorize
Alpaca, recurring scheduling, runtime deployment, broker-network submission, or
real-money trading.

