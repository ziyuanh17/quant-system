# Web Console Remote Access Through Tailscale

This runbook exposes the read-only web console privately to devices in the
owner's Tailscale tailnet. It does not use Tailscale Funnel and does not expose
the console to the public internet.

## Architecture

```text
authorized tailnet device
  -> Tailscale Serve HTTPS URL
  -> http://127.0.0.1:8000
  -> authenticated read-only quant console
```

The console must remain bound to `127.0.0.1`. Tailscale Serve is the only
remote ingress path.

## Source And Runtime Boundary

Prepare and review deployment files in the development clone. Install and run
the service from the Studio runtime clone only after reviewed changes have
been promoted through GitHub.

Current intended runtime clone:

```text
/Users/mochifufu/Code/quant-system-runtime
```

## Runtime Configuration

Set these values in the runtime clone's untracked `.env`. Use the exact login
shown by `tailscale status --json` for the intended owner:

```text
QUANT_CONSOLE_AUTH_MODE=tailscale
QUANT_CONSOLE_TAILSCALE_USERS=owner@example.com
QUANT_CONSOLE_HOST=127.0.0.1
QUANT_CONSOLE_PORT=8000
```

API-key mode remains available as a fallback. Do not put keys or identity
configuration in the launchd plist.

## Manual Verification

From the runtime clone:

```bash
bash scripts/run_web_console.sh
```

In another terminal:

```bash
curl http://127.0.0.1:8000/api/v1/
curl http://127.0.0.1:8000/api/v1/overview
```

Direct localhost API requests without Tailscale identity headers should return
`401`. Verify authenticated access through the Tailscale Serve HTTPS URL.

## Localize And Install Launchd

From the runtime clone:

```bash
cp configs/launchd/com.quant-system.console.plist.example \
  configs/launchd/com.quant-system.console.local.plist

repo_root="$(pwd)"
perl -pi -e "s#/absolute/path/to/quant-system#$repo_root#g" \
  configs/launchd/com.quant-system.console.local.plist

plutil -lint configs/launchd/com.quant-system.console.local.plist
```

After manual verification passes, copy the localized plist into
`~/Library/LaunchAgents/`, change `Disabled` to `false`, and bootstrap it:

```bash
cp configs/launchd/com.quant-system.console.local.plist \
  ~/Library/LaunchAgents/com.quant-system.console.plist

launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist
```

Verify:

```bash
launchctl print gui/$(id -u)/com.quant-system.console
curl http://127.0.0.1:8000/api/v1/
```

## Enable Private Tailscale Access

Configure a persistent private HTTPS proxy:

```bash
tailscale serve --bg 8000
tailscale serve status
```

Open the displayed `https://...ts.net` URL from an authorized and allowlisted
Tailscale device. No additional console API key is required.

Do not use `tailscale funnel`.

## Rollback

Disable remote ingress:

```bash
tailscale serve reset
```

Unload the console service:

```bash
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist
```

The trading scheduler and broker workflows are independent of this read-only
console service.
