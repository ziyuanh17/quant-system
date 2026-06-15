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

## Current Boundary

The runner is API-only. There is no CLI, scheduler, launchd service, runtime
deployment, paper-trading path, Alpaca path, network call, or broker-order
capability in this stage.
