# Web Console Security Boundary

## What the Console Can See

- Local JSON artifacts in `data/` (scheduler runs, paper signals, broker state)
- Local Markdown docs in `docs/`
- SQLite database in `data/web/console.db`
- Log files in `logs/`
- Configuration in `configs/` (non-secret values only)

## What the Console Cannot See

- `.env` file contents
- Broker API keys, secret keys, or confirmation phrases
- Raw broker API responses
- Raw account IDs
- Network traffic between the Mac Studio and external services

## What the Console Cannot Do

- Submit, cancel, or modify orders
- Change scheduler state or configuration
- Edit risk limits or safety gates
- Promote research candidates to execution
- Write to `data/` directories (read-only)
- Access files outside the project root

## Network Boundary

- Default: binds to `127.0.0.1` (local only)
- For remote access: use private Tailscale Serve or an authenticated reverse
  proxy
- Never bind to `0.0.0.0` without a reverse proxy or network-level security
- No HTTPS in the app (use reverse proxy for HTTPS)
- Never use Tailscale Funnel for the private console

## Authentication Model

- API key via `QUANT_CONSOLE_API_KEY` environment variable
- Passed as `Authorization: Bearer <key>` header
- No session management (stateless)
- No token refresh or expiration
- No multi-user support (single shared key)

## Data Classification

- **Private:** All API endpoints, including schema discovery, require
  authentication
- **Sensitive:** Account data, decision traces, research data
- **Prohibited:** Credentials, API keys, raw broker payloads, confirmation phrases

## Redaction Rules

- No field matching `api_key`, `secret_key`, `token`, `password`, `credential`
- No field matching `raw_response` or `raw_response_ref`
- No field matching `private_key`
- Account IDs are redacted to aliases (e.g., "local-paper", "alpaca-paper")
- Raw broker payloads are never exposed
