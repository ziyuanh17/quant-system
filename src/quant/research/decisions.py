"""Load and validate research decision reports."""

from pathlib import Path

from quant.models.research import ResearchBatchSpec, ResearchDecisionReport


def load_research_decision_report(path: Path) -> ResearchDecisionReport:
    """Load a schema-versioned research decision report."""
    return ResearchDecisionReport.model_validate_json(path.read_text())


def validate_decision_report_against_batch(
    report: ResearchDecisionReport,
    batch: ResearchBatchSpec,
) -> None:
    """Fail when decision metadata diverges from the reviewed batch spec."""
    if report.batch_id != batch.batch_id:
        raise ValueError("decision report batch_id does not match batch")

    candidates_by_id = {
        candidate.candidate_id: candidate for candidate in batch.candidates
    }
    decisions_by_id = {
        decision.candidate_id: decision for decision in report.decisions
    }
    if set(decisions_by_id) != set(candidates_by_id):
        raise ValueError("decision report candidate set does not match batch")

    for candidate_id, decision in decisions_by_id.items():
        candidate = candidates_by_id[candidate_id]
        if decision.comparison_role != candidate.comparison_role:
            raise ValueError(
                f"decision comparison_role does not match batch for "
                f"{candidate_id}"
            )
        if decision.promotion_eligible != candidate.promotion_eligible:
            raise ValueError(
                f"decision promotion_eligible does not match batch for "
                f"{candidate_id}"
            )
