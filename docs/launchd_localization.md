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

For launchd execution on macOS, prefer a runtime clone outside protected
folders such as `Documents`. The current local runtime path is:

```text
/Users/ziyuan/Code/quant-system-runtime
```

See
[launchd_filesystem_permission_diagnosis.md](launchd_filesystem_permission_diagnosis.md)
for the reason and setup details.

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

When preparing the launchd runtime clone, run this from:

```text
/Users/ziyuan/Code/quant-system-runtime
```

Keep `Disabled` set to `true` until the preflight and one manual wrapper run
have both passed. Do not attempt `launchctl bootstrap` while this key is still
`true`; launchd treats that as disabled state and can reject the load.

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
`false`. This changes the plist from review-only to loadable. It does not
itself run the job.

Then load it:

```bash
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Only after a separate review, kick off one manual launchd run. The first
triggered execution should be preflight-only; see
[launchd_triggered_execution_rehearsal_design.md](launchd_triggered_execution_rehearsal_design.md).

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
- Do not point launchd at the Codex workspace under `Documents`; use the
  runtime clone outside protected folders.
- Do not enable launchd before preflight, one manual full wrapper run, and
  dashboard review.
- Do not bootstrap the plist while `Disabled=true`; switch it to
  `Disabled=false` only when you are ready for launchd to register the
  scheduled job.
- Bootstrapping registers the calendar schedule. It should not submit an order
  immediately unless a run trigger fires or `kickstart` is explicitly used.
- The first `kickstart` rehearsal should inject
  `QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true` through the installed plist's
  launchd environment, then unload and remove the plist after inspection.
- After the preflight kickstart passes from the runtime clone, review
  [launchd_full_wrapper_rehearsal_design.md](launchd_full_wrapper_rehearsal_design.md)
  before any non-preflight launchd `kickstart`.
- Stop and inspect if reconciliation fails or if Alpaca shows an unexpected
  open paper order.
