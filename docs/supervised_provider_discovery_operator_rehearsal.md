# Supervised Provider Discovery Operator Rehearsal

This document describes the actual-command rehearsal for the discovery-only
operator command:

```bash
quant dry-run supervised-provider-discover \
  --request-path reviewed/supervised-provider-discovery-request.json
```

## Scenarios

The rehearsal runs four isolated command scenarios:

- `fresh_completion`: the command completes discovery, writes one operator
  record, and produces a finite manifest without running that manifest.
- `restart_reuse`: running the same command twice reuses the same durable
  operator record.
- `blocked_discovery`: policy-limited discovery blocks, the command exits
  nonzero, and no finite manifest is produced.
- `tampered_rehearsal_block`: changed prerequisite handoff-rehearsal evidence
  is rejected before an operator record is written.

The report binds the executable path and hash, Python source hashes,
prerequisite discovery-handoff rehearsal evidence, command stdout/stderr,
operator records, and every linked JSON artifact. Reopening the report
verifies all hashes again and rescans for prohibited operational directories.

On June 17, 2026, the local actual-command rehearsal passed all four
scenarios. The report bound 124 Python source files, captured five command
observations, verified three operator records, linked 301 scenario evidence
paths, and found no order, fill, semantic-paper, or Alpaca directory.

## Boundary

This rehearsal invokes the actual CLI command, but only against local
synthetic reviewed inputs. It does not run the finite loop, poll for new work,
start launchd, touch the runtime clone, submit orders, or connect to paper,
Alpaca, or any broker.
