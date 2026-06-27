# Semantic-Target Alpaca Paper Request Inspection Runtime Rehearsal

Date: 2026-06-27

Status: In review

## Summary

This runtime-clone rehearsal verified the broker-free inspector:

```bash
quant semantic-target inspect-alpaca-paper-request
```

The inspector ran against the prepared Alpaca paper request under `/tmp`. It
blocked without broker access because the request was expired and the regular
US equity session was closed.

No credentials were sourced. No Alpaca client was constructed. No Alpaca API
call was made. No order-capable command was run.

## Source And Runtime State

Source workspace:

```text
commit: fb6d7db
status: ## codex/semantic-paper-infra...origin/codex/semantic-paper-infra
```

Runtime clone before fast-forward:

```text
commit: 7c7110f
status:
## main...origin/main [ahead 18]
?? data/semantic-target/
```

Runtime clone after fast-forward:

```text
commit: fb6d7db
status:
## main...origin/main [ahead 20]
?? data/semantic-target/
```

The untracked `data/semantic-target/` directory is existing runtime evidence
and was preserved.

## Runtime Inspection Command

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target inspect-alpaca-paper-request \
  --request-path /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json
```

Result:

```text
exit code: 1

Request: runtime-alpaca-paper-request
Valid now: no
Summary: blocked before Alpaca paper command
Symbol: AAPL
Approved target: 2
Reference price: 20.00
Max quantity: 2.0
Max notional: 1000.0
Valid until: 2026-06-27T04:19:43.447991+00:00
Regular session open: no
Paper output root: /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-paper-output/runtime-alpaca-paper-request
Blocked because: alpaca paper request is expired
Blocked because: regular US equity session is closed
Inspection created no Alpaca or execution artifacts.
```

## Scheduler And Runtime Evidence

Scheduler and launchd evidence:

```text
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
installed_plist_absent=true
```

Runtime operational directory counts after inspection:

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

Future paper output root:

```text
paper_output_absent=true
```

## Verdict

Passed.

The runtime clone can inspect a prepared Alpaca paper request and block before
the order-capable command when local conditions are not safe. The next manual
paper API attempt needs a fresh near-term request during a regular US equity
session.
