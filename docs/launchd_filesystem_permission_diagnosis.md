# Launchd Filesystem Permission Diagnosis

This note records the diagnosis and fix for the launchd `Operation not
permitted` failure seen when the Alpaca paper wrapper lived under
`~/Documents`.

## Problem

The preflight-only launchd kickstart from the Codex workspace failed before the
wrapper script ran:

```text
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
/bin/bash: /Users/ziyuan/Documents/Codex/2026-05-07/quant-system/scripts/run_alpaca_paper_refresh.sh: Operation not permitted
```

That meant launchd could register the job, but the background process could not
enter or execute the repo path under `Documents`.

## Diagnosis

The likely blocker was macOS privacy protection around `~/Documents` for a
background launchd process. The manual wrapper worked in the interactive
terminal, but the launchd-started process failed before it reached the wrapper.

The chosen fix was not to move the Codex workspace. Instead, a separate
runtime clone was created outside `Documents`:

```text
/Users/ziyuan/Code/quant-system-runtime
```

This keeps the main Codex/Git review workspace stable while giving launchd a
less protected runtime path.

## Runtime Clone Setup

Created the runtime directory and local clone:

```bash
mkdir -p /Users/ziyuan/Code
git clone \
  /Users/ziyuan/Documents/Codex/2026-05-07/quant-system \
  /Users/ziyuan/Code/quant-system-runtime
```

Changed the runtime clone remote to GitHub:

```bash
git remote set-url origin git@github.com:ziyuanh17/quant-system.git
```

Copied local runtime config:

```bash
cp \
  /Users/ziyuan/Documents/Codex/2026-05-07/quant-system/.env \
  /Users/ziyuan/Code/quant-system-runtime/.env
chmod 600 /Users/ziyuan/Code/quant-system-runtime/.env
```

Created a runtime-local launchd plist:

```bash
cp \
  configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example \
  configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist

perl -pi -e \
  's#/absolute/path/to/quant-system#/Users/ziyuan/Code/quant-system-runtime#g' \
  configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Created a fresh runtime virtualenv instead of copying the old one:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[broker-alpaca]"
```

This mattered because the old virtualenv entrypoints had absolute shebangs
back into the `Documents` workspace. The runtime `quant` entrypoint now points
to:

```text
/Users/ziyuan/Code/quant-system-runtime/.venv/bin/python
```

## Verification

Manual preflight from the runtime clone succeeded:

```bash
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true \
  bash scripts/run_alpaca_paper_refresh.sh
```

Then launchd was retried with the installed plist pointing at the runtime
clone and with:

```text
EnvironmentVariables:
  QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true
```

Pre-kickstart launchd state showed:

```text
state = not running
runs = 0
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY => true
```

After one `launchctl kickstart`, launchd showed:

```text
state = not running
runs = 1
last exit code = 0
```

The launchd stdout log showed:

```text
preflight_only=true
preflight completed without broker submission
completed_at=2026-06-04T05:31:07Z
```

No trading artifacts were created in the runtime clone:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/workflows/alpaca-paper-refresh
```

After inspection, the launchd job was unloaded and the temporary installed
plist was removed.

## Operational Model

Use two local directories:

```text
Codex review workspace:
  /Users/ziyuan/Documents/Codex/2026-05-07/quant-system

launchd runtime clone:
  /Users/ziyuan/Code/quant-system-runtime
```

The Codex workspace remains the place for code review, docs, tests, and normal
development. The runtime clone is the path launchd should execute from.

To update the runtime clone after reviewed commits are pushed:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
git pull origin main
```

If dependencies change, refresh the runtime virtualenv:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
.venv/bin/python -m pip install -e ".[broker-alpaca]"
```

Do not commit `.env`, `.venv/`, `logs/`, or
`configs/launchd/*.local.plist`.

## Outcome

Moving the launchd runtime path outside `Documents` fixed the filesystem
execution boundary for preflight-only launchd execution.

The next step should design the first full launchd-triggered wrapper rehearsal,
still on Alpaca paper only, before running any non-preflight `kickstart`.
