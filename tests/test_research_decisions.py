"""Test research decision report validation."""

import json
from pathlib import Path

import pytest

from quant.models.research import (
    ResearchComparisonRole,
    ResearchDecisionReport,
)
from quant.research import (
    load_research_batch_spec,
    load_research_decision_report,
    validate_decision_report_against_batch,
)


def test_checked_in_aapl_decision_report_matches_batch() -> None:
    batch = load_research_batch_spec(
        Path("data/research/strategy-batches/aapl-strategy-research-batch-v1")
    )
    report = load_research_decision_report(
        Path("data/research/reports/aapl-strategy-research-batch-v1/decision.json")
    )

    validate_decision_report_against_batch(report, batch)

    assert all(
        decision.comparison_role == ResearchComparisonRole.DECLARED_POLICY
        for decision in report.decisions
    )


def test_decision_report_rejects_promotion_eligible_sizing_ablation() -> None:
    payload = json.loads(
        Path(
            "data/research/reports/aapl-strategy-research-batch-v1/decision.json"
        ).read_text()
    )
    payload["decisions"][0]["comparison_role"] = "sizing_ablation"
    payload["decisions"][0]["promotion_eligible"] = True

    with pytest.raises(ValueError, match="sizing-ablation decisions"):
        ResearchDecisionReport.model_validate(payload)


def test_decision_report_validator_rejects_batch_metadata_mismatch() -> None:
    batch = load_research_batch_spec(
        Path("data/research/strategy-batches/aapl-strategy-research-batch-v1")
    )
    report = load_research_decision_report(
        Path("data/research/reports/aapl-strategy-research-batch-v1/decision.json")
    )
    payload = report.model_dump(mode="json")
    payload["decisions"][0]["promotion_eligible"] = False
    mismatched = ResearchDecisionReport.model_validate(payload)

    with pytest.raises(ValueError, match="promotion_eligible"):
        validate_decision_report_against_batch(mismatched, batch)
