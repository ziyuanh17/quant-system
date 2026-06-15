# Supervised Autonomous Dry-Run Service

## Purpose

This API-only service repeatedly runs broker-free semantic-target dry-runs
while conditions remain healthy.

A **supervisor** is a small controller that checks whether an automated process
may continue. Before every cycle, it checks for an explicit shutdown request,
checks health, obtains one fresh request, and calls the existing bounded
autonomous dry-run runner.

This implementation is not connected to the CLI, launchd, a recurring
scheduler, the runtime clone, paper trading, Alpaca, or any broker.

## Bounds

`SupervisedDryRunServicePolicy` fixes:

```text
service and policy identity
exact autonomous authorization revision
maximum cycle count
minimum interval between cycles
maximum total runtime
```

The cycle count cannot exceed the authorization's maximum run count. The
interval cannot be shorter than the authorization's minimum interval.

The service remains bounded even though it can receive a fresh request each
cycle. A later deployment stage would still need separate review before
starting it through a scheduler or long-running service manager.

## Cycle Rules

Each cycle follows this order:

```text
check total runtime
check explicit shutdown signal
obtain and persist health decision
stop unless health is healthy
obtain one fresh request with a new run ID
run the bounded autonomous dry-run
persist one append-only cycle event
stop on any blocked or failed result
sleep before the next cycle
```

Degraded health stops the service. It is not treated as a warning that allows
another run.

## Durable Evidence And Restart

A **cycle event** is an immutable record of what happened during one repeated
check-and-run cycle. Events are append-only:

```text
services/<service-id>/policy.json
services/<service-id>/health-checks/<check-id>.json
services/<service-id>/events/<sequence>.json
services/<service-id>/record.json
autonomous/runs/<run-id>.json
```

The service holds one service-level lock while running. On restart, it validates
the existing contiguous event history and continues at the next cycle. If a
terminal event or final record already exists, it returns the same result
instead of running again.

Provider errors become durable `error_stop` events. A process interruption
between cycles leaves the last completed event available for restart.

## Review Boundary

This stage proves the service contract and local behavior only. It does not
provide request discovery, a production health provider, a CLI command,
launchd configuration, runtime deployment, notification delivery, paper
execution, or broker access.

The first complete no-network rehearsal is recorded in
[supervised_autonomous_dry_run_rehearsal.md](supervised_autonomous_dry_run_rehearsal.md).

The reviewed contracts for production-shaped health snapshots and fresh
request envelopes are documented in
[supervised_provider_contracts.md](supervised_provider_contracts.md).
