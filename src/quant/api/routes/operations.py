"""Operations API endpoints.

Provides workflow run history, scheduled run history, and event timeline.

"""

from datetime import datetime, timezone

from fastapi import APIRouter

from quant.api.freshness import EXPECTED_FRESHNESS
from quant.api.models import Status, StatusValue

router = APIRouter(tags=["operations"])


def _nc(source: str = "system") -> dict:
     """Return a not_configured status dict."""
     return {
          "state": "not_configured",
          "severity": "ok",
          "observedAt": datetime.now(timezone.utc).isoformat(),
          "sourceUpdatedAT": None,
          "expectedFreshnessSeconds": EXPECTED_FRESHNESS.get(source, 3600),
          "isStale": False,
          "sourceType": source,
          "evidenceRef": None,
          "message": "not configured",
       }


@router.get("/runs")
async def list_runs(run_type: str = "all", page: int = 1, page_size: int = 50) -> dict:
     """List workflow and scheduled runs.

      Returns
      -------
      dict
          Paginated run list.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "runType": run_type,
          "total": 0,
          "page": page,
          "pageSize": page_size,
          "items": [],
       }


@router.get("/events")
async def list_events(page: int = 1, page_size: int = 50) -> dict:
     """List operational events.

      Returns
      -------
      dict
          Paginated event list.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "total": 0,
          "page": page,
          "pageSize": page_size,
          "items": [],
       }
