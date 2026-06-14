"""Research API endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key

router = APIRouter(tags=["research"])


@router.get("/families", dependencies=[Depends(require_api_key)])
async def list_families() -> dict:
    """List research families.."""
    now = datetime.now(UTC)
    # No research artifacts exist yet — return empty list
    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "families": [],
    }


@router.get(
    "/candidates/{candidate_id}", dependencies=[Depends(require_api_key)]
)
async def get_candidate(candidate_id: str) -> dict:
    """Detail for one research candidate.."""
    now = datetime.now(UTC)
    # No research artifacts exist yet — return empty detail
    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "candidate": {
            "candidateId": candidate_id,
            "familyId": "",
            "hypothesis": "",
            "strategyName": "",
            "strategyVersion": "",
            "parameters": [],
            "symbols": [],
            "splitPolicy": None,
            "evaluationResults": None,
            "comparison": None,
            "recommendation": None,
            "trialCount": 0,
            "trials": [],
            "dataLineage": [],
            "reproducibilityStatus": None,
            "promotionRecommendation": None,
        },
    }
