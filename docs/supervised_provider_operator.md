# Supervised Provider Dry-Run Operator

## Purpose

`quant dry-run supervised-provider` is a manually started, broker-free command
that assembles one exact set of reviewed local inputs and runs one supervised
dry-run cycle.

The command accepts only one reviewed request path. It has no mode, output
root, cycle-count, interval, paper, Alpaca, broker, scheduler, or runtime
selector.

## Reviewed Request

`SupervisedProviderOperatorRequest` binds:

```text
request identity
exact provider-assembly manifest path and SHA-256 hash
exact passing provider-assembly rehearsal report path and SHA-256 hash
single-cycle supervised-service policy
evidence output root
```

Before assembly, the operator verifies the passing rehearsal, both input
hashes, service identity, authorization identity, cycle index, and the
single-cycle zero-interval boundary.

## Durable Result

One successful command writes an immutable operator result that records the
request hash, assembly identity, service identity and status, and exact hashes
of the assembly and service records. Restart returns the existing result only
after verifying those linked records remain unchanged.

The underlying supervised dry-run may persist target, risk, execution-plan,
and `would_submit` dry-run evidence. It cannot submit an order.

## June 15, 2026 Rehearsal

The actual command ran twice against one fresh reviewed synthetic request at:

```text
/tmp/quant-supervised-provider-operator-yjrrCi
```

Both invocations returned the same completed assembly and supervised-service
result. The evidence tree contained 20 files and no `orders`, `fills`,
`semantic-paper`, or `alpaca` directory.

## Review Boundary

This command is finite, manually started, local, and dry-run-only. It does not
approve launchd, runtime-clone deployment, recurring scheduling, semantic
local paper, Alpaca, broker access, or order submission.
