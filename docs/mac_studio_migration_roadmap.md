# Mac Studio Migration Roadmap

This roadmap tracks the finite migration from the MacBook Air development and
runtime environment to a Mac Studio that will become the serving machine and
primary development host.

## Completion Definition

The migration is complete only when:

- the Mac Studio has separate development and runtime clones,
- the Mac Studio runtime passes local checks, preflight, a controlled full
  Alpaca paper run, reconciliation, and dashboard health,
- the MacBook Air launchd schedule is unloaded,
- the Mac Studio launchd schedule is loaded,
- exactly one machine owns the recurring schedule,
- the first natural Mac Studio scheduled run succeeds,
- rollback instructions and migration evidence are recorded.

## Safety Invariants

- Never load the recurring Alpaca paper schedule on both Macs.
- Confirm the MacBook Air schedule is unloaded before loading the Studio
  schedule.
- Never commit or place `.env` inside the runtime-state archive.
- Transfer `.env` separately and keep permissions at `600`.
- Keep real-money trading disabled throughout the migration.
- Stop the cutover if reconciliation fails or an unexpected paper order exists.

## Migration Milestones

| Order | Milestone | Status | Completion Evidence |
| --- | --- | --- | --- |
| M1 | Migration Design and Safety Boundary | Done | Finite roadmap, completion definition, single-owner invariant, and rollback boundary documented. |
| M2 | MacBook Air Source and Runtime Audit | Done | Source, runtime clone, launchd state, required environment-key presence, and latest paper health inspected without exposing secrets. |
| M3 | Migration Audit and Export Tooling | Done | Tested scripts safely audit a host and export checksum-backed operational artifacts without `.env`. |
| M4 | MacBook Air Runtime-State Export | Done | Fresh merged archive and SHA-256 checksum created from current runtime artifacts. |
| M5 | Mac Studio Access and Base Setup | In Review | Tailscale and non-interactive SSH access passed; Studio architecture, timezone, disk, and unloaded scheduler were verified. |
| M6 | Mac Studio Development Clone Bootstrap | In Review | GitHub clone, dependencies, Codex authentication, and `make check` passed with 212 tests. |
| M7 | Mac Studio Runtime Clone Bootstrap | In Review | Isolated runtime clone, dependencies, safe `.env`, and localized disabled launchd plist created. |
| M8 | Runtime-State and Secret Transfer | In Review | Merged archive checksum verified, operational artifacts restored, `.env` transferred separately, and permissions verified. |
| M9 | Mac Studio Controlled Rehearsals | In Review | Audit, preflight-only wrapper run, read-only snapshot, and reconciliation passed; controlled order-capable rehearsal remains pending. |
| M10 | Single-Owner Scheduler Cutover | Planned | Unload Air schedule, confirm absent, then load Studio schedule and confirm only Studio owns it. |
| M11 | First Natural Mac Studio Run Review | Planned | Natural launchd run succeeds with healthy dashboard and passed reconciliation. |
| M12 | Migration Closeout | Planned | Record final host ownership, rollback state, artifact locations, and development workflow. |

## Current Gate

The Mac Studio is bootstrapped and read-only broker verification passed. The
next gate is the controlled order-capable rehearsal after the regular market
opens. Refresh broker truth and the current candidate price, then obtain
explicit approval immediately before submission. Keep launchd unloaded until
the resulting evidence is reviewed.

Execution evidence is recorded in
`docs/mac_studio_migration_execution.md`. Durable Codex continuation context is
recorded in `docs/codex_project_handoff.md`.

## MacBook Air Preparation Outcome

Completed on June 7, 2026:

- audited the source workspace and runtime clone,
- confirmed the runtime executable and required `.env` keys are present,
- confirmed `.env` permissions are `600`,
- confirmed the runtime Git remote is
  `git@github.com:ziyuanh17/quant-system.git`,
- recorded the Air's earlier launchd ownership with `runs = 2` and
  `last exit code = 0`,
- created and checksum-verified a secret-free runtime-state archive.

The Air schedule is now unloaded. The Studio schedule is also unloaded, so no
machine currently owns recurring execution.

Evidence and the exact archive path are recorded in
`docs/mac_studio_migration_air_preparation.md`.

## MacBook-Side Tools

Safe host/runtime audit:

```bash
bash scripts/migration/audit_host.sh /Users/ziyuan/Code/quant-system-runtime
```

Runtime-state export:

```bash
bash scripts/migration/export_runtime_state.sh \
  /Users/ziyuan/Code/quant-system-runtime \
  /Users/ziyuan/Code/quant-system-migration
```

The archive includes:

```text
data/live/
data/workflows/alpaca-paper-refresh/
logs/
site/status.json
```

It intentionally excludes `.env`, source code, virtual environments, and
reproducible market-data caches.
