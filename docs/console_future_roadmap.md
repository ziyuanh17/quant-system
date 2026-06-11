# Web Console Future Roadmap

## Potential Future Enhancements

### Priority 1: Real-time Updates

- Server-Sent Events (SSE) for live status updates
- WebSocket support for real-time decision traces
- Configurable polling interval (currently hardcoded to 60s)

### Priority 2: Multi-User Support

- Role-based access control (RBAC)
- Separate keys for operator, researcher, and reviewer roles
- Session management with token refresh
- Login page with username/password

### Priority 3: Alerting

- Email alerts for failed reconciliations
- Slack/Teams webhook integration
- Alert routing based on severity
- Incident auto-creation from failed health checks

### Priority 4: Historical Trending

- Expand SQLite schema for portfolio/risk history
- Add time-series charts for P&L, drawdown, exposure
- Add time-series charts for broker/API latency
- Add time-series charts for resource saturation (disk, memory)

### Priority 5: Research Integration

- Connect to research evaluation harness
- Show champion/challenger comparisons
- Show promotion gate status
- Show dataset lineage and reproducibility status

### Priority 6: Broker Expansion

- Connect to additional broker adapters
- Show multi-broker reconciliation
- Show cross-broker P&L aggregation

### Priority 7: Infrastructure

- Docker container support
- systemd service files for Linux
- Health check endpoint (`/health`)
- Graceful shutdown handling
- Multiple uvicorn workers

## Deferred Beyond V1

- Order submission or cancellation
- Human approval workflows
- Scheduler start/stop controls
- Risk-limit editing
- Strategy promotion into execution
- Real-money trading controls
- Public exposure of private console data
