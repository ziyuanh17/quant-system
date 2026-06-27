# Semantic-Target Alpaca Paper Request Runtime Rehearsal

Date: 2026-06-26

Status: In review

## Summary

This runtime-clone rehearsal exercised the broker-free Alpaca paper request
preparer using synthetic local data under `/tmp`.

It prepared:

```text
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json
```

The rehearsal did not source `.env`, print secrets, construct an Alpaca client,
contact Alpaca, inspect a paper account, submit orders, run the
order-capable Alpaca paper command, load launchd, or run a scheduler.

## Source And Runtime State

Source workspace:

```text
commit: ddc6d9e
status: ## codex/semantic-paper-infra...origin/codex/semantic-paper-infra
```

Runtime clone before fast-forward:

```text
commit: 1232347
status:
## main...origin/main [ahead 11]
?? data/semantic-target/
```

Runtime clone after fast-forward:

```text
commit: ddc6d9e
status:
## main...origin/main [ahead 14]
?? data/semantic-target/
```

The untracked `data/semantic-target/` directory is existing runtime evidence
from prior semantic-target work. It was preserved.

## Scheduler And Environment

Scheduler and launchd evidence:

```text
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
installed_plist_absent=true
```

Runtime shell environment presence:

```text
QUANT_ALPACA_PAPER_API_KEY=absent
QUANT_ALPACA_PAPER_SECRET_KEY=absent
QUANT_ALPACA_PAPER_ACCOUNT_ID=absent
QUANT_ALPACA_PAPER_URL_OVERRIDE=absent
QUANT_BROKER=absent
QUANT_MAX_ORDER_NOTIONAL=absent
```

No secret values were printed.

## Synthetic Source Request

A small deterministic AAPL CSV was written under:

```text
/tmp/quant-runtime-alpaca-paper-request-prep/AAPL.csv
```

Runtime command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id runtime-source-momentum \
  --data /tmp/quant-runtime-alpaca-paper-request-prep/AAPL.csv \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 2 \
  --slow-window 3 \
  --min-rows 4 \
  --initial-cash 1000 \
  --output-root /tmp/quant-runtime-alpaca-paper-request-prep/local-requests
```

Output:

```text
Request: /tmp/quant-runtime-alpaca-paper-request-prep/local-requests/inputs/requests/runtime-source-momentum.json
Signal: buy
Signal date: 2026-01-04
Reference price: 20.00
Target quantity: 2
```

## Alpaca Paper Request Preparation

Runtime command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target prepare-alpaca-paper-request \
  --request-id runtime-alpaca-paper-request \
  --source-request-path /tmp/quant-runtime-alpaca-paper-request-prep/local-requests/inputs/requests/runtime-source-momentum.json \
  --output-root /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs \
  --paper-output-root /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-paper-output \
  --max-order-notional 1000 \
  --allowed-max-quantity 2 \
  --valid-for-seconds 900
```

Output:

```text
Request: /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json
Source request: /tmp/quant-runtime-alpaca-paper-request-prep/local-requests/inputs/requests/runtime-source-momentum.json
Symbol: AAPL
Approved target: 2
Reference price: 20.00
Max order notional: 1000.0
Valid until: 2026-06-27T04:19:43.447991+00:00
Paper output root: /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-paper-output/runtime-alpaca-paper-request
Prepared only. No Alpaca API call was made.
```

## Request Validation

The generated request validated as `SemanticTargetAlpacaPaperOperatorRequest`:

```text
request_id=runtime-alpaca-paper-request
broker=alpaca-paper
symbol=AAPL
max_qty=2.0
enabled=True
output_root=/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-paper-output/runtime-alpaca-paper-request
```

## Artifact Counts

Runtime operational directory counts after the rehearsal:

```text
data/live/orders files=3 dirs=1
data/live/fills files=3 dirs=1
data/live/account_snapshots files=23 dirs=1
data/live/reconciliation files=1 dirs=1
data/semantic-target files=155 dirs=290
data/workflows files=9 dirs=2
data/scheduler absent
data/paper absent
data/web absent
logs files=19 dirs=1
```

The rehearsal wrote only under `/tmp`:

```text
/tmp/quant-runtime-alpaca-paper-request-prep/local-requests files=137 dirs=256
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs files=6 dirs=10
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-paper-output absent
```

Prepared Alpaca input files:

```text
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/contributor-sets/source-contributor-set.json
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/portfolio-targets/runtime-alpaca-paper-request-portfolio-target/1.json
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/risk-targets/runtime-alpaca-paper-request-risk-target/1.json
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/strategy-evaluations/0.json
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/strategy-targets/0.json
```

The future paper output root remained absent, proving the order-capable Alpaca
paper command was not run.

## Notes

One artifact-listing command used bare `sort`, which was not on the runtime
shell path:

```text
zsh:1: command not found: sort
```

That failed command was read-only. The listing was rerun successfully with
`/usr/bin/sort`.

## Verdict

Passed.

The runtime clone can prepare one reviewed Alpaca paper request from a local
semantic-paper source request without credentials, broker access, paper output,
launchd, or scheduler behavior.

## Next Gate

The next stage may prepare a reviewed one-request manual Alpaca paper API test.
Before any broker interaction, capture fresh runtime status, scheduler absence,
environment scope, request hash, and paper-account preflight evidence. The
scope remains one reviewed request only.
