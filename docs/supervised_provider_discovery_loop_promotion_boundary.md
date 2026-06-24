# Supervised Provider Discovery-To-Loop Promotion Boundary

This document defines the review boundary before the manually started
discovery-to-loop dry-run command can be considered for any stronger
operational use.

In plain language, **promotion** means moving a capability from one level of
use to a more operational level. Here the current level is: a human manually
starts one dry-run command with one reviewed request file. Promotion could mean
allowing a prepared operator runbook, a runtime-clone rehearsal, or eventually
a recurring service. This document does not perform that promotion.

The **boundary** is the line the system must not cross without a separate
review. It is a set of required evidence, explicit non-goals, and stop
conditions.

## Current Approved Capability

The current checked-in command is:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

It consumes one reviewed composition request, verifies the discovery-only
command rehearsal, runs one reviewed discovery-only request, and then runs
only the exact finite manifest produced by discovery.

The command is still manual and dry-run only. It has no scheduler, launchd,
runtime-clone, paper, Alpaca, broker, mode, output-root, or order selector.

## Promotion Does Not Mean Approval To Trade

This boundary does not authorize:

- broker orders;
- Alpaca semantic-target paper execution;
- local semantic-paper execution;
- recurring scheduling;
- launchd loading or kickstarting;
- runtime-clone mutation;
- automatic repair of drift;
- bypassing fresh broker, scheduler, or reconciliation checks.

Any future order-capable stage still requires its own design, rehearsal, fresh
read-only broker checks, and explicit approval immediately before an
order-capable command.

## Evidence Required Before Any Promotion Proposal

A promotion proposal must name exact evidence, not just a general confidence
claim:

1. checked-in source commit;
2. clean development worktree before the proposal;
3. passing actual-command discovery-to-loop rehearsal report;
4. source hashes and executable hash bound by that report;
5. proof of completion, restart reuse, blocked discovery, blocked finite loop,
   and tampered prerequisite rejection;
6. proof that no order, fill, semantic-paper, or Alpaca directories appeared;
7. full non-web test result;
8. direct check that recurring Alpaca paper launchd is not loaded;
9. explicit statement of the next operational level being requested.

The proposal must also say what is still excluded. For example, a runtime-clone
copy rehearsal would still exclude launchd loading and broker access unless
those are named in a later reviewed stage.

## Stop Conditions

Do not promote if any of these are true:

- source or executable hashes no longer match the reviewed rehearsal evidence;
- the development worktree contains unrelated unreviewed changes;
- the recurring Alpaca paper scheduler is loaded unexpectedly;
- the proposal depends on historical broker position data instead of fresh
  read-only observations;
- any rehearsal creates order, fill, semantic-paper, or Alpaca artifacts;
- any blocked scenario exits successfully;
- restart creates duplicate composition or loop records;
- the next stage is described vaguely, such as "turn it on" or "make it live",
  without exact scope and rollback rules.

## Recommended Next Operational Levels

Use separate reviews in this order:

1. source-only promotion review: confirm the checked-in command and rehearsal
   evidence are accepted;
2. runtime-clone copy rehearsal: copy reviewed source to the runtime clone and
   verify the command help/import path only, without running workflows;
3. runtime-clone no-network command rehearsal: run synthetic reviewed inputs
   from the runtime clone, with no scheduler and no broker credentials used;
4. finite manual operator runbook: document exactly how a human would prepare,
   inspect, run, and archive one dry-run request;
5. deployment design: only after the manual runtime rehearsal is reviewed,
   design whether any recurring service should exist at all.

Each level must be completed and reviewed before the next level starts.

## Review Question

The review should answer one narrow question:

```text
Is the manually started discovery-to-loop dry-run command, plus its
actual-command evidence, mature enough to consider the next explicitly scoped
promotion stage?
```

A "yes" answer does not authorize the next stage automatically. It only allows
that next stage to be designed or rehearsed separately.
