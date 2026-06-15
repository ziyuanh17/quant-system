# Autonomous Dry-Run Local Rehearsal

## Purpose

This document records the June 15, 2026 no-network rehearsal of the bounded
autonomous semantic-target dry-run API.

The rehearsal tests whether routine dry-runs can proceed without per-order
human approval while remaining inside one reviewed deployment authorization.
It does not connect the API to a CLI, scheduler, runtime service, paper
trading, Alpaca, or a broker.

## Rehearsal Location

The actual synthetic rehearsal wrote temporary evidence under:

```text
/tmp/quant-autonomous-dry-run-rehearsal-66wX9F
```

The generated immutable report was reopened through the evidence verifier
after all scenarios completed.

## Observed Scenarios

```text
repeated allowed runs:
  succeeded, succeeded

restart idempotency:
  succeeded, succeeded
  one exact run record and workflow were reused

expired authorization:
  blocked before workflow creation

target above authorization limit:
  blocked before workflow creation

working-order block followed by a later attempt:
  blocked, blocked
  later attempt halted because the prior attempt was blocked
```

The rehearsal report passed every scenario.

## Safety Evidence

The temporary rehearsal evidence contained:

```text
7 distinct autonomous run records
4 distinct dry-run workflow records
0 order files
0 fill files
0 semantic-paper directories
```

No broker client was constructed, no network provider was called, no order was
submitted, no runtime-clone state was changed, and no scheduler was loaded.

## Verdict

The bounded autonomous dry-run API passed its first complete local rehearsal.
It demonstrated repeated routine automation without per-order approval and
halted safely when authorization or execution conditions were not satisfied.
