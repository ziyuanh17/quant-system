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
- Keep the MacBook Air schedule active until the Studio is ready for cutover.
- Never commit or place `.env` inside the runtime-state archive.
- Transfer `.env` separately and keep permissions at `600`.
- Keep real-money trading disabled throughout the migration.
- Stop the cutover if reconciliation fails or an unexpected paper order exists.

## Migration Milestones

| Order | Milestone | Status | Completion Evidence |
| --- | --- | --- | --- |
| M1 | Migration Design and Safety Boundary | In Review | Finite roadmap, completion definition, single-owner invariant, and rollback boundary documented. |
| M2 | MacBook Air Source and Runtime Audit | In Review | Source, runtime clone, launchd state, required environment-key presence, and latest paper health inspected without exposing secrets. |
| M3 | Migration Audit and Export Tooling | In Review | Tested scripts safely audit a host and export checksum-backed operational artifacts without `.env`. |
| M4 | MacBook Air Runtime-State Export | In Review | Timestamped archive and SHA-256 checksum created from current runtime artifacts. |
| M5 | Mac Studio Access and Base Setup | Blocked | Requires Mac Studio hostname/IP, username, SSH access, and permission to operate remotely. |
| M6 | Mac Studio Development Clone Bootstrap | Planned | Clone repo, install dependencies, authenticate Codex/GitHub, and pass `make check`. |
| M7 | Mac Studio Runtime Clone Bootstrap | Planned | Create isolated runtime clone, environment, localized disabled launchd plist, and safe `.env`. |
| M8 | Runtime-State and Secret Transfer | Planned | Verify archive checksum, restore operational artifacts, transfer `.env` separately, and verify permissions. |
| M9 | Mac Studio Controlled Rehearsals | Planned | Pass audit, preflight-only wrapper run, controlled full wrapper run, reconciliation, and healthy dashboard. |
| M10 | Single-Owner Scheduler Cutover | Planned | Unload Air schedule, confirm absent, then load Studio schedule and confirm only Studio owns it. |
| M11 | First Natural Mac Studio Run Review | Planned | Natural launchd run succeeds with healthy dashboard and passed reconciliation. |
| M12 | Migration Closeout | Planned | Record final host ownership, rollback state, artifact locations, and development workflow. |

## Current Blocker

Automatic work on the Mac Studio requires:

```text
Mac Studio hostname or IP address
Mac Studio macOS username
Remote Login (SSH) enabled on the Mac Studio
network reachability from the MacBook Air
permission to connect and execute setup commands
```

The MacBook Air recurring schedule was unloaded on June 9, 2026 after the
first actionable scheduled Alpaca paper order exposed short-selling and
reconciliation timing gaps. The actionable-order safety remediation is now in
the reviewed source history. The MacBook Air runtime clone has been synced and
passed a preflight-only rehearsal, but the Mac Studio runtime cutover remains
paused. Read-only broker readiness passed with zero reconciliation differences;
the dedicated controlled order-capable rehearsal command is now in review, and
its execution still requires explicit approval immediately before submission.

SSH reaches the Mac Studio over Tailscale, but the MacBook Air public key is
not yet authorized for user `mochifufu`.

## MacBook Air Preparation Outcome

Completed on June 7, 2026:

- audited the source workspace and runtime clone,
- confirmed the runtime executable and required `.env` keys are present,
- confirmed `.env` permissions are `600`,
- confirmed the runtime Git remote is
  `git@github.com:ziyuanh17/quant-system.git`,
- confirmed the Air is the current launchd owner with `runs = 2` and
  `last exit code = 0`,
- created and checksum-verified a secret-free runtime-state archive.

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
