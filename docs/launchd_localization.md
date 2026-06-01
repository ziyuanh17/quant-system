# Launchd Localization Runbook

This runbook explains how to turn the checked-in Alpaca paper launchd template
into a local machine-specific plist. It does not enable the schedule by itself.

Use this only after reviewing:

- [alpaca_paper_schedule.md](alpaca_paper_schedule.md)
- [alpaca_paper_smoke_execution.md](alpaca_paper_smoke_execution.md)
- [alpaca_paper_wrapper_run.md](alpaca_paper_wrapper_run.md)

## Why Localize

The checked-in template intentionally contains placeholder paths:

```text
/absolute/path/to/quant-system
```

Those paths are machine-specific and should not be committed. A local plist
copy lets launchd run the wrapper from the correct repo directory while keeping
the repository portable.

## Files

Checked-in template:

```text
configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example
```

Suggested local untracked copy:

```text
configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

The local copy is ignored by git.

## Localize

From the repo root:

```bash
cp \
  configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example \
  configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Replace every placeholder path with this repo's absolute path:

```bash
repo_root="$(pwd)"
perl -pi -e "s#/absolute/path/to/quant-system#$repo_root#g" \
  configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Keep `Disabled` set to `true` until the preflight and one manual wrapper run
have both passed.

## Validate

Check the plist syntax:

```bash
plutil -lint configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Confirm the localized file is not tracked:

```bash
git status --short configs/launchd/
```

Run wrapper preflight:

```bash
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true bash scripts/run_alpaca_paper_refresh.sh
```

Run one manual full wrapper cycle:

```bash
bash scripts/run_alpaca_paper_refresh.sh
```

Publish Alpaca-only dashboard status:

```bash
quant ops publish-status \
  --no-check-paper-service \
  --no-check-comparison \
  --check-alpaca-paper
```

Review `site/status.json`, the latest wrapper log, and Alpaca paper dashboard
state before loading launchd.

## Load Later

Only after explicit review, copy the localized plist into the user launchd
directory:

```bash
cp \
  configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Edit the copied file under `~/Library/LaunchAgents/` and set `Disabled` to
`false`.

Then load it:

```bash
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Kick off one manual launchd run:

```bash
launchctl kickstart \
  gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Inspect:

```text
logs/launchd-alpaca-paper-refresh.out.log
logs/launchd-alpaca-paper-refresh.err.log
logs/alpaca-paper-refresh-*.log
site/status.json
```

## Disable Or Unload

Disable the job:

```bash
launchctl disable gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Unload the job:

```bash
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Remove the installed plist only after unloading:

```bash
rm ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Do not remove local logs or artifacts until they have been reviewed.

## Safety Notes

- This is still Alpaca paper only.
- Do not put API keys into the plist.
- Keep secrets in `.env`.
- Do not commit the localized plist.
- Do not enable launchd before preflight, one manual full wrapper run, and
  dashboard review.
- Stop and inspect if reconciliation fails or if Alpaca shows an unexpected
  open paper order.
