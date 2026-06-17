# Supervised Provider Discovery Rehearsal

This document describes the no-network rehearsal for API-only
supervised-provider request discovery.

The rehearsal proves that discovery can safely hand reviewed request files to
the finite supervised-provider loop without adding a CLI, scheduler, runtime,
paper, Alpaca, broker, or order path.

## Scenarios

The rehearsal covers six deterministic scenarios:

- `discovery_to_loop`: discovery writes one finite manifest and the finite
  loop consumes it to complete two reviewed one-cycle requests.
- `restart_reuse`: rerunning discovery returns the same durable result and
  manifest before the finite loop runs.
- `empty_directory_block`: discovery blocks when the reviewed request
  directory is absent.
- `over_limit_block`: discovery blocks when the reviewed directory contains
  more requests than the policy allows.
- `changed_input_block`: discovery blocks when a request's linked assembly
  evidence changed after review.
- `stop_on_block_handoff`: discovery writes a manifest for three requests, the
  finite loop completes one request, blocks on a stale second request, and
  does not touch the remaining request.

The report records source hashes, prerequisite assembly-rehearsal evidence,
discovery results, generated finite manifests, finite loop records, and all
linked JSON evidence. Reopening the report verifies every hash again and
rescans for prohibited operational directories.

On June 16, 2026, the local rehearsal passed all six scenarios. The report
bound 122 Python source files, linked 122 scenario evidence paths, verified six
discovery results, three finite manifests, three finite loop records, and found
no order, fill, semantic-paper, or Alpaca directory.

## Boundary

This rehearsal is API-only. It does not run `quant`, create an operator-facing
entry point, poll for new work, start launchd, touch the runtime clone, submit
orders, or connect to paper, Alpaca, or any broker.
