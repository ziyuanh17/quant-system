# Semantic-Paper Manual Operator Run

This document records the first manual runtime semantic-paper local-data run.

The run used reviewed local AAPL market-bar data from the runtime clone,
generated one reviewed request under runtime `data/semantic-target`, inspected
it, and ran local semantic paper twice. It did not source `.env`, use
credentials, load launchd, contact Alpaca, connect to a broker, submit
broker-network orders, or create broker-network fills.

## Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Development branch: `codex/semantic-paper-infra`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Runtime clone commit: `2614ebc`
- Runtime clone status before run: clean
- Request ID: `reviewed-aapl-momentum-local-paper-20260626`

Scheduler state before run:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501

installed_plist_absent=true
```

Reviewed local input:

```text
14889f58cb558119f521121ca3030ff267db1144721b9f82012138738b3fed77  data/normalized/market_bars/AAPL.csv
```

Runtime operational directory baseline before run:

```text
data/live/orders 1781193481
data/live/fills 1781249658
data/live/account_snapshots 1781294101
data/live/reconciliation 1780207045
data/semantic-target absent
data/workflows 1781149085
data/scheduler absent
data/paper absent
data/web absent
logs 1781294100
```

## Commands

Prepare the reviewed request:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id reviewed-aapl-momentum-local-paper-20260626 \
  --data data/normalized/market_bars/AAPL.csv \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 5 \
  --slow-window 20 \
  --min-rows 20 \
  --initial-cash 100000 \
  --output-root data/semantic-target/manual-local-paper/requests/reviewed-aapl-momentum-local-paper-20260626
```

Inspect the generated request:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper inspect-activated-target \
  --request-path data/semantic-target/manual-local-paper/requests/reviewed-aapl-momentum-local-paper-20260626/inputs/requests/reviewed-aapl-momentum-local-paper-20260626.json
```

Run local semantic paper twice:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target \
  --request-path data/semantic-target/manual-local-paper/requests/reviewed-aapl-momentum-local-paper-20260626/inputs/requests/reviewed-aapl-momentum-local-paper-20260626.json \
  --activation-root data/semantic-target/manual-local-paper/activation/reviewed-aapl-momentum-local-paper-20260626 \
  --output-root data/semantic-target/manual-local-paper/output/reviewed-aapl-momentum-local-paper-20260626
```

## Result

Request preparation reported:

- signal: `hold`
- signal date: `2026-06-12`
- reference price: `291.38`
- target quantity: `0`

Inspection reported:

- request valid now
- current position `0` shares
- approved target `0` shares
- intended order: none
- base rehearsal passed
- activation-consumption rehearsal passed
- inspection created no activation or execution artifacts

Both local semantic-paper runs reported:

- activation decision: `allowed`
- orchestration:
  `reviewed-aapl-momentum-local-paper-20260626-orchestration`
- workflow status: `execution_completed`
- execution status: `satisfied`
- reconciliation report: `1d8a3e75-20c0-4884-beb8-b0831ffaeb2b`

The final local-paper state was:

- cash: `100000.0`
- positions: none
- orders: `0`
- fills: `0`
- lifecycle events: `1`

This zero-order result is expected because the latest reviewed local AAPL
momentum signal was `hold` and the initial local-paper position was flat.

## Key Artifact Hashes

```text
d90e269b450f9e1c5b02aad0eb53aebaaab0c680c11daf5a73b6f961b63e1bb7  data/semantic-target/manual-local-paper/requests/reviewed-aapl-momentum-local-paper-20260626/inputs/requests/reviewed-aapl-momentum-local-paper-20260626.json
eab285fce6b9afae78632cc5af24f5d572c8df80f4bd49ef762944cca52efaa2  data/semantic-target/manual-local-paper/output/reviewed-aapl-momentum-local-paper-20260626/orchestrations/reviewed-aapl-momentum-local-paper-20260626-orchestration.json
38c435925af2d94b820908be2dede11e6fba8ce8f469bcf68493745ea75b2825  data/semantic-target/manual-local-paper/output/reviewed-aapl-momentum-local-paper-20260626/semantic-paper/state.json
069b6c4e9ad361ae234617b2d3639c23d8a24bb75cc970e53dc720e8869fc010  data/semantic-target/manual-local-paper/output/reviewed-aapl-momentum-local-paper-20260626/semantic-paper/reconciliations/execution-reviewed-aapl-momentum-local-paper-20260626-risk-target-r1/1d8a3e75-20c0-4884-beb8-b0831ffaeb2b.json
```

## Runtime State After Run

Runtime clone status after run:

```text
git status --short --branch
## main...origin/main
?? data/semantic-target/
```

Runtime operational directories after run:

```text
data/live/orders 1781193481
data/live/fills 1781249658
data/live/account_snapshots 1781294101
data/live/reconciliation 1780207045
data/semantic-target 1782530116
data/workflows 1781149085
data/scheduler absent
data/paper absent
data/web absent
logs 1781294100
```

Runtime `__pycache__` directory count after run:

```text
422
```

## Interpretation

The manual runtime semantic-paper local-data path can generate, inspect, and
run one reviewed local-data request while keeping broker-network paths unused.
The only runtime working-tree change is the expected untracked
`data/semantic-target` local-paper evidence root.

This run does not authorize recurring scheduling, Alpaca semantic targets,
broker-network orders, broker-network fills, or real-money trading.

