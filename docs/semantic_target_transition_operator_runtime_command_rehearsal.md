# Semantic-Target Transition Operator Runtime Command Rehearsal

This document records the runtime-clone command rehearsal for the local
semantic-paper transition operator and its evidence verifier.

The rehearsal used deterministic synthetic inputs under `/tmp`, generated one
reviewed request under `/tmp`, ran the explicit transition-leg local paper
operator twice, verified the evidence, and verified the persisted report. It
did not source `.env`, use credentials, load launchd, contact Alpaca, write
runtime data, touch broker-network paths, or submit broker-network orders.

## Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Development branch: `codex/semantic-paper-infra`
- Reviewed source commit: `daf0cd4`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Runtime branch used for command rehearsal: `codex/semantic-paper-infra`
- Runtime commit used for command rehearsal: `daf0cd4`
- Runtime clone was restored to `main` after the rehearsal.

Before switching branches, the runtime clone had existing untracked local
semantic-target evidence. It was preserved in a reversible git stash:

```text
stash@{0}: On main: codex-runtime-transition-rehearsal-prep
```

Scheduler state before rehearsal:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501

installed_plist_absent=true
```

Runtime operational directory baseline while on the reviewed branch:

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

## Commands

The rehearsal root was:

```text
/tmp/quant-runtime-transition-operator-rehearsal-20260630
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
  --request-id runtime-transition-request \
  --data /tmp/quant-runtime-transition-operator-rehearsal-20260630/input/AAPL.csv \
  --symbol AAPL \
  --quantity 3 \
  --current-position -2 \
  --current-average-price 100 \
  --fast-window 2 \
  --slow-window 3 \
  --min-rows 4 \
  --initial-cash 1000 \
  --output-root /tmp/quant-runtime-transition-operator-rehearsal-20260630/requests
```

Inspection from the runtime clone:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper inspect-activated-target \
  --request-path /tmp/quant-runtime-transition-operator-rehearsal-20260630/requests/inputs/requests/runtime-transition-request.json
```

Transition operator, run twice with the same reviewed request:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper transition-target \
  --request-path /tmp/quant-runtime-transition-operator-rehearsal-20260630/requests/inputs/requests/runtime-transition-request.json \
  --output-root /tmp/quant-runtime-transition-operator-rehearsal-20260630/output
```

Evidence verifier and persisted-report verifier:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper verify-transition-target \
  --request-path /tmp/quant-runtime-transition-operator-rehearsal-20260630/requests/inputs/requests/runtime-transition-request.json \
  --output-root /tmp/quant-runtime-transition-operator-rehearsal-20260630/output \
  --report-path /tmp/quant-runtime-transition-operator-rehearsal-20260630/reports/transition-verification.json

PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper verify-transition-report \
  --report-path /tmp/quant-runtime-transition-operator-rehearsal-20260630/reports/transition-verification.json
```

## Result

Request preparation reported:

- signal: `buy`
- signal date: `2026-01-04`
- reference price: `20.00`
- target quantity: `3`
- request path:
  `/tmp/quant-runtime-transition-operator-rehearsal-20260630/requests/inputs/requests/runtime-transition-request.json`

Inspection reported:

- request valid now;
- current position `-2` shares;
- approved target `3` shares;
- intended net order `BUY 5 AAPL`;
- intended notional `$100.00`;
- base rehearsal passed;
- activation-consumption rehearsal passed;
- inspection created no activation or execution artifacts.

The first transition-operator run reported:

- execution plan: `execution-runtime-transition-request-risk-target-r1`
- transition plan: `transition-execution-runtime-transition-request-risk-target-r1`
- execution status: `satisfied`
- leg statuses: `reconciled, reconciled`
- reconciliations: `2`

The second transition-operator run reported the same satisfied execution plan
and transition plan with:

- leg statuses: `reconciled, reconciled`
- reconciliations: `0`

This proves restart reuse: the second run did not create new transition-leg
execution or reconciliation evidence.

The verifier reported:

- passed: `yes`
- final status: `satisfied`
- legs: `2/2`
- orders: `2`
- fills: `2`
- reconciliations: `2`
- final position: `3`

The persisted report verifier also passed.

Final synthetic local-paper state:

```text
cash=900.0
positions=[{'symbol': 'AAPL', 'quantity': 3, 'average_price': 20.0, 'last_price': 20.0}]
orders=2
order_quantities=[2, 3]
fills=2
fill_quantities=[2, 3]
report_passed=True
report_legs=2/2
report_final_position=3
```

## Runtime State After Rehearsal

Runtime clone status immediately after the command run on the reviewed branch:

```text
## codex/semantic-paper-infra...origin/codex/semantic-paper-infra
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

The runtime clone was then restored to `main`:

```text
## main...origin/main [ahead 20]
stash@{0}: On main: codex-runtime-transition-rehearsal-prep
```

The stash preserves the pre-existing untracked runtime semantic-target
evidence. It was not deleted.

## Interpretation

The runtime clone can run the reviewed local transition-operator command family
against synthetic reviewed inputs while keeping all generated evidence under
`/tmp`. The local transition path correctly represented a cross-zero move as
two legs, `close_short BUY 2` and `open_long BUY 3`, then the verifier produced
a durable passing report.

This is still a no-network, synthetic-input rehearsal. It does not authorize
live data use, runtime data writes, recurring scheduling, Alpaca semantic
targets, broker-network orders, fills, or real-money trading.
