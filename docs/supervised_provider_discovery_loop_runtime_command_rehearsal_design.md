# Supervised Provider Discovery-To-Loop Runtime Command Rehearsal Design

This document designs the next runtime-clone rehearsal for the manually
started discovery-to-loop dry-run command.

It is a design only. It does not run the command rehearsal, create synthetic
inputs, source `.env`, use credentials, load launchd, contact Alpaca, connect
to a broker, or submit orders.

In plain language, this rehearsal would answer one narrow question:

```text
Can the runtime clone run the existing no-network actual-command rehearsal
against synthetic reviewed inputs, while keeping all evidence outside the
runtime data tree?
```

## Current Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit before this design bundle: `365f6d4`
- Runtime clone already verified import and CLI help at reviewed source
  `1a31de6`.

The command family under review remains:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

## Scope

The execution stage may only:

1. verify the development workspace is clean;
2. verify the runtime clone is clean and at the reviewed source;
3. verify the recurring Alpaca paper launchd job is not loaded;
4. run the existing no-network rehearsal generator from the runtime clone;
5. write rehearsal evidence under `/tmp`;
6. verify the generated rehearsal report;
7. verify no runtime data, scheduler, paper, Alpaca, broker, order, or fill
   path changed.

The execution stage must not:

- run any hand-authored live request file;
- use any runtime `.env`;
- read broker credentials;
- write under `/Users/mochifufu/Code/quant-system-runtime/data`;
- write under `/Users/mochifufu/Code/quant-system-runtime/logs`;
- load, unload, or kickstart launchd;
- contact Alpaca;
- run semantic local paper;
- submit or rehearse broker orders.

## Planned Command

The rehearsal should run from the runtime clone with bytecode writing disabled:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from datetime import UTC, datetime
from pathlib import Path

from quant.workflows import (
    load_and_verify_supervised_provider_discovery_loop_rehearsal,
    run_supervised_provider_discovery_loop_command_rehearsal,
)

root = Path("/tmp/quant-runtime-discovery-loop-command-rehearsal")
now = datetime.now(UTC)
report = run_supervised_provider_discovery_loop_command_rehearsal(
    rehearsal_id="runtime-discovery-loop-command-rehearsal",
    output_root=root,
    quant_executable_path=Path(".venv/bin/quant"),
    evaluated_at=now,
)
path = root / "reports" / "runtime-discovery-loop-command-rehearsal.json"
verified = load_and_verify_supervised_provider_discovery_loop_rehearsal(path)
print(f"path={path}")
print(f"passed={verified.passed}")
print(f"scenarios={len(verified.scenarios)}")
print(f"source_files={len(verified.source_paths)}")
print(
    "observations="
    f"{sum(len(item.command_observation_paths) for item in verified.scenarios)}"
)
print(
    "composition_records="
    f"{sum(len(item.composition_record_paths) for item in verified.scenarios)}"
)
print(
    "evidence_paths="
    f"{sum(len(item.evidence_paths) for item in verified.scenarios)}"
)
print(f"prohibited={len(verified.prohibited_artifact_paths)}")
PY
```

The command is allowed because the existing rehearsal generator creates local
synthetic reviewed inputs under `/tmp` and invokes the CLI only against those
inputs. It does not require `.env`, credentials, network access, launchd, or a
broker.

## Evidence To Capture

Before running the rehearsal, capture:

- development workspace status and commit;
- runtime clone status and commit;
- runtime clone latest stash entry, so the preserved web-app work remains
  visible;
- scheduler not-loaded evidence;
- installed launchd plist absence;
- runtime operational directory snapshot.

After running the rehearsal, capture:

- report path;
- report pass status;
- scenario count;
- command observation count;
- composition record count;
- linked evidence count;
- prohibited artifact count;
- runtime clone status;
- runtime operational directory snapshot.

Operational directories to compare:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/semantic-target
data/workflows
data/scheduler
data/paper
data/web
logs
```

Existing historical runtime directories may remain present. The pass condition
is that the rehearsal does not create or modify runtime operational evidence.

## Pass Criteria

The rehearsal passes only if:

- the runtime clone starts clean;
- the runtime clone remains clean;
- the scheduler remains unloaded;
- the installed launchd plist remains absent;
- the generated report verifies successfully;
- all required scenarios pass;
- `prohibited_artifact_paths` is empty in the report;
- the report evidence root is under `/tmp`;
- no runtime `data` or `logs` path is created or modified by the rehearsal;
- no `.env` file is sourced;
- no broker credentials are read.

## Fail-Closed Conditions

Stop immediately if:

- the runtime clone is dirty before the rehearsal;
- the runtime clone is not at the reviewed source;
- launchd reports the Alpaca paper job is loaded;
- the installed Alpaca paper plist exists;
- the command needs `.env`, credentials, or network access;
- the report does not verify;
- the report contains any prohibited artifact path;
- runtime operational directories change unexpectedly;
- the runtime clone becomes dirty.

## Explicit Non-Authorization

Approving this design would not authorize executing the rehearsal. A later
stage must separately approve the runtime-clone no-network command rehearsal
execution.

Even if that execution passes, it would not authorize running real reviewed
operator requests, loading launchd, recurring scheduling, semantic local
paper, Alpaca semantic targets, broker access, orders, or fills.
