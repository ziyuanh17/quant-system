# Finite Supervised Provider Command Rehearsal

## Purpose

This no-network rehearsal exercises the actual:

```bash
quant dry-run supervised-provider-finite
```

command. It proves exact-list completion, restart reuse, preflight rejection,
and stop-on-block behavior without adding request discovery or recurring
execution.

## Evidence Design

Every command invocation writes an immutable observation with:

```text
exact quant executable path and SHA-256 hash
exact SHA-256 hashes for every Python file under src/quant
exact command arguments
exit code
stdout and stderr
observation time
```

The final report binds the exact passing provider-assembly rehearsal, every
legitimate loop record, all linked scenario evidence, and a scan for
prohibited operational directories.

## Scenarios

The rehearsal runs four isolated scenarios:

```text
exact-list completion
restart reuse
preflight rejection before any request runs
stop on stale second request
```

Exact-list completion and restart must exit successfully. Preflight rejection
must exit nonzero without creating a loop record or request outputs.
Stop-on-block must create one durable blocked loop record, complete only the
first request, and leave the later request untouched.

## June 15, 2026 Evidence

One complete local run under:

```text
/tmp/quant-finite-supervised-provider-command-rehearsal-shxRb7
```

produced:

```text
passed scenarios: 4
actual command observations: 5
legitimate loop records: 3
linked scenario evidence paths: 119
bound Python source files: 120
prohibited operational directories: 0
total files: 197
```

The completed report reopened and verified successfully.

## Review Boundary

This rehearsal proves only the manually started finite dry-run command. It
does not approve request discovery, launchd, runtime-clone deployment,
recurring scheduling, semantic local paper, Alpaca, broker access, or order
submission.
