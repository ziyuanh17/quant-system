# Web Console Deployment Guide

This document covers deploying the quant-system web console on the Mac Studio.

## Quick Start

```bash
# Start the server locally
quant web serve

# Or with custom port
quant web serve --port 8080
```

The console will be available at `http://127.0.0.1:8000`.

## Production Deployment

### 1. Generate API Key

```bash
openssl rand -hex 32
```

Copy the output and set it as `QUANT_CONSOLE_API_KEY` in `.env` or the launchd plist.

### 2. Configure `.env`

```bash
QUANT_CONSOLE_API_KEY=<your-generated-key>
```

### 3. Start Manually

```bash
quant web serve --host 127.0.0.1 --port 8000
```

### 4. Install launchd Service

```bash
# Follow the localization and verification procedure first.
# The API key remains in the runtime clone's .env, never in the plist.
cp configs/launchd/com.quant-system.console.plist.example \
   configs/launchd/com.quant-system.console.local.plist

# Load the service
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist
```

### 5. Verify

```bash
# Check the service is running
launchctl list | grep quant-system.console

# Test authentication (should return 401)
curl http://127.0.0.1:8000/api/v1/overview

# Test with API key (should return 200)
curl -H "Authorization: Bearer YOUR_KEY" \
     http://127.0.0.1:8000/api/v1/overview
```

## Network Security

- **Tailscale Serve (recommended):** Keep the console on `127.0.0.1` and proxy
  it privately with `tailscale serve --bg 8000`. See
  [console_remote_access.md](console_remote_access.md).
- **Reverse proxy:** Place the console behind nginx/Caddy with HTTPS and
  basic auth if you need external access.
- **Never bind to `0.0.0.0`** without a reverse proxy or network-level security.

## Backup

The console reads from local artifacts. Back up:

- `site/` — published knowledge index and status snapshots
- `data/web/console.db` — SQLite historical observability database
- `configs/launchd/com.quant-system.console.local.plist` — localized launchd
  configuration
- `.env` — API key (keep secret)

## Rollback

```bash
# Stop the service
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist

# Restore from backup
cp /backup/site/site/knowledge_index.json site/knowledge_index.json
cp /backup/data/web/console.db data/web/console.db

# Restart
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist
```

## Known Limits

- Single-threaded uvicorn (no async workers)
- No rate limiting
- No session management (API key only)
- No HTTPS in the app (use reverse proxy)
- SQLite for historical data (not suitable for high write volume)
- No caching — docs are scanned on each request
