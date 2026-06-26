# Momentum Semantic-Paper Request Rehearsal

This document records the first rehearsal of `quant semantic-paper
prepare-momentum-request` using the local AAPL market-bar file.

## Scope

The rehearsal covered only local request preparation, read-only inspection, and
local semantic-paper execution. It did not contact Alpaca, load a scheduler,
touch the runtime clone, submit broker-network orders, or change project data.

## Inputs

- Data: `data/normalized/market_bars/AAPL.csv`
- Symbol: `AAPL`
- Quantity for a buy signal: `2`
- Fast window: `5`
- Slow window: `20`
- Initial local-paper position: `0`
- Initial local-paper cash: `100000`
- Temporary output root:
  `/tmp/quant-semantic-paper-request-rehearsal-20260626135828`

## Commands

```bash
.venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id reviewed-momentum-request \
  --data data/normalized/market_bars/AAPL.csv \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 5 \
  --slow-window 20 \
  --min-rows 20 \
  --initial-cash 100000 \
  --output-root /tmp/quant-semantic-paper-request-rehearsal-20260626135828/requests
```

The generated request was inspected without writing execution artifacts:

```bash
.venv/bin/quant semantic-paper inspect-activated-target \
  --request-path /tmp/quant-semantic-paper-request-rehearsal-20260626135828/requests/inputs/requests/reviewed-momentum-request.json
```

The same request was then run twice through local semantic paper:

```bash
.venv/bin/quant semantic-paper activated-target \
  --request-path /tmp/quant-semantic-paper-request-rehearsal-20260626135828/requests/inputs/requests/reviewed-momentum-request.json \
  --activation-root /tmp/quant-semantic-paper-request-rehearsal-20260626135828/activation \
  --output-root /tmp/quant-semantic-paper-request-rehearsal-20260626135828/output
```

## Result

The latest legacy momentum signal was `hold` on `2023-12-29` at reference price
`192.53`. With a starting local-paper position of `0`, the translated semantic
target was `0` shares.

Inspection reported:

- request valid now
- current position `0` shares
- approved target `0` shares
- intended order `none`
- base rehearsal passed
- activation-consumption rehearsal passed

Both local semantic-paper command runs reused the same orchestration and reached:

- workflow status: `execution_completed`
- execution status: `satisfied`
- reconciliation report: `fdb16f3b-e4ca-4c46-82a4-10d354d3f312`

The final local-paper state had:

- cash: `100000.0`
- positions: none
- orders: `0`
- fills: `0`
- semantic-paper snapshots: `4`
- lifecycle events: `1`

## Interpretation

This rehearsal proves the real local-data request generator can produce a valid
reviewed semantic-paper request and that the local semantic-paper path can
satisfy an already-flat target without creating unnecessary orders. It does not
prove a generated real-data buy or sell request; the earlier synthetic rehearsal
covered the local order/fill path with a translated `BUY 2 AAPL` target.

