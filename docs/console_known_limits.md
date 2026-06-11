# Web Console Known Limits

## What the Console Can Do

- Display read-only operational status from local artifacts
- Show account lanes (local paper, dry-run, Alpaca paper, real-money)
- Show automatic decision traces from workflow runs
- Browse and search `docs/` documentation
- Show system component flow diagram
- Display incident history from incident documents
- Show research families and candidate details
- Query historical observability data from SQLite

## What the Console Cannot Do

- Submit, cancel, or modify orders
- Change scheduler state or configuration
- Edit risk limits or safety gates
- Promote research candidates to execution
- Access `.env`, credentials, or raw broker API responses
- Stream real-time data (polling only, 60s interval)
- Handle concurrent users (single-threaded uvicorn)
- Cache data (scans disk on each request)

## Security Limits

- API key authentication only (no OAuth, no sessions)
- No rate limiting
- No HTTPS in the app (use reverse proxy or Tailscale)
- No audit logging beyond access logs
- No multi-user support

## Performance Limits

- Single-threaded uvicorn (no async workers)
- No connection pooling (SQLite)
- No caching (docs scanned on each request)
- Designed for solo operator, not multi-user
- 60-second polling interval (not real-time)

## Data Limits

- Reads from local JSON artifacts only
- No network calls to external APIs (except broker adapters)
- Historical data stored in SQLite (limited by disk)
- No data retention policy configured
- No automated cleanup of old artifacts

## Deployment Limits

- macOS only (launchd, not systemd/cron)
- Mac Studio only (not tested on Linux)
- No container support (Docker/Kubernetes)
- No health check endpoint (only `/api/v1/`)
- No graceful shutdown handling
