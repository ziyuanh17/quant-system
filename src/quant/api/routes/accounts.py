"""Accounts API endpoints.

Provides account listing and detail views.

"""

from datetime import datetime, timezone

from fastapi import APIRouter, Path

from quant.api.freshness import EXPECTED_FRESHNESS
from quant.api.models import (
    AccountSummary,
    Environment,
    Status,
    StatusValue,
)

router = APIRouter(tags=["accounts"])


def _not_configured(source: str = "system") -> Status:
     """Return a not_configured status."""
     return Status(
         state=StatusValue.NOT_CONFIGURED,
         severity="ok",
         observed_at=datetime.now(timezone.utc),
         source_updated_at=None,
         expected_freshness_seconds=EXPECTED_FRESHNESS.get(source, 3600),
         is_stale=False,
         source_type=source,
         message="not configured",
     )


@router.get("/")
async def list_accounts() -> dict:
     """List all configured accounts."""
     now = datetime.now(timezone.utc)

     accounts = [
         AccountSummary(
             environment=Environment.LOCAL_PAPER,
             broker="paper",
             account_alias="local-paper",
             connection=_not_configured("paper_state"),
             trading_permission="simulated",
             equity=None,
             cash=None,
             position_count=0,
             open_order_count=0,
             reconciliation=_not_configured("reconciliation"),
             freshness=_not_configured("paper_state"),
         ),
         AccountSummary(
             environment=Environment.DRY_RUN,
             broker="dry-run",
             account_alias="dry-run",
             connection=_not_configured("paper_state"),
             trading_permission="record only",
             equity=None,
             cash=None,
             position_count=0,
             open_order_count=0,
             reconciliation=_not_configured("reconciliation"),
             freshness=_not_configured("paper_state"),
         ),
         AccountSummary(
             environment=Environment.ALPACA_PAPER,
             broker="alpaca-paper",
             account_alias="alpaca-paper",
             connection=_not_configured("broker_snapshot"),
             trading_permission="paper orders",
             equity=None,
             cash=None,
             position_count=0,
             open_order_count=0,
             reconciliation=_not_configured("reconciliation"),
             freshness=_not_configured("broker_snapshot"),
         ),
         AccountSummary(
             environment=Environment.REAL_MONEY,
             broker="none",
             account_alias="real-money",
             connection=_not_configured(),
             trading_permission="not_configured",
             equity=None,
             cash=None,
             position_count=0,
             open_order_count=0,
             reconciliation=_not_configured(),
             freshness=_not_configured(),
         ),
     ]

     return {
         "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
         "accounts": [a.model_dump() for a in accounts],
     }


@router.get("/{account_alias}")
async def get_account(
     account_alias: str = Path(..., description="Account alias"),
) -> dict:
     """Detail for one account."""
     now = datetime.now(timezone.utc)
     nc = _not_configured

     return {
         "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
         "account": {
             "permission": {
                 "environment": "local-paper",
                 "broker": account_alias,
                 "accountAlias": account_alias,
                 "connection": nc("broker_snapshot").model_dump(),
                 "tradingPermission": "not_configured",
                 "safetyGateStatus": nc("health_check").model_dump(),
                 "maxOrderNotional": None,
                 "riskLimits": {},
                 "lastSnapshotAt": None,
             },
             "risk": {},
             "performance": {},
             "positions": [],
             "openOrders": [],
             "recentFills": [],
             "reconciliation": nc("reconciliation"),
             "latestDecision": None,
         },
     }
