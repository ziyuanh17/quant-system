# Semantic-Target Alpaca Paper Market Session Guard Runtime Rehearsal

Date: 2026-06-27

Status: In review

## Summary

This runtime-clone rehearsal verified that the order-capable Alpaca paper
command blocks before broker interaction when the regular US equity session is
closed.

No Alpaca API call was made. No credentials were sourced. No broker client was
constructed. No paper output root was created.

## Source And Runtime State

Source workspace:

```text
commit: 7c7110f
status: ## codex/semantic-paper-infra...origin/codex/semantic-paper-infra
```

Runtime clone before fast-forward:

```text
commit: ddc6d9e
status:
## main...origin/main [ahead 14]
?? data/semantic-target/
```

Runtime clone after fast-forward:

```text
commit: 7c7110f
status:
## main...origin/main [ahead 18]
?? data/semantic-target/
```

The untracked `data/semantic-target/` directory is existing runtime evidence
and was preserved.

## Clock Evidence

```text
utc=2026-06-27T21:30:37Z
local=2026-06-27T14:30:37-0700
```

This was Saturday, outside the regular US equity session.

## Guard Command

Runtime command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper \
  --request-path /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json \
  --from-env
```

Result:

```text
exit code: 2

Invalid value: regular US equity session is closed; refusing to submit or
queue an Alpaca paper market order
```

The command blocked before loading paper credentials or constructing the
broker client.

## Scheduler And Runtime Evidence

Scheduler and launchd evidence:

```text
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
installed_plist_absent=true
```

Runtime operational directory counts after the guard check:

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

The runtime command enforces the closed-session guard before broker
interaction. The next manual paper API attempt should be prepared with a fresh
near-term request and run during a regular US equity session.
