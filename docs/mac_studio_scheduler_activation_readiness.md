# Mac Studio Scheduler Activation Readiness

> Historical evidence: this document records the activation-readiness review at
> that time. Its commit, positions, protected-position assumptions, and
> scheduler observations are not current operational truth.

This record reviews whether the Mac Studio Alpaca paper runtime is ready for a
separate recurring launchd activation decision after the successful controlled
order-capable rehearsal. It does not activate the scheduler.

## Review Outcome

As of June 11, 2026, the operational prerequisites are ready for review:

```text
runtime clone=/Users/mochifufu/Code/quant-system-runtime
runtime commit=4853789
origin/main=4853789
runtime quant entrypoint=/Users/mochifufu/Code/quant-system-runtime/.venv/bin/quant
local launchd plist lint=passed
local launchd plist Disabled=true
local launchd working directory=/Users/mochifufu/Code/quant-system-runtime
installed launchd service=unloaded
broker=alpaca-paper
maximum order notional=400
dashboard publishing=true
preflight-only wrapper=passed without broker submission
controlled rehearsal=passed
open orders=0
positions=AAPL:-1,F:+1
post-order reconciliation=passed
post-order reconciliation differences=0
```

The runtime clone has one expected tracked runtime artifact modification:
`site/status.json`. Runtime credentials, environments, logs, and broker
artifacts remain ignored.

## Controlled Rehearsal Evidence

The explicitly approved one-share F paper market buy filled at an average
price of `$14.33`. The protected AAPL short remained exactly `-1`, the new F
position became exactly `+1`, no open orders remained, and post-order
reconciliation passed.

```text
client order ID=codex-rehearsal-F-20260611T1557Z
rehearsal ID=a4b5f7a6-6c45-4742-b93b-80175382133f
reconciliation ID=28476853-37d9-4dc7-bccf-16ccb3fc264f
```

No cleanup order was submitted. The existing `AAPL=-1` and `F=+1` positions
must be treated as protected current broker truth during activation review.

## Remaining Activation Gates

Before loading the scheduler:

1. Review and commit this readiness record and the rehearsal outcome.
2. Promote the reviewed commit to the runtime clone.
3. Re-run no-order preflight and read-only reconciliation.
4. Confirm no open orders and exact positions `AAPL=-1,F=+1`.
5. Obtain separate explicit approval to load the recurring scheduler.
6. Confirm that the first natural scheduled run will be reviewed after the
   weekday 12:55 PM America/Los_Angeles trigger.

Do not run `launchctl kickstart` as part of activation. Do not close either
paper position automatically. If any readiness fact changes, stop and repeat
the review before activation.
