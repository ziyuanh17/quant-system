# Supervised Provider Discovery-To-Loop Source Promotion Review

This document records the source-only promotion review for the manually
started discovery-to-loop dry-run command.

In plain language, this review asks whether the current source evidence is
strong enough to design the next stage. It does not copy files to the runtime
clone, load a scheduler, run launchd, connect to a broker, use Alpaca, run
semantic local paper, or submit orders.

## Reviewed Source

- Branch: `main`
- Reviewed commit before this review bundle: `2fb9f13`
- Command under review:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

## Reviewed Evidence

The review accepts these checked-in source artifacts as the current evidence
set:

- [supervised_provider_discovery_loop_operator.md](supervised_provider_discovery_loop_operator.md)
- [supervised_provider_discovery_loop_rehearsal.md](supervised_provider_discovery_loop_rehearsal.md)
- [supervised_provider_discovery_loop_promotion_boundary.md](supervised_provider_discovery_loop_promotion_boundary.md)
- `src/quant/workflows/supervised_provider_discovery_loop_rehearsal.py`
- `tests/test_supervised_provider_discovery_loop_rehearsal.py`

The checked-in rehearsal evidence says the actual command passed completion,
restart reuse, blocked discovery, blocked finite loop, and tampered
prerequisite rejection. It also says the rehearsal found no order, fill,
semantic-paper, or Alpaca directory.

## Review Decision

The source evidence is mature enough to consider the next explicitly scoped
stage: a runtime-clone copy rehearsal design.

This decision does not authorize the runtime-clone rehearsal itself. It only
authorizes designing that rehearsal in a later change set.

## Required Scope For The Next Design

The next design should be limited to:

1. exact source commit to copy;
2. exact runtime-clone destination checks;
3. import/help verification commands only;
4. proof that no workflow request is run;
5. proof that no scheduler, launchd job, Alpaca path, broker path, local
   semantic-paper path, order path, or fill path is touched;
6. rollback steps if the runtime clone does not match the reviewed source.

The design should keep the recurring Alpaca paper scheduler unloaded and must
not use broker credentials.

## Rejected Escalations

This review explicitly rejects skipping ahead to:

- running synthetic workflow inputs from the runtime clone;
- adding any recurring service;
- loading or kickstarting launchd;
- using paper, Alpaca, or broker adapters;
- submitting or rehearsing broker orders;
- automatic drift repair;
- changing runtime-clone state before a separate design is reviewed.

## Stop Conditions

Stop before the next stage if:

- the source worktree is dirty with unrelated changes;
- the reviewed commit changes before the design is written;
- scheduler state is not freshly checked;
- the next stage cannot be explained as no-network and no-workflow;
- any proposed command would create workflow, order, fill, semantic-paper, or
  Alpaca evidence.

## Review Answer

```text
Yes: the manually started discovery-to-loop dry-run command and its
actual-command evidence are mature enough to design a runtime-clone copy
rehearsal.

No: this review does not authorize running that rehearsal, deploying anything,
enabling recurring execution, or touching any broker-connected path.
```
