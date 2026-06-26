# Activated Local Semantic-Paper Operator Rehearsal

## Purpose

This document records the first local canary rehearsal of:

```bash
quant semantic-paper activated-target
```

The command is limited to durable local semantic paper. It can create local
paper orders and fills under the selected output root, but it cannot contact
Alpaca, load a scheduler, mutate the runtime clone, or submit a broker-network
order.

## Reviewed Synthetic Request

The rehearsal used temporary synthetic files under:

```text
/tmp/quant-semantic-paper-canary-ipaequq3
```

The request modeled a translated legacy momentum canary:

```text
symbol: AAPL
initial local-paper position: 0 shares
approved target: +2 shares
reference price: $100
expected local-paper order: BUY 2 shares
expected notional: $200
```

The request referenced a passing base semantic-target rehearsal, a passing
activation-consumption rehearsal, a time-limited `semantic_paper`
authorization, and exact contributor, strategy target, strategy evaluation,
risk, execution-policy, cash, and initial-position inputs.

## Commands

The request was inspected first:

```bash
quant semantic-paper inspect-activated-target \
  --request-path /tmp/quant-semantic-paper-canary-ipaequq3/inputs/requests/semantic-paper-canary-request.json
```

Inspection exited `0` and wrote no activation or execution artifacts. It
reported:

```text
Valid now: yes
Current position: 0 shares
Approved target: 2 shares
Intended order: BUY 2 shares at reference price $100.00 ($200.00 notional)
Base rehearsal passed: yes
Activation-consumption rehearsal passed: yes
```

The actual command was then run twice with the same request and output roots:

```bash
quant semantic-paper activated-target \
  --request-path /tmp/quant-semantic-paper-canary-ipaequq3/inputs/requests/semantic-paper-canary-request.json \
  --activation-root /tmp/quant-semantic-paper-canary-ipaequq3/activation \
  --output-root /tmp/quant-semantic-paper-canary-ipaequq3/output
```

Both runs exited `0` and reported:

```text
Activation decision: allowed
Workflow status: execution_completed
Execution status: satisfied
```

## Evidence Counts

After both runs, durable output contained exactly:

```text
1 preserved operator request
1 activation evaluation
1 activation consumption
1 orchestration record
1 execution plan
4 lifecycle events
1 local semantic-paper order record
1 local semantic-paper fill record
1 local semantic-paper reconciliation report
1 local semantic-paper state file
4 local semantic-paper snapshots
```

The local semantic-paper state ended at:

```text
AAPL position: +2 shares
average price: $100
orders: 1
fills: 1
```

This proves restart behavior reused the existing activation consumption,
orchestration, execution plan, order, fill, and reconciliation evidence rather
than creating duplicates.

## Safety Evidence

The rehearsal used only synthetic input under `/tmp`. It did not use `.env`,
credentials, Alpaca, launchd, scheduler, runtime-clone state, or broker-network
submission.

The recurring Alpaca paper refresh scheduler was checked after the rehearsal
and reported `service not found`, and the runtime clone remained clean.

## Verdict

The activated local semantic-paper operator command passed its first synthetic
translated-momentum canary rehearsal. It is now suitable for review as the
local paper infrastructure path for future researched strategy targets, while
Alpaca paper and recurring scheduler exposure remain separate later gates.
