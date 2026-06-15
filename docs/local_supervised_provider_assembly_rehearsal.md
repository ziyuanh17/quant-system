# Local Supervised Provider Assembly Rehearsal

## Purpose

This API-only, no-network rehearsal proves that the local supervised provider
assembly accepts exact reviewed inputs, rejects changed or stale inputs, and
can feed one bounded supervised dry-run cycle without creating operational
artifacts.

It does not expose a CLI command, deploy a service, change the runtime clone,
connect to paper or Alpaca, reach a broker, or submit an order.

## Scenarios

The rehearsal runs seven isolated scenarios:

```text
successful assembly
restart reuses and verifies immutable outputs
changed reviewed input is rejected
changed generated output is detected
stale strategy target is rejected
stale account snapshot is rejected
assembled provider inputs complete one supervised dry-run cycle
```

Rejected scenarios preserve their observed rejection reason and linked input
evidence. They do not pretend an assembly record was created.

## Verification

The immutable report links every relevant input, assembly record, generated
provider input, and supervised-service record. Reopening the report:

- confirms every linked file still exists;
- reloads every legitimate assembly record;
- verifies generated health-snapshot and request-envelope hashes;
- confirms the provider-to-supervisor service record completed; and
- rescans the complete evidence tree for `orders`, `fills`,
  `semantic-paper`, or `alpaca` directories.

The intentionally changed-output scenario is expected to fail assembly restart
verification. Its changed file remains linked as evidence of the detection.

## June 15, 2026 Evidence

One complete local run under
`/tmp/quant-provider-assembly-rehearsal-YpLGgw` produced:

```text
passed scenarios: 7
linked evidence paths: 68
assembly records: 4
completed supervised-service records: 1
prohibited operational directories: 0
total files: 69
```

The report successfully reopened and verified after the run.

## Review Boundary

This rehearsal proves the local assembly and provider-to-supervisor handoff.
It does not approve CLI, launchd, runtime-clone, recurring scheduler, semantic
local-paper, Alpaca, broker, or order-submission exposure. Any such connection
requires a separate design and review.
