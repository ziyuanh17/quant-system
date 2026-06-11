# Mac Studio Migration Execution

This note records the Mac Studio migration work performed on June 10, 2026.
No order-capable command was executed and no recurring schedule was loaded.

## Studio Base Audit

```text
hostname=MochiFufus-Mac-Studio.local
user=mochifufu
architecture=arm64
macOS=26.5.1
timezone=America/Los_Angeles
scheduler=unloaded
```

Tailscale and non-interactive SSH access from the MacBook Air passed. The Air
now has a concrete `quant-studio` SSH alias for Codex remote-project discovery.

## Source Bootstrap

Created from GitHub commit `3f60b4f`:

```text
/Users/mochifufu/Code/quant-system
/Users/mochifufu/Code/quant-system-runtime
```

Installed `uv 0.11.20` and synchronized both clones with development and Alpaca
broker extras. Both clones passed:

```text
ruff=passed
pyright=passed
pytest=212 passed
```

A fresh clone initially exposed one non-hermetic health test dependency on an
ambient log file. Creating the expected ignored bootstrap log allowed the
environment-level verification to pass. A future test-improvement milestone
should make that test independent of repository-local logs.

## Runtime-State Transfer

The Air development workspace and runtime clone held distinct valid history:

```text
orders:
  canceled May smoke order
  filled June strategy sell
snapshots=14
workflows=8
fills=0
```

They were merged into a secret-free archive:

```text
/Users/ziyuan/Code/quant-system-migration/
  quant-runtime-state-20260611T033335Z.tar.gz
  quant-runtime-state-20260611T033335Z.tar.gz.sha256
```

The checksum passed before and after transfer. `.env` was transferred
separately and its Studio permissions are `600`.

## Launchd State

The Studio-local plist uses Studio runtime paths, passed `plutil -lint`, and
remains:

```text
Disabled=true
```

The job was not installed or loaded. Both the Air and Studio schedulers remain
unloaded.

## No-Order Studio Verification

The Studio runtime passed:

1. full `make check`,
2. migration host audit,
3. preflight-only wrapper execution,
4. fresh read-only Alpaca paper account snapshot, and
5. fresh Alpaca reconciliation.

Latest Studio read-only result:

```text
cash=100290.73
buying_power=399643.06
positions=1
retained_position=AAPL:-1
open_orders=0
reconciliation=passed
differences=0
snapshots_after_verification=15
scheduler=unloaded
```

## Codex Readiness

Installed `codex-cli 0.139.0` on the Studio. Existing ChatGPT authentication
was valid, and `codex doctor --json` reported overall status `ok`.

GitHub SSH push authentication is not configured on the Studio yet. The public
repository was cloned over HTTPS; configure a Studio-specific GitHub SSH key
before pushing development changes.

## Next Gate

Continue milestone 87 from the Studio runtime clone after the regular market
opens. Refresh the current `F` price and broker truth, request immediate
explicit approval, and execute only the dedicated controlled paper rehearsal.
Keep launchd unloaded until that evidence is reviewed.
