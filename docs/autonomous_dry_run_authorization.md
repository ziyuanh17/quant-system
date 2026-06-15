# Autonomous Dry-Run Authorization

## Purpose

This design allows routine semantic-target dry-runs to run automatically
without asking a human to approve every intended order.

It does not connect the system to a recurring scheduler, local paper trading,
Alpaca, or any broker. It provides the bounded API that a separately reviewed
scheduler could call later.

## Human And Software Responsibilities

A human approves the operating limits once:

```text
which symbol and contributor-set revision may run
which strategy versions may contribute
which dry-run account identity may be used
whether short targets are permitted
maximum absolute target shares
authorization start and expiry times
maximum number of runs
minimum time between runs
```

Software may then perform routine dry-runs inside those limits. Each run still
checks current target freshness, portfolio aggregation, risk approval, account
state, working orders, and execution-policy compatibility.

This is human-on-the-loop operation: people approve deployment boundaries and
handle exceptions, while software handles routine decisions within those
boundaries.

## Durable Records

`AutonomousDryRunAuthorization` is an immutable deployment authorization.
`AutonomousDryRunRequest` contains the complete inputs for one attempt.
`AutonomousDryRunRecord` records whether that attempt succeeded or was
blocked.

The filesystem layout is:

```text
authorizations/<authorization-id>/<revision>.json
runs/<run-id>.json
workflows/...
locks/<authorization-id>.lock
```

The authorization lock prevents concurrent processes from both claiming the
same remaining run allowance. Reusing a run ID with different inputs fails.

## Fail-Closed Rules

An autonomous attempt is blocked before the dry-run workflow when:

- the authorization is not active at the runner's current time;
- the request references another authorization revision;
- symbol, contributor set, or strategy versions are outside the authorization;
- target or risk limits exceed the authorization;
- the maximum run count or minimum interval is violated; or
- a previous attempt under the same authorization was blocked.

The dry-run workflow can also block because of stale or unavailable targets,
working orders, fractional operational targets, or other existing safety
checks. Such a result becomes a blocked autonomous run and halts later runs
under that authorization.

Recovery requires a new reviewed authorization revision. The runner does not
silently skip a blocked result and continue.

## Finite Manually Started Loop

The only autonomous operator command is:

```bash
quant dry-run autonomous-finite-loop \
  --manifest-path reviewed/finite-loop.json \
  --output-root data/semantic-target/autonomous-dry-run
```

The manifest fixes one authorization, an exact ordered list of request files,
their SHA-256 hashes, and a fixed interval between successful runs. The command
verifies every input before the first run, processes only that finite list,
and stops immediately when one run blocks. Restarting returns the same durable
loop summary after completion.

The command cannot discover requests, add iterations, change trading mode, or
continue indefinitely. It has no paper, Alpaca, broker, scheduler, launchd,
runtime-deployment, or network capability.

The first actual command result is recorded in
[finite_autonomous_dry_run_loop_rehearsal.md](finite_autonomous_dry_run_loop_rehearsal.md).

## Supervised API-Only Service

The supervised autonomous dry-run service can obtain one fresh request per
cycle. A supervisor is a small controller that checks whether automation may
continue. It checks an explicit shutdown signal and persists a health decision
before each dry-run, then stops on any degraded, failed, blocked, or uncertain
condition.

The service is still bounded by a maximum cycle count and maximum runtime. Its
append-only cycle events support restart after the last completed cycle. It
has no CLI, scheduler, launchd, runtime, paper, Alpaca, or broker connection.
See
[supervised_autonomous_dry_run_service.md](supervised_autonomous_dry_run_service.md).

## No-Network Rehearsal

The API-only local rehearsal creates isolated synthetic scenarios for:

```text
two repeated allowed runs under one authorization
restart idempotency for one exact run
expired authorization blocking
target-limit blocking
halt of later runs after a working-order block
```

The rehearsal writes one immutable report and links every authorization,
autonomous run record, and resulting dry-run workflow record. Reopening the
report verifies the linked evidence instead of rerunning the scenarios.

The first complete local result is recorded in
[autonomous_dry_run_rehearsal.md](autonomous_dry_run_rehearsal.md).
