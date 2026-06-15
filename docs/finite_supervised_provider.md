# Finite Supervised Provider Dry-Run

## Purpose

`quant dry-run supervised-provider-finite` manually starts one exact ordered
list of independently fresh supervised-provider requests.

It remains finite and broker-free. The command accepts only one reviewed
manifest path and has no output-root, iteration, interval, mode, paper,
Alpaca, broker, scheduler, runtime, or request-discovery selector.

## Reviewed Manifest

`FiniteSupervisedProviderManifest` binds:

```text
loop identity
ordered supervised-provider request paths and SHA-256 hashes
loop evidence output root
creation time
```

Before the first cycle, the runner verifies every request file and every
linked assembly-manifest and assembly-rehearsal hash. It also requires unique
request IDs, assembly manifests, service IDs, and request output roots.

## Execution And Restart

Requests run in manifest order. Each request independently assembles fresh
provider inputs and runs exactly one supervised dry-run cycle.

The loop stops durably on the first rejected or non-completed request. Later
requests are not run. A completed or blocked loop is terminal; restart returns
the same summary after verifying linked operator records.

## June 15, 2026 Rehearsal

The actual command was exercised under:

```text
/tmp/quant-finite-supervised-provider-m4QXCR
```

The exact-list scenario ran twice and both invocations reported:

```text
status: completed
completed: 2/2
```

The stop-on-stale scenario reported:

```text
status: blocked
completed: 1/3
blocked request: stale_target_rejected-blocked-cli
exit code: 1
third request: not run
```

No order, fill, semantic-paper, or Alpaca directory appeared.

## Review Boundary

This stage supports multiple fresh cycles only inside one manually started,
content-bound finite manifest. It does not approve request discovery, launchd,
runtime-clone deployment, recurring scheduling, semantic local paper, Alpaca,
broker access, or order submission.
