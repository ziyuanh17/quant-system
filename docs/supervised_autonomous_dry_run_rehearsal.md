# Supervised Autonomous Dry-Run Service Rehearsal

## Purpose

This document records the June 15, 2026 no-network rehearsal of the supervised
autonomous dry-run service.

The rehearsal tests whether the API-only supervisor continues when conditions
are healthy, stops when conditions are uncertain, and resumes safely after a
process interruption. It does not connect the service to a CLI, scheduler,
launchd, runtime deployment, paper trading, Alpaca, or a broker.

## Rehearsal Location

The actual synthetic rehearsal wrote temporary evidence under:

```text
/tmp/quant-supervised-dry-run-rehearsal-FR80Q5
```

The generated immutable report was reopened through the evidence verifier
after all scenarios completed.

## Observed Scenarios

```text
healthy continuation:
  two healthy cycles succeeded

degraded health:
  stopped before request generation

failed health:
  stopped before request generation

explicit shutdown:
  stopped before health and request generation

blocked autonomous run:
  working-order block stopped the service after one attempt

request-provider failure:
  failure became a durable error-stop event

maximum runtime:
  stopped before health and request generation

restart continuation:
  resumed after one durable cycle and completed the second cycle
```

The rehearsal report passed every scenario.

## Safety Evidence

The temporary rehearsal evidence contained:

```text
8 scenario service records
10 append-only cycle events
8 persisted health checks
5 autonomous dry-run records
0 order directories
0 fill directories
0 semantic-paper directories
0 Alpaca directories
```

The verifier also detects missing cycle evidence, changed service summaries,
new prohibited operational directories, and rehearsal-ID reuse.

No broker client was constructed, no network provider was called, no order was
submitted, no runtime-clone state was changed, and no scheduler was loaded.

## Verdict

The supervised autonomous dry-run service passed its first complete local
rehearsal. Its next review should define the production health and fresh-request
inputs before considering any CLI, service-manager, or scheduler deployment.
