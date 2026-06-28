"""Test fake-client semantic-target Alpaca paper rehearsals."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quant.execution import LIVE_TRADING_CONFIRMATION
from quant.models.execution import TradingMode, TradingSafetyConfig
from quant.models.execution_lifecycle import (
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.operator import SemanticTargetAlpacaPaperOperatorRequest
from quant.models.targets import ResearchRiskPolicy
from quant.workflows import (
    load_and_verify_semantic_target_alpaca_paper_rehearsal,
    load_semantic_target_alpaca_paper_operator_request,
    load_semantic_target_alpaca_paper_run_verification_report,
    run_semantic_target_alpaca_paper_fake_rehearsal,
    verify_semantic_target_alpaca_paper_run,
    write_semantic_target_alpaca_paper_run_verification_report,
)


def test_fake_alpaca_paper_rehearsal_reaches_satisfaction_once(
    tmp_path,
) -> None:
    report = run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="alpaca-paper-fake",
        output_root=tmp_path,
        evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
    )

    assert report.passed
    assert report.first_status == ExecutionPlanStatus.SATISFIED
    assert report.second_status == ExecutionPlanStatus.SATISFIED
    assert report.order_count == 1
    assert report.fill_count == 1
    assert report.final_position_quantity == 2
    assert report.reconciliation_report_count == 1
    assert report.prohibited_api_calls == ()
    assert all(str(tmp_path) in path for path in report.evidence_paths)

    verified = load_and_verify_semantic_target_alpaca_paper_rehearsal(
        tmp_path / "reports" / "alpaca-paper-fake.json"
    )
    assert verified == report

    request = load_semantic_target_alpaca_paper_operator_request(
        tmp_path / "requests" / "alpaca-paper-fake-request.json"
    )
    assert request.alpaca_submission_enabled is True
    assert request.safety_config.broker_name == "alpaca-paper"
    assert request.allowed_symbol == "AAPL"
    assert request.allowed_max_quantity == 2


def test_alpaca_paper_run_verifier_accepts_rehearsal_evidence(
    tmp_path,
) -> None:
    run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="alpaca-paper-fake",
        output_root=tmp_path,
        evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
    )

    verification = verify_semantic_target_alpaca_paper_run(
        tmp_path / "requests" / "alpaca-paper-fake-request.json",
        verified_at=datetime(2026, 6, 26, 12, 5, tzinfo=UTC),
    )

    assert verification.passed
    assert verification.final_status == ExecutionPlanStatus.SATISFIED
    assert verification.order_count == 1
    assert verification.fill_count == 1
    assert verification.reconciliation_report_count == 1
    assert verification.final_position_quantity == Decimal("2")
    assert verification.issues == ()


def test_alpaca_paper_run_verification_report_is_immutable(
    tmp_path,
) -> None:
    run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="alpaca-paper-fake",
        output_root=tmp_path,
        evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
    )
    request_path = tmp_path / "requests" / "alpaca-paper-fake-request.json"
    verification = verify_semantic_target_alpaca_paper_run(
        request_path,
        verified_at=datetime(2026, 6, 26, 12, 5, tzinfo=UTC),
    )
    report_path = tmp_path / "reports" / "verification.json"

    written_path = write_semantic_target_alpaca_paper_run_verification_report(
        verification=verification,
        request_path=request_path,
        output_path=report_path,
    )
    loaded = load_semantic_target_alpaca_paper_run_verification_report(
        written_path
    )

    assert loaded.passed
    assert loaded.request_id == "alpaca-paper-fake-request"
    assert loaded.request_path == str(request_path)
    assert loaded.event_count == 4
    assert loaded.order_count == 1
    assert loaded.fill_count == 1
    assert loaded.reconciliation_report_count == 1

    with pytest.raises(FileExistsError):
        write_semantic_target_alpaca_paper_run_verification_report(
            verification=verification,
            request_path=request_path,
            output_path=report_path,
        )


def test_alpaca_paper_run_verifier_blocks_missing_reconciliation(
    tmp_path,
) -> None:
    run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="alpaca-paper-fake",
        output_root=tmp_path,
        evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
    )
    reconciliation_path = next(
        (tmp_path / "output" / "reconciliations").rglob("*.json")
    )
    reconciliation_path.unlink()

    verification = verify_semantic_target_alpaca_paper_run(
        tmp_path / "requests" / "alpaca-paper-fake-request.json",
        verified_at=datetime(2026, 6, 26, 12, 5, tzinfo=UTC),
    )

    assert not verification.passed
    assert "expected at least one reconciliation report" in verification.issues


def test_alpaca_paper_run_verifier_blocks_tampered_request_input(
    tmp_path,
) -> None:
    run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="alpaca-paper-fake",
        output_root=tmp_path,
        evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
    )
    risk_target_path = next(
        (tmp_path / "inputs" / "risk-targets").rglob("*.json")
    )
    risk_target_path.write_text(risk_target_path.read_text() + "\n")

    verification = verify_semantic_target_alpaca_paper_run(
        tmp_path / "requests" / "alpaca-paper-fake-request.json",
        verified_at=datetime(2026, 6, 26, 12, 5, tzinfo=UTC),
    )

    assert not verification.passed
    assert any("hash mismatch" in issue for issue in verification.issues)


def test_fake_alpaca_paper_rehearsal_detects_tampered_evidence(
    tmp_path,
) -> None:
    run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="alpaca-paper-fake",
        output_root=tmp_path,
        evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
    )
    state_path = tmp_path / "output" / "snapshots"
    first_snapshot = next(state_path.rglob("*.json"))
    first_snapshot.write_text(first_snapshot.read_text() + "\n")

    with pytest.raises(ValueError, match="evidence hash mismatch"):
        load_and_verify_semantic_target_alpaca_paper_rehearsal(
            tmp_path / "reports" / "alpaca-paper-fake.json"
        )


def test_alpaca_paper_request_requires_alpaca_paper_safety() -> None:
    with pytest.raises(ValidationError, match="alpaca-paper broker"):
        SemanticTargetAlpacaPaperOperatorRequest(
            request_id="bad-request",
            contributor_set_path="contributor.json",
            contributor_set_sha256="0" * 64,
            strategy_decision_paths=("decision.json",),
            strategy_decision_sha256s=("1" * 64,),
            portfolio_target_path="portfolio.json",
            portfolio_target_sha256="2" * 64,
            risk_target_path="risk.json",
            risk_target_sha256="3" * 64,
            risk_policy=ResearchRiskPolicy(
                risk_policy_version="approve_or_reject_v1",
                max_absolute_target=Decimal("100"),
            ),
            execution_policy=ExecutionLifecyclePolicy(
                execution_policy_version="single_market_order_v1",
                reconciliation_policy_version=(
                    "account_wide_exact_reconciliation_v1"
                ),
                drift_policy_version="detect_only_v1",
            ),
            reference_price=100,
            safety_config=TradingSafetyConfig(
                mode=TradingMode.LIVE,
                live_trading_enabled=True,
                live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
                max_order_notional=1000,
                broker_name="alpaca-live",
            ),
            output_root="output",
            evaluated_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
            valid_until=datetime(2026, 6, 26, 12, 30, tzinfo=UTC),
            alpaca_submission_enabled=True,
            allowed_symbol="AAPL",
            allowed_max_quantity=Decimal("2"),
        )
