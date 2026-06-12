# Web Console Runbook

## Starting the Console

```bash
# Start locally (development)
quant web serve

# Custom port
quant web serve --port 8080

# Production (with API key)
QUANT_CONSOLE_API_KEY=$(openssl rand -hex 32) quant web serve
```

For the restart-safe runtime deployment and private iPhone access, follow
[console_remote_access.md](console_remote_access.md).

## Checking Health

```bash
# Check API is responding
curl http://127.0.0.1:8000/api/v1/

# Check overview (requires API key)
curl -H "Authorization: Bearer YOUR_KEY" \
     http://127.0.0.1:8000/api/v1/overview
```

## Publishing Status

```bash
# Publish operational health to site/status.json
quant ops publish-status

# Publish knowledge index to site/knowledge_index.json
quant ops publish-knowledge
```

## Viewing Logs

```bash
# Console server logs
tail -f logs/console.log

# Console error logs
tail -f logs/console-error.log
```

## Common Issues

**Console returns 401:** API key is required. Set `QUANT_CONSOLE_API_KEY` or
start without it for development.

**Overview shows "not_configured":** No workflow artifacts exist yet. Run
`quant workflow paper-signal-refresh` to generate data.

**Knowledge Center shows no documents:** Run `quant ops publish-knowledge` to
scan `docs/`.

## Backup

```bash
# Back up console data
tar czf /backup/quant-console-$(date +%Y%m%d).tar.gz \
     site/knowledge_index.json \
     data/web/console.db \
     configs/launchd/com.quant-system.console.local.plist
```

## Rollback

```bash
# Stop the service
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist

# Restore from backup
tar xzf /backup/quant-console-YYYYMMDD.tar.gz

# Restart
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.console.plist
```
