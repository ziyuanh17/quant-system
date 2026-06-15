# Supervised Provider Operator Command Rehearsal

## Purpose

This no-network rehearsal exercises the actual:

```bash
quant dry-run supervised-provider
```

command. It proves the manually started boundary completes fresh reviewed
work, safely reuses durable results after restart, and rejects stale or
changed reviewed inputs.

## Evidence Design

Every command invocation creates an immutable observation containing:

```text
exact quant executable path and SHA-256 hash
exact SHA-256 hashes for every Python file under src/quant
exact command arguments
exit code
stdout and stderr
observation time
```

The final report also binds the exact passing provider-assembly rehearsal,
legitimate operator records, all linked scenario evidence, and a scan for
prohibited operational directories.

## Scenarios

The rehearsal runs four isolated scenarios:

```text
fresh completion
restart reuse
stale target input blocked
changed manifest input blocked
```

Fresh completion and restart must exit successfully. Stale and changed inputs
must exit nonzero without creating a durable operator result or supervised
execution output.

## June 15, 2026 Evidence

One complete local run under:

```text
/tmp/quant-supervised-provider-command-rehearsal-jbNCbR
```

produced:

```text
passed scenarios: 4
actual command observations: 5
legitimate operator records: 2
linked scenario evidence paths: 46
bound Python source files: 118
prohibited operational directories: 0
total files: 123
```

The completed report reopened and verified successfully.

## Review Boundary

This rehearsal proves only the manually started, one-cycle, local dry-run
command. It does not approve launchd, runtime-clone deployment, recurring
scheduling, semantic local paper, Alpaca, broker access, or order submission.
