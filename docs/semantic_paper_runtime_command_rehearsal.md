# Semantic-Paper Runtime Command Rehearsal

This document records the runtime-clone no-network actual-command rehearsal
for the reviewed semantic-paper command family.

The rehearsal used deterministic synthetic market data under `/tmp`, generated
one reviewed request under `/tmp`, inspected it, and ran local semantic paper
twice with all evidence under `/tmp`. It did not source `.env`, use
credentials, load launchd, contact Alpaca, write runtime data, touch
broker-network paths, or submit broker-network orders.

## Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Development branch: `codex/semantic-paper-infra`
- Development commit before this evidence update: `e1ef6c9`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Runtime clone commit: `2614ebc`
- Runtime clone status before rehearsal: clean

Scheduler state before rehearsal:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501

installed_plist_absent=true
```

Runtime operational directory baseline before rehearsal:

```text
data/live/orders exists
data/live/fills exists
data/live/account_snapshots exists
data/live/reconciliation exists
data/semantic-target absent
data/workflows exists
data/scheduler absent
data/paper absent
data/web absent
logs exists
```

Runtime `__pycache__` directory count before rehearsal:

```text
422
```

## Commands

The rehearsal root was:

```text
/tmp/quant-runtime-semantic-paper-command-rehearsal-20260626
```

Synthetic market bars:

```text
date,symbol,open,high,low,close,volume
2026-01-01,AAPL,10,11,9,10,1000
2026-01-02,AAPL,10,11,9,10,1000
2026-01-03,AAPL,10,11,9,10,1000
2026-01-04,AAPL,20,21,19,20,1000
```

Request preparation from the runtime clone:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id runtime-reviewed-momentum-request \
  --data /tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/input/AAPL.csv \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 2 \
  --slow-window 3 \
  --min-rows 4 \
  --initial-cash 1000 \
  --output-root /tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/requests
```

Inspection from the runtime clone:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper inspect-activated-target \
  --request-path /tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/requests/inputs/requests/runtime-reviewed-momentum-request.json
```

Local semantic-paper execution from the runtime clone, run twice with the same
request:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target \
  --request-path /tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/requests/inputs/requests/runtime-reviewed-momentum-request.json \
  --activation-root /tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/activation \
  --output-root /tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/output
```

## Result

Request preparation reported:

- signal: `buy`
- signal date: `2026-01-04`
- reference price: `20.00`
- target quantity: `2`
- request path:
  `/tmp/quant-runtime-semantic-paper-command-rehearsal-20260626/requests/inputs/requests/runtime-reviewed-momentum-request.json`

Inspection reported:

- request valid now
- current position `0` shares
- approved target `2` shares
- intended order `BUY 2 AAPL`
- intended notional `$40.00`
- base rehearsal passed
- activation-consumption rehearsal passed
- inspection created no activation or execution artifacts

Both local semantic-paper executions reported:

- activation decision: `allowed`
- orchestration: `runtime-reviewed-momentum-request-orchestration`
- workflow status: `execution_completed`
- execution status: `satisfied`
- reconciliation report: `9a84e2ad-97fc-4084-98b9-184c85033351`

The final synthetic local-paper state was:

- cash: `960.0`
- position: `AAPL +2` at average price `20.0`
- orders: `1`
- fills: `1`
- order status: `filled`
- fill quantity: `2`
- lifecycle events: `4`

## Runtime State After Rehearsal

Runtime clone status after rehearsal:

```text
git status --short --branch
## main...origin/main
```

Runtime operational directories after rehearsal:

```text
data/live/orders exists
data/live/fills exists
data/live/account_snapshots exists
data/live/reconciliation exists
data/semantic-target absent
data/workflows exists
data/scheduler absent
data/paper absent
data/web absent
logs exists
```

Runtime `__pycache__` directory count after rehearsal:

```text
422
```

## Interpretation

The runtime clone can run the reviewed semantic-paper CLI path end to end
against synthetic reviewed inputs while keeping all generated evidence under
`/tmp`. Repeating the same request reused the satisfied orchestration and did
not create a duplicate local-paper order or fill.

This is still a no-network, synthetic-input rehearsal. It does not authorize
live data use, runtime data writes, recurring scheduling, Alpaca semantic
targets, broker-network orders, fills, or real-money trading.

