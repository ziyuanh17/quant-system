"""Accounts API endpoints.."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key
from quant.api.freshness import EXPECTED_FRESHNESS
from quant.api.models import (
    AccountSummary,
    Environment,
    Status,
    StatusValue,
)

router = APIRouter(tags=["accounts"])

_DATA_DIR = Path("data")


def _status_from_value(value, source, is_stale=False, message=""):
    """Convert a string status to a Status model."""
    state_map = {
        "healthy": StatusValue.HEALTHY,
        "degraded": StatusValue.DEGRADED,
        "failed": StatusValue.FAILED,
        "running": StatusValue.RUNNING,
        "disabled": StatusValue.DISABLED,
        "not_configured": StatusValue.NOT_CONFIGURED,
        "unknown": StatusValue.UNKNOWN,
        "stale": StatusValue.STALE,
        "skipped": StatusValue.UNKNOWN,
        "passed": StatusValue.HEALTHY,
    }
    return Status(
        state=state_map.get(value, StatusValue.UNKNOWN),
        severity="ok" if value in ("healthy", "not_configured", "skipped", "passed") else "error",
        observed_at=datetime.now(timezone.utc),
        source_updated_at=None,
        expected_freshness_seconds=EXPECTED_FRESHNESS.get(source, 3600),
        is_stale=is_stale,
        source_type=source,
        message=message,
    )


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_accounts() -> dict:
    """List all configured accounts."""
    now = datetime.now(timezone.utc)

    # Try to read paper broker state
    state_path = _DATA_DIR / "paper" / "state" / "default.json"
    paper_cash = None
    paper_positions = 0
    paper_status = _status_from_value("not_configured", "paper_state", message="not configured")

    if state_path.exists():
        try:
            data = json.loads(state_path.read_text())
            paper_cash = data.get("cash")
            paper_positions = len(data.get("positions", []))
            paper_status = _status_from_value("healthy", "paper_state")
        except (json.JSONDecodeError, OSError):
            pass

    # Check for Alpaca paper artifacts
    alpaca_workflow_dir = _DATA_DIR / "workflows" / "alpaca-paper-refresh"
    alpaca_status = _status_from_value("not_configured", "broker_snapshot", message="not configured")
    if alpaca_workflow_dir.exists():
        alpaca_files = list(alpaca_workflow_dir.glob("*.json"))
        if alpaca_files:
            alpaca_status = _status_from_value("healthy", "broker_snapshot")

    accounts = [
        AccountSummary(
            environment=Environment.LOCAL_PAPER,
            broker="paper",
            account_alias="local-paper",
            connection=paper_status,
            trading_permission="simulated",
            equity=paper_cash,
            cash=paper_cash,
            position_count=paper_positions,
            open_order_count=0,
            reconciliation=paper_status,
            freshness=paper_status,
        ),
        AccountSummary(
            environment=Environment.DRY_RUN,
            broker="dry-run",
            account_alias="dry-run",
            connection=_status_from_value("not_configured", "paper_state", message="record only"),
            trading_permission="record only",
            equity=None,
            cash=None,
            position_count=0,
            open_order_count=0,
            reconciliation=_status_from_value("not_configured", "reconciliation", message="record only"),
            freshness=_status_from_value("not_configured", "paper_state", message="record only"),
        ),
        AccountSummary(
            environment=Environment.ALPACA_PAPER,
            broker="alpaca-paper",
            account_alias="alpaca-paper",
            connection=alpaca_status,
            trading_permission="paper orders" if alpaca_status.state != StatusValue.NOT_CONFIGURED else "disabled",
            equity=None,
            cash=None,
            position_count=0,
            open_order_count=0,
            reconciliation=alpaca_status,
            freshness=alpaca_status,
        ),
        AccountSummary(
            environment=Environment.REAL_MONEY,
            broker="none",
            account_alias="real-money",
            connection=_status_from_value("not_configured", "real_money", message="not configured"),
            trading_permission="not_configured",
            equity=None,
            cash=None,
            position_count=0,
            open_order_count=0,
            reconciliation=_status_from_value("not_configured", "real_money", message="not configured"),
            freshness=_status_from_value("not_configured", "real_money", message="not configured"),
        ),
    ]

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "accounts": [a.model_dump() for a in accounts],
    }


@router.get("/{account_alias}", dependencies=[Depends(require_api_key)])
async def get_account(
    account_alias: str,
) -> dict:
    """Detail for one account."""
    now = datetime.now(timezone.utc)

    # Try to read paper broker state
    state_path = _DATA_DIR / "paper" / "state" / "default.json"
    positions = []
    cash = None

    if state_path.exists() and account_alias == "local-paper":
        try:
            data = json.loads(state_path.read_text())
            cash = data.get("cash")
            positions = data.get("positions", [])
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "account": {
            "permission": {
                "environment": account_alias,
                "broker": account_alias,
                "accountAlias": account_alias,
                "connection": _status_from_value(
                "healthy" if account_alias == "local-paper" and state_path.exists() else "not_configured",
                "broker_snapshot",
                ).model_dump(),
                "tradingPermission": "simulated" if account_alias == "local-paper" else "not_configured",
                "safetyGateStatus": _status_from_value(
                "healthy" if account_alias == "local-paper" else "not_configured",
                "health_check",
                ).model_dump(),
                "maxOrderNotional": None,
                "riskLimits": {},
                "lastSnapshotAt": datetime.now(timezone.utc).isoformat() if state_path.exists() else None,
            },
            "risk": {},
            "performance": {},
            "positions": positions,
            "openOrders": [],
            "recentFills": [],
            "reconciliation": _status_from_value(
                "healthy" if account_alias == "local-paper" and state_path.exists() else "not_configured",
                "reconciliation",
            ),
            "latestDecision": None,
            "cash": cash,
        },
    }
