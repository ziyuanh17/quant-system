# Mac Studio Migration: MacBook Air Preparation

This note records the migration work completed automatically on the MacBook
Air before the Mac Studio is reachable.

## Date and Source State

- Preparation date: June 7, 2026
- Current Air hostname: `zystation.local`
- Architecture: `arm64`
- macOS version: `26.3.1`
- Source workspace:
  `/Users/ziyuan/Documents/Codex/2026-05-07/quant-system`
- Runtime clone: `/Users/ziyuan/Code/quant-system-runtime`
- Runtime Git remote: `git@github.com:ziyuanh17/quant-system.git`

## Runtime Audit

The safe audit confirmed:

```text
runtime_root_present=true
git_present=true
quant_present=true
env_present=true
QUANT_ALPACA_PAPER_API_KEY=present
QUANT_ALPACA_PAPER_SECRET_KEY=present
QUANT_BROKER=present
QUANT_MAX_ORDER_NOTIONAL=present
QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN=present
```

No secret values were printed or written into this document.

The runtime `.env` permissions are:

```text
-rw-------
```

## Current Scheduler Ownership

The MacBook Air remains the only known recurring scheduler owner:

```text
label=com.quant-system.alpaca-paper-refresh
runtime=/Users/ziyuan/Code/quant-system-runtime
runs=2
last_exit_code=0
schedule=weekdays at 12:55 local time
```

The schedule intentionally remains loaded until the Mac Studio has passed its
controlled rehearsals and is ready for the single-owner cutover.

## Runtime-State Export

Created:

```text
/Users/ziyuan/Code/quant-system-migration/quant-runtime-state-20260607T233346Z.tar.gz
/Users/ziyuan/Code/quant-system-migration/quant-runtime-state-20260607T233346Z.tar.gz.sha256
```

Checksum verification result:

```text
quant-runtime-state-20260607T233346Z.tar.gz: OK
```

The archive contains:

```text
data/live/
data/workflows/alpaca-paper-refresh/
logs/
site/status.json
```

The archive excludes:

```text
.env
.venv/
source code
raw/normalized/feature market-data caches
machine-specific launchd plists
```

## Remaining External Blocker

To continue automatically from the Air onto the Studio, provide:

```text
Mac Studio hostname or IP address
Mac Studio macOS username
confirmation that Remote Login (SSH) is enabled
```

Once SSH connectivity is available, Codex can perform the Studio bootstrap,
transfer the secret-free archive, guide or perform the separate `.env`
transfer, run controlled rehearsals, and execute the final single-owner
scheduler cutover.

