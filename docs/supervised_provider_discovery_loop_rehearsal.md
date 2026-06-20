# Supervised Provider Discovery-To-Loop Command Rehearsal

This document describes the actual-command rehearsal for the composed
discovery-to-finite-loop command:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

The rehearsal uses local synthetic reviewed inputs only. It proves the command
line path behaves like the API design, without creating any paper, Alpaca,
broker, order, fill, scheduler, launchd, runtime-clone, or recurring-service
path.

## Scenarios

The rehearsal runs five isolated command scenarios:

- `exact_completion`: discovery completes, produces one finite manifest, and
  the command runs exactly that manifest to completion.
- `restart_reuse`: running the same command twice reuses one durable
  composition record instead of creating duplicate workflow evidence.
- `discovery_block`: discovery blocks before a finite manifest can be run, and
  the command exits nonzero without finite-loop output.
- `loop_block`: discovery succeeds, the finite loop reaches a blocked request,
  and the command exits nonzero with durable blocked composition evidence.
- `tampered_rehearsal_block`: changed prerequisite discovery-operator
  rehearsal evidence is rejected before a composition record is written.

The report binds the executable path and hash, Python source hashes, the exact
prerequisite discovery-operator command rehearsal, command stdout/stderr,
composition records, and every linked JSON artifact. Reopening the report
verifies all hashes again and rescans for prohibited operational directories.

On June 19, 2026 local time, the local actual-command rehearsal passed all
five scenarios. The report bound 126 Python source files, captured six command
observations, verified four composition records, linked 1,519 scenario
evidence paths, and found no order, fill, semantic-paper, or Alpaca directory.

## Boundary

This rehearsal invokes the actual CLI command, but only against local
synthetic reviewed inputs. It does not poll for new work after the reviewed
discovery pass, start launchd, touch the runtime clone, submit orders, or
connect to paper, Alpaca, or any broker.

The synthetic inputs are freshness-sensitive. Rehearsal generation should use
the current time so that provider request envelopes, health snapshots, and
supervised-service policies are valid when the actual command runs.
