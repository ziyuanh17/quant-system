# Semantic-Paper Runtime Command Rehearsal Design

This document designs the next runtime-clone rehearsal for the reviewed
semantic-paper command family.

It is a design only. It does not run request generation, inspect a request, run
local semantic paper, source `.env`, use credentials, load launchd, contact
Alpaca, connect to a broker, or submit orders.

In plain language, this rehearsal would answer one narrow question:

```text
Can the runtime clone run the reviewed semantic-paper CLI commands against
synthetic inputs while keeping all generated evidence outside the runtime data
tree?
```

## Current Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit for the import/help rehearsal: `2614ebc`
- Runtime clone already verified package import and semantic-paper CLI help at
  reviewed source `2614ebc`.

The command family under review is:

```bash
quant semantic-paper prepare-momentum-request
quant semantic-paper inspect-activated-target
quant semantic-paper activated-target
```

## Scope

The execution stage may only:

1. verify the development workspace is clean;
2. verify the runtime clone is clean and at the reviewed source;
3. verify the recurring Alpaca paper launchd job is not loaded;
4. build deterministic synthetic market-bar input under `/tmp`;
5. run `prepare-momentum-request` from the runtime clone with all output under
   `/tmp`;
6. run `inspect-activated-target` against the generated `/tmp` request;
7. run `activated-target` twice against the generated `/tmp` request, with
   activation and local-paper output under `/tmp`;
8. verify the resulting local semantic-paper state has exactly one local order,
   one fill, and final `AAPL +2`;
9. verify repeated execution reused the same orchestration and did not create a
   duplicate order or fill;
10. verify no runtime data, scheduler, paper, Alpaca, broker-network order, or
   fill path changed.

The execution stage must not:

- run any hand-authored production request file;
- use any runtime `.env`;
- read broker credentials;
- write under `/Users/mochifufu/Code/quant-system-runtime/data`;
- write under `/Users/mochifufu/Code/quant-system-runtime/logs`;
- load, unload, or kickstart launchd;
- contact Alpaca;
- submit broker-network orders;
- reuse live market data or live account state.

## Planned Commands

The rehearsal should run from the runtime clone with bytecode writing disabled
and with every generated artifact rooted under `/tmp`:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
root=/tmp/quant-runtime-semantic-paper-command-rehearsal
rm -rf "$root"
mkdir -p "$root/input"
```

Create deterministic synthetic market bars:

```bash
cat > "$root/input/AAPL.csv" <<'CSV'
date,symbol,open,high,low,close,volume
2026-01-01,AAPL,10,11,9,10,1000
2026-01-02,AAPL,10,11,9,10,1000
2026-01-03,AAPL,10,11,9,10,1000
2026-01-04,AAPL,20,21,19,20,1000
CSV
```

Prepare the reviewed request:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id runtime-reviewed-momentum-request \
  --data "$root/input/AAPL.csv" \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 2 \
  --slow-window 3 \
  --min-rows 4 \
  --initial-cash 1000 \
  --output-root "$root/requests"
```

Inspect the generated request without writing execution artifacts:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper inspect-activated-target \
  --request-path "$root/requests/inputs/requests/runtime-reviewed-momentum-request.json"
```

Run the same generated request twice through local semantic paper:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target \
  --request-path "$root/requests/inputs/requests/runtime-reviewed-momentum-request.json" \
  --activation-root "$root/activation" \
  --output-root "$root/output"

PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target \
  --request-path "$root/requests/inputs/requests/runtime-reviewed-momentum-request.json" \
  --activation-root "$root/activation" \
  --output-root "$root/output"
```

Verify the generated local-paper state:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

root = Path("/tmp/quant-runtime-semantic-paper-command-rehearsal/output")
state = json.loads((root / "semantic-paper" / "state.json").read_text())
orchestration = json.loads(
    (root / "orchestrations" / "runtime-reviewed-momentum-request-orchestration.json").read_text()
)
print(f"cash={state['cash']}")
print(f"positions={state['positions']}")
print(f"orders={len(state['orders'])}")
print(f"fills={len(state['fills'])}")
print(f"status={orchestration['status']}")
print(f"execution_status={orchestration['execution_status']}")
print(f"reconciliation={orchestration['reconciliation_report_id']}")
PY
```

The local semantic-paper execution is allowed only because the request and all
paper evidence are synthetic and rooted under `/tmp`. It remains broker-free
and must not touch runtime operational directories.

## Evidence To Capture

Before running the rehearsal, capture:

- development workspace status and commit;
- runtime clone status and commit;
- scheduler not-loaded evidence;
- installed launchd plist absence;
- runtime operational directory snapshot;
- existing runtime `__pycache__` directory count.

After running the rehearsal, capture:

- generated request path;
- inspection summary and intended order;
- first and second command statuses;
- orchestration ID and reconciliation ID;
- final local-paper cash, position, order count, and fill count;
- runtime clone status;
- runtime operational directory snapshot;
- runtime `__pycache__` directory count.

Operational directories to compare:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/semantic-target
data/workflows
data/scheduler
data/paper
data/web
logs
```

Existing historical runtime directories may remain present. The pass condition
is that the rehearsal does not create or modify runtime operational evidence.

## Pass Criteria

The rehearsal passes only if:

- the runtime clone starts clean;
- the runtime clone remains clean;
- the scheduler remains unloaded;
- the installed launchd plist remains absent;
- all generated inputs and outputs are under `/tmp`;
- request preparation reports a `buy` signal and target quantity `2`;
- inspection reports intended `BUY 2 AAPL`;
- both local semantic-paper runs reach `execution_completed` and `satisfied`;
- the two runs reuse the same orchestration and reconciliation evidence;
- final synthetic local-paper state has exactly one order, one fill, and
  `AAPL +2`;
- no runtime `data` or `logs` path is created or modified by the rehearsal;
- no `.env` file is sourced;
- no broker credentials are read;
- no Alpaca or broker-network command is invoked.

## Fail-Closed Conditions

Stop immediately if:

- the runtime clone is dirty before the rehearsal;
- the runtime clone is not at the reviewed source;
- launchd reports the Alpaca paper job is loaded;
- the installed Alpaca paper plist exists;
- any command needs `.env`, credentials, or network access;
- any generated artifact would be written under the runtime clone data or logs
  tree;
- inspection does not report the expected `BUY 2 AAPL` intent;
- repeated execution creates a second local order or fill;
- runtime operational directories change unexpectedly;
- the runtime clone becomes dirty.

## Explicit Non-Authorization

Approving this design would not authorize executing the rehearsal. A later
stage must separately approve the runtime-clone no-network actual-command
rehearsal execution.

Even if that execution passes, it would not authorize running real reviewed
operator requests, using live data, loading launchd, recurring scheduling,
Alpaca semantic targets, broker access, broker-network orders, fills, or
real-money trading.

