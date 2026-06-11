"""Research API endpoints.

Provides research family listing, candidate detail, and trial ledger.

"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["research"])


@router.get("/families")
async def list_families() -> dict:
     """List research families.

      Returns
      -------
      dict
          Research family summaries.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "families": [],
       }


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str) -> dict:
     """Detail for one research candidate.

      Returns
      -------
      dict
          Candidate detail with evaluation results, trials, and
          promotion recommendation.

      """
     now = datetime.now(timezone.utc)
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
