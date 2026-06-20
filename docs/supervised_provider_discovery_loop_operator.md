# Supervised Provider Discovery-To-Loop Operator

This document describes the manually started discovery-to-finite-loop command:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

The command consumes one reviewed
`SupervisedProviderDiscoveryLoopOperatorRequest`. The request fixes:

- the exact discovery-only operator request path and hash;
- the exact passing discovery-operator command rehearsal report path and hash;
- the composition output root.

## What It Does

The command:

1. preserves the reviewed composition request;
2. verifies the discovery-only operator command rehearsal;
3. runs one reviewed discovery-only operator request;
4. if discovery blocks, writes a blocked composition record and stops before
   the finite loop;
5. if discovery completes, runs only the exact finite manifest produced by
   discovery;
6. writes one immutable composition record.

The command exits nonzero if discovery blocks or if the finite loop blocks.

## Boundary

The command has only `--request-path`. It has no output-root, mode, iteration,
scheduler, runtime, paper, Alpaca, broker, or order selector. It does not poll
for new work, discover additional requests after the reviewed discovery pass,
or submit broker orders.
