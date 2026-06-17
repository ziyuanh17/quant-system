# Supervised Provider Discovery Operator

This document describes the manually started discovery-only operator command:

```bash
quant dry-run supervised-provider-discover \
  --request-path reviewed/supervised-provider-discovery-request.json
```

The command consumes one reviewed
`SupervisedProviderDiscoveryOperatorRequest`. The request fixes the discovery
policy, evidence output root, and exact passing discovery-handoff rehearsal
report by path and hash.

## What It Does

The command:

1. preserves the reviewed request under the output root;
2. verifies the discovery-handoff rehearsal report;
3. runs one supervised-provider discovery pass;
4. writes one immutable operator record;
5. exits nonzero when discovery blocks.

When discovery completes, the command may write a finite manifest. It does not
run that manifest. A separate finite supervised-provider command is still
required for any loop execution.

## Boundary

The command has only `--request-path`. It has no output-root, mode, iteration,
scheduler, runtime, paper, Alpaca, broker, or order selector. It does not scan
for new work repeatedly and does not call the finite loop.
