# Documentation Map

Start with these current, canonical documents:

- [current_system_status.md](current_system_status.md): checked-in capabilities,
  activation boundary, and recommended next work.
- [architecture.md](architecture.md): system-wide component boundaries.
- [semantic_target_architecture.md](semantic_target_architecture.md): semantic
  target contracts and execution lifecycle.
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
