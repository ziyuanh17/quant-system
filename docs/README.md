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
- [semantic_paper_runtime_copy_rehearsal.md](semantic_paper_runtime_copy_rehearsal.md):
  evidence for the semantic-paper runtime-clone import/help-only rehearsal.
- [semantic_paper_runtime_command_rehearsal_design.md](semantic_paper_runtime_command_rehearsal_design.md):
  design for a semantic-paper runtime-clone no-network actual-command
  rehearsal with synthetic reviewed inputs.
- [semantic_paper_runtime_command_rehearsal.md](semantic_paper_runtime_command_rehearsal.md):
  evidence for the semantic-paper runtime-clone no-network actual-command
  rehearsal.
- [semantic_paper_manual_operator_runbook_design.md](semantic_paper_manual_operator_runbook_design.md):
  design for a one-request manual runtime semantic-paper local-data runbook.
- [semantic_paper_manual_operator_run.md](semantic_paper_manual_operator_run.md):
  evidence for one manual runtime semantic-paper local-data run.
- [semantic_target_alpaca_paper_testing_boundary.md](semantic_target_alpaca_paper_testing_boundary.md):
  design boundary for one-request semantic-target Alpaca paper testing.
- [semantic_target_alpaca_paper_fake_rehearsal.md](semantic_target_alpaca_paper_fake_rehearsal.md):
  evidence for the source-level semantic-target Alpaca paper fake-client
  rehearsal.
- [semantic_target_alpaca_paper_manual_runbook_design.md](semantic_target_alpaca_paper_manual_runbook_design.md):
  design for a one-request manual runtime semantic-target Alpaca paper test.
- [semantic_target_alpaca_paper_fake_cli.md](semantic_target_alpaca_paper_fake_cli.md):
  evidence for the fake-client CLI boundary for semantic-target Alpaca paper.
- [semantic_target_alpaca_paper_cli_design.md](semantic_target_alpaca_paper_cli_design.md):
  design for the future one-request real Alpaca paper CLI command.
- [semantic_target_alpaca_paper_cli.md](semantic_target_alpaca_paper_cli.md):
  source evidence for the one-request semantic-target Alpaca paper CLI command
  verified with an injected fake paper client.
- [semantic_target_alpaca_paper_runtime_rehearsal_design.md](semantic_target_alpaca_paper_runtime_rehearsal_design.md):
  design for a no-network runtime-clone import/help/preflight rehearsal before
  a real Alpaca paper order test.
- [semantic_target_alpaca_paper_runtime_rehearsal.md](semantic_target_alpaca_paper_runtime_rehearsal.md):
  evidence for the no-network runtime-clone import/help/preflight rehearsal.
- [semantic_target_alpaca_paper_request_preparation_design.md](semantic_target_alpaca_paper_request_preparation_design.md):
  design for preparing one reviewed Alpaca paper request from existing
  semantic-target artifacts without broker access.
- [semantic_target_alpaca_paper_request_preparation.md](semantic_target_alpaca_paper_request_preparation.md):
  source evidence for the broker-free Alpaca paper request preparer.
- [semantic_target_alpaca_paper_request_runtime_rehearsal.md](semantic_target_alpaca_paper_request_runtime_rehearsal.md):
  runtime evidence for broker-free Alpaca paper request preparation using
  synthetic local inputs under `/tmp`.
- [semantic_target_alpaca_paper_manual_test_design.md](semantic_target_alpaca_paper_manual_test_design.md):
  design for the first one-request manual Alpaca paper API test.
- [semantic_target_alpaca_paper_manual_test_preflight.md](semantic_target_alpaca_paper_manual_test_preflight.md):
  blocked preflight evidence for the first manual Alpaca paper API test.
- [semantic_target_alpaca_paper_market_session_guard.md](semantic_target_alpaca_paper_market_session_guard.md):
  source evidence for the closed-session guard on the order-capable Alpaca
  paper command.
- [semantic_target_alpaca_paper_market_session_guard_runtime_rehearsal.md](semantic_target_alpaca_paper_market_session_guard_runtime_rehearsal.md):
  runtime evidence that the closed-session guard blocks before broker
  interaction.
- [semantic_target_alpaca_paper_request_inspection.md](semantic_target_alpaca_paper_request_inspection.md):
  source evidence for broker-free inspection of prepared Alpaca paper requests.
- [semantic_target_alpaca_paper_request_inspection_runtime_rehearsal.md](semantic_target_alpaca_paper_request_inspection_runtime_rehearsal.md):
  runtime evidence for broker-free inspection of a prepared Alpaca paper
  request.
- [semantic_target_alpaca_paper_evidence_verifier_design.md](semantic_target_alpaca_paper_evidence_verifier_design.md):
  design for a broker-free verifier of one-request Alpaca paper run evidence.
- [semantic_target_alpaca_paper_evidence_verifier.md](semantic_target_alpaca_paper_evidence_verifier.md):
  source evidence for broker-free verification of completed Alpaca paper run
  artifacts.
- [semantic_target_alpaca_paper_evidence_verifier_rehearsal.md](semantic_target_alpaca_paper_evidence_verifier_rehearsal.md):
  local fake-client rehearsal evidence for the Alpaca paper run verifier.
- [semantic_target_alpaca_paper_readiness_preflight.md](semantic_target_alpaca_paper_readiness_preflight.md):
  source and rehearsal evidence for broker-free readiness reports and freshness
  checks before one reviewed Alpaca paper test.
- [semantic_target_alpaca_paper_readiness_freshness.md](semantic_target_alpaca_paper_readiness_freshness.md):
  evidence for the freshness gate applied when consuming Alpaca paper readiness
  reports before broker construction.
- [semantic_target_fresh_market_session_alpaca_paper_test.md](semantic_target_fresh_market_session_alpaca_paper_test.md):
  current runbook for the next one-request semantic-target Alpaca paper test
  during a regular market session.
- [semantic_target_fresh_market_session_alpaca_paper_execution.md](semantic_target_fresh_market_session_alpaca_paper_execution.md):
  market-session Alpaca paper execution evidence showing a fail-closed
  ambiguous cross-zero reversal and the resulting guard.
- [semantic_target_reversal_lifecycle_design.md](semantic_target_reversal_lifecycle_design.md):
  design for explicit close/open lifecycle semantics for target transitions
  that cross zero.
- [semantic_target_durable_transition_plan.md](semantic_target_durable_transition_plan.md):
  implemented broker-free durable transition plan artifacts for semantic target
  transitions, including cross-zero close/open legs.
- [semantic_target_transition_leg_events.md](semantic_target_transition_leg_events.md):
  implemented append-only per-leg lifecycle events for durable transition
  plans, still broker-free.
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
