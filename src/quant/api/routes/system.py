"""System component API endpoints.."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key

router = APIRouter(tags=["system"])

_DATA_DIR = Path("data")


def _count_json_files(directory: Path) -> int:
    """Count JSON files in a directory (recursively)."""
    if not directory.exists():
        return 0
    return len(list(directory.rglob("*.json")))


@router.get("/components", dependencies=[Depends(require_api_key)])
async def list_components() -> dict:
    """List system components with implementation status.."""
    now = datetime.now(UTC)

    # Count runs per component from data directories
    scheduler_runs = _count_json_files(_DATA_DIR / "scheduler" / "latest")
    workflow_runs = _count_json_files(
        _DATA_DIR / "workflows" / "paper-signal-refresh"
    )
    paper_signals = _count_json_files(_DATA_DIR / "paper" / "signals")
    validation_runs = _count_json_files(_DATA_DIR / "validation")
    feature_runs = _count_json_files(_DATA_DIR / "features")

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "components": [
            {
                "name": "provider",
                "purpose": "Fetch raw market data",
                "inputs": [],
                "outputs": ["raw_data"],
                "implementationStatus": "implemented",
                "failureModes": ["network_failure", "rate_limit"],
                "safetyBoundary": "validation",
                "recentRuns": workflow_runs,
                "recentIssues": 0,
            },
            {
                "name": "normalizer",
                "purpose": "Normalize provider data to standard schema",
                "inputs": ["raw_data"],
                "outputs": ["normalized_data"],
                "implementationStatus": "implemented",
                "failureModes": ["schema_mismatch"],
                "safetyBoundary": "validation",
                "recentRuns": workflow_runs,
                "recentIssues": 0,
            },
            {
                "name": "validator",
                "purpose": "Validate normalized data integrity",
                "inputs": ["normalized_data"],
                "outputs": ["validation_report"],
                "implementationStatus": "implemented",
                "failureModes": ["data_corruption"],
                "safetyBoundary": "fail_closed",
                "recentRuns": validation_runs,
                "recentIssues": 0,
            },
            {
                "name": "features",
                "purpose": "Compute technical indicators",
                "inputs": ["normalized_data"],
                "outputs": ["feature_artifacts"],
                "implementationStatus": "implemented",
                "failureModes": ["missing_columns"],
                "safetyBoundary": "validation",
                "recentRuns": feature_runs,
                "recentIssues": 0,
            },
            {
                "name": "strategy",
                "purpose": "Generate trading signals",
                "inputs": ["feature_artifacts"],
                "outputs": ["signals"],
                "implementationStatus": "implemented",
                "failureModes": ["signal_error"],
                "safetyBoundary": "risk_overlay",
                "recentRuns": paper_signals,
                "recentIssues": 0,
            },
            {
                "name": "research_evaluation",
                "purpose": "Evaluate strategy candidates",
                "inputs": ["signals", "feature_artifacts"],
                "outputs": ["evaluation_artifacts"],
                "implementationStatus": "partial",
                "failureModes": ["evaluation_error"],
                "safetyBoundary": "research_only",
                "recentRuns": 0,
                "recentIssues": 0,
            },
            {
                "name": "risk",
                "purpose": "Apply risk constraints to signals",
                "inputs": ["signals"],
                "outputs": ["risk_checked_signals"],
                "implementationStatus": "implemented",
                "failureModes": ["risk_error"],
                "safetyBoundary": "fail_closed",
                "recentRuns": paper_signals,
                "recentIssues": 0,
            },
            {
                "name": "broker_adapter",
                "purpose": "Execute orders through broker API",
                "inputs": ["risk_checked_signals"],
                "outputs": ["order_responses"],
                "implementationStatus": "partial",
                "failureModes": ["broker_error"],
                "safetyBoundary": "safety_gates",
                "recentRuns": scheduler_runs,
                "recentIssues": 0,
            },
            {
                "name": "reconciliation",
                "purpose": "Compare local and broker records",
                "inputs": ["order_responses"],
                "outputs": ["reconciliation_report"],
                "implementationStatus": "implemented",
                "failureModes": ["reconciliation_error"],
                "safetyBoundary": "alert_on_failure",
                "recentRuns": scheduler_runs,
                "recentIssues": 0,
            },
            {
                "name": "operations",
                "purpose": "Health checks and monitoring",
                "inputs": ["reconciliation_report"],
                "outputs": ["health_status"],
                "implementationStatus": "implemented",
                "failureModes": ["health_check_error"],
                "safetyBoundary": "read_only",
                "recentRuns": scheduler_runs,
                "recentIssues": 0,
            },
        ],
    }
