"""Decision trace API endpoints.

Provides automatic decision history and individual decision traces.

"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["decisions"])


@router.get("/")
async def list_decisions(page: int = 1, page_size: int = 50) -> dict:
     """List automatic decisions.

      Returns
      -------
      dict
          Paginated decision list.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "total": 0,
          "page": page,
          "pageSize": page_size,
          "items": [],
       }


@router.get("/{decision_id}")
async def get_decision(decision_id: str) -> dict:
     """Detail for one automatic decision trace.

      Returns
      -------
      dict
          Full decision trace.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "decision": {
               "triggerSource": "scheduler",
               "isScheduled": True,
               "strategy": "momentum",
               "strategyVersion": "1.0.0",
               "sourceCommit": "",
               "inputData": "",
               "signal": "hold",
               "signalReason": "",
               "intendedSide": None,
               "intendedQuantity": None,
               "intendedPriceReference": None,
               "intendedNotional": None,
               "riskGates": [],
               "submissionAttempted": None,
               "submissionReason": None,
               "brokerResult": None,
               "orderState": None,
               "fillState": None,
               "beforeSnapshot": None,
               "afterSnapshot": None,
               "reconciliation": None,
               "outcome": "hold",
               "stopReason": None,
               "observedAt": now.isoformat(),
            },
       }
