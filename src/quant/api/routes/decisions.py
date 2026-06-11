"""Decision trace API endpoints."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key

router = APIRouter(tags=["decisions"])

_DATA_DIR = Path("data")


def _sanitize_decision(data: dict, decision_id: str, observed_at: str) -> dict:
    """Return the allowlisted fields safe for the private console."""
    decision = data.get("decision", {})
    trade = data.get("trade") or {}
    fill = trade.get("fill") or {}
    return {
        "decisionId": decision_id,
        "strategy": data.get("strategy", "momentum"),
        "symbol": decision.get("symbol"),
        "signal": decision.get("action", "unknown"),
        "signalDate": decision.get("signal_date"),
        "signalReason": decision.get("reason", ""),
        "marketPrice": decision.get("market_price"),
        "outcome": "skipped"
        if data.get("skipped")
        else decision.get("action", "unknown"),
        "environment": "local-paper",
        "fillStatus": fill.get("status"),
        "fillQuantity": fill.get("quantity"),
        "fillPrice": fill.get("price"),
        "observedAt": observed_at,
    }


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_decisions(page: int = 1, page_size: int = 50) -> dict:
    """List automatic decisions."""
    now = datetime.now(UTC)
    signals_dir = _DATA_DIR / "paper" / "signals"
    items = []

    if signals_dir.exists():
        for filepath in sorted(
            signals_dir.rglob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(filepath.read_text())
                items.append(
                    {
                        "id": filepath.stem,
                        "decisionId": filepath.stem,
                        "strategy": data.get("strategy", "momentum"),
                        "signal": data.get("decision", {}).get(
                            "action", "unknown"
                        ),
                        "outcome": data.get("decision", {}).get(
                            "action", "unknown"
                        ),
                        "environment": "local-paper",
                        "observedAt": data.get("snapshot", {}).get(
                            "captured_at", now.isoformat()
                        ),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": items[start:end],
    }


@router.get("/{decision_id}", dependencies=[Depends(require_api_key)])
async def get_decision(decision_id: str) -> dict:
    """Detail for one automatic decision."""
    now = datetime.now(UTC)
    signals_dir = _DATA_DIR / "paper" / "signals"

    if signals_dir.exists():
        for filepath in signals_dir.rglob(f"{decision_id}*.json"):
            try:
                data = json.loads(filepath.read_text())
                observed_at = data.get("snapshot", {}).get(
                    "captured_at", now.isoformat()
                )
                return {
                    "schema": {
                        "schemaVersion": "v1",
                        "generatedAt": now.isoformat(),
                    },
                    "decision": _sanitize_decision(
                        data,
                        filepath.stem,
                        observed_at,
                    ),
                }
            except (json.JSONDecodeError, OSError):
                continue

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "decision": {
            "decisionId": decision_id,
            "strategy": "",
            "signal": "",
            "outcome": "not_found",
            "environment": "local-paper",
            "observedAt": now.isoformat(),
        },
    }
