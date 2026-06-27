# Documentation Map

Start with these current, canonical documents:

- [current_system_status.md](current_system_status.md): checked-in capabilities,
  activation boundary, and recommended next work.
- [architecture.md](architecture.md): system-wide component boundaries.
- [semantic_target_architecture.md](semantic_target_architecture.md): semantic
  target contracts and execution lifecycle.
- [supervised_provider_discovery_loop_promotion_boundary.md](supervised_provider_discovery_loop_promotion_boundary.md):
  source-only review boundary before any stronger operational use of the
  composed discovery-to-loop dry-run command.
- [supervised_provider_discovery_loop_source_promotion_review.md](supervised_provider_discovery_loop_source_promotion_review.md):
  source-only decision record for whether the next stage may design a
  runtime-clone copy rehearsal.
- [supervised_provider_discovery_loop_runtime_copy_rehearsal_design.md](supervised_provider_discovery_loop_runtime_copy_rehearsal_design.md):
  design for a no-workflow runtime-clone copy/import/help rehearsal.
- [supervised_provider_discovery_loop_runtime_copy_rehearsal.md](supervised_provider_discovery_loop_runtime_copy_rehearsal.md):
  runtime-clone copy/import/help rehearsal evidence.
- [semantic_paper_runtime_copy_rehearsal_design.md](semantic_paper_runtime_copy_rehearsal_design.md):
  design for a semantic-paper runtime-clone import/help-only rehearsal.
- [supervised_provider_discovery_loop_runtime_command_rehearsal_design.md](supervised_provider_discovery_loop_runtime_command_rehearsal_design.md):
  design for a no-network runtime-clone actual-command rehearsal with
  synthetic reviewed inputs.
- [supervised_provider_discovery_loop_runtime_command_rehearsal.md](supervised_provider_discovery_loop_runtime_command_rehearsal.md):
  runtime-clone no-network actual-command rehearsal evidence.
- [supervised_provider_discovery_loop_manual_operator_runbook_design.md](supervised_provider_discovery_loop_manual_operator_runbook_design.md):
  design for a future one-request manual dry-run operator runbook.
- [supervised_provider_discovery_loop_manual_operator_run.md](supervised_provider_discovery_loop_manual_operator_run.md):
  evidence for one synthetic manual discovery-to-loop dry-run from the runtime
  clone.
- [supervised_provider_discovery_loop_manual_synthetic_readiness_review.md](supervised_provider_discovery_loop_manual_synthetic_readiness_review.md):
  decision to stop at manual synthetic dry-run readiness unless a separate
  non-synthetic request design is proposed.
- [strategy_research_restart_plan.md](strategy_research_restart_plan.md):
  research-only plan for restarting candidate strategy evaluation after the
  operator-promotion sequence, including the implemented research-batch
  contract.
- [runbook.md](runbook.md): supported operator commands.
- [trading_safety.md](trading_safety.md): safety gates.
- [codex_project_handoff.md](codex_project_handoff.md): collaboration and host
  rules.
- [roadmap.md](roadmap.md): historical milestone ledger and current
  recommendation.

## Document Classes

Design and architecture documents explain intended boundaries. Some older
design files preserve the constraints that applied before their implementation;
their “future” and “non-goal” language describes that milestone, not necessarily
the current repository.

Runbooks describe commands that exist, but a command being documented does not
authorize running it. Broker-connected or order-capable operations still
require the applicable safety gates and explicit approval.

Incident, rehearsal, migration, launchd, smoke-execution, and activation
documents are historical evidence. Preserve their dated observations and
commands. They do not establish current broker positions, runtime-clone
version, scheduler state, or authorization.

## Truth Hierarchy

When documents disagree:

1. fresh broker/runtime observations govern operational truth;
2. checked-in code and tests govern implemented source behavior;
3. [current_system_status.md](current_system_status.md) governs the summarized
   current capability boundary;
4. historical evidence governs only the event it records;
5. roadmap and design intentions do not override implemented behavior.
