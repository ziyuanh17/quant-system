from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quant.models.targets import (
    ContributionStatus,
    ContributorSet,
    ContributorSpec,
    PortfolioTargetStatus,
    ResearchRiskPolicy,
    RiskTargetStatus,
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.research import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
    load_contributor_set,
    load_portfolio_target_decision,
    load_risk_target_decision,
    write_contributor_set,
    write_portfolio_target_decision,
    write_risk_target_decision,
)


def test_contributor_set_rejects_duplicate_ownership() -> None:
    contributor = ContributorSpec(strategy_id="momentum", strategy_version="2")

    with pytest.raises(ValidationError, match="must be unique"):
        _contributor_set(expected_contributors=(contributor, contributor))


def test_aggregation_sums_signed_targets_in_contributor_order() -> None:
    evaluated_at = _now()
    contributor_set = _contributor_set()
    decisions = (
        _decision(
            decision_id="mean-reversion-4",
            strategy_id="mean-reversion",
            strategy_version="1",
            target_value=Decimal("4"),
        ),
        _decision(
            decision_id="momentum-minus-10",
            strategy_id="momentum",
            strategy_version="2",
            target_value=Decimal("-10"),
        ),
    )

    target = aggregate_strategy_targets(
        portfolio_target_id="portfolio-1",
        revision=1,
        contributor_set=contributor_set,
        decisions=decisions,
        evaluated_at=evaluated_at,
    )

    assert target.status == PortfolioTargetStatus.AGGREGATED
    assert target.aggregate_value == Decimal("-6")
    assert target.contributing_decision_ids == (
        "momentum-minus-10",
        "mean-reversion-4",
    )
    assert all(
        item.contribution_status == ContributionStatus.INCLUDED
        for item in target.contribution_evaluations
    )


def test_aggregation_preserves_fractional_research_targets() -> None:
    target = aggregate_strategy_targets(
        portfolio_target_id="portfolio-fractional",
        revision=1,
        contributor_set=_contributor_set(),
        decisions=(
            _decision(
                decision_id="momentum-fractional",
                target_value=Decimal("-1.5"),
            ),
            _decision(
                decision_id="mean-reversion-fractional",
                strategy_id="mean-reversion",
                strategy_version="1",
                target_value=Decimal("0.25"),
            ),
        ),
        evaluated_at=_now(),
    )

    assert target.aggregate_value == Decimal("-1.25")


def test_aggregation_rejects_unsupported_policy_version() -> None:
    contributor_set = _contributor_set().model_copy(
        update={"portfolio_policy_version": "unknown_v1"}
    )

    with pytest.raises(ValueError, match="unsupported portfolio policy"):
        aggregate_strategy_targets(
            portfolio_target_id="portfolio-unsupported",
            revision=1,
            contributor_set=contributor_set,
            decisions=(),
            evaluated_at=_now(),
        )


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    [
        ("missing", ContributionStatus.MISSING),
        ("duplicate", ContributionStatus.DUPLICATE),
        ("unavailable", ContributionStatus.UNAVAILABLE),
        ("wrong-unit", ContributionStatus.UNIT_MISMATCH),
    ],
)
def test_aggregation_blocks_ineligible_contributors(
    scenario: str,
    expected_status: ContributionStatus,
) -> None:
    decisions_by_scenario = {
        "missing": (),
        "duplicate": (
            _decision(decision_id="duplicate-1"),
            _decision(decision_id="duplicate-2"),
        ),
        "unavailable": (
            _decision(
                decision_id="unavailable",
                target_value=None,
                declared_status=TargetDeclaredStatus.UNAVAILABLE,
            ),
        ),
        "wrong-unit": (
            _decision(
                decision_id="wrong-unit",
                unit=TargetUnit.NOTIONAL,
            ),
        ),
    }
    contributor_set = _contributor_set(
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        )
    )

    target = aggregate_strategy_targets(
        portfolio_target_id=f"portfolio-{expected_status.value}",
        revision=1,
        contributor_set=contributor_set,
        decisions=decisions_by_scenario[scenario],
        evaluated_at=_now(),
    )

    assert target.status == PortfolioTargetStatus.BLOCKED
    assert target.aggregate_value is None
    assert target.contributing_decision_ids == ()
    assert (
        target.contribution_evaluations[0].contribution_status
        == expected_status
    )
    if expected_status == ContributionStatus.DUPLICATE:
        assert target.contribution_evaluations[0].matched_decision_ids == (
            "duplicate-1",
            "duplicate-2",
        )


def test_aggregation_blocks_stale_target_instead_of_flattening() -> None:
    contributor_set = _contributor_set(
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=60,
    )

    target = aggregate_strategy_targets(
        portfolio_target_id="portfolio-stale",
        revision=1,
        contributor_set=contributor_set,
        decisions=(_decision(decision_id="stale"),),
        evaluated_at=_now() + timedelta(minutes=2),
    )

    assert target.status == PortfolioTargetStatus.BLOCKED
    assert (
        target.contribution_evaluations[0].contribution_status
        == ContributionStatus.STALE
    )


def test_risk_approves_exact_aggregate_without_resizing() -> None:
    portfolio_target = _aggregated_target()

    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-approved",
        revision=1,
        portfolio_target=portfolio_target,
        policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        evaluated_at=_now(),
    )

    assert risk_target.status == RiskTargetStatus.APPROVED
    assert risk_target.approved_target_value == portfolio_target.aggregate_value


def test_risk_rejects_without_clamping() -> None:
    portfolio_target = _aggregated_target()

    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-rejected",
        revision=1,
        portfolio_target=portfolio_target,
        policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("5"),
        ),
        evaluated_at=_now(),
    )

    assert risk_target.status == RiskTargetStatus.REJECTED
    assert risk_target.approved_target_value is None
    assert risk_target.reasons == ("absolute target exceeds policy limit",)


def test_risk_rejects_unsupported_policy_version() -> None:
    with pytest.raises(ValueError, match="unsupported risk policy"):
        evaluate_research_risk_target(
            risk_target_id="risk-unsupported",
            revision=1,
            portfolio_target=_aggregated_target(),
            policy=ResearchRiskPolicy(risk_policy_version="unknown_v1"),
            evaluated_at=_now(),
        )


def test_blocked_portfolio_target_is_rejected_by_risk() -> None:
    blocked = aggregate_strategy_targets(
        portfolio_target_id="portfolio-blocked",
        revision=1,
        contributor_set=_contributor_set(),
        decisions=(),
        evaluated_at=_now(),
    )

    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-blocked",
        revision=1,
        portfolio_target=blocked,
        policy=ResearchRiskPolicy(risk_policy_version="approve_or_reject_v1"),
        evaluated_at=_now(),
    )

    assert risk_target.status == RiskTargetStatus.REJECTED
    assert risk_target.reasons == ("portfolio target is blocked",)


def test_portfolio_and_risk_artifacts_are_immutable(tmp_path) -> None:
    contributor_set = _contributor_set()
    portfolio_target = _aggregated_target()
    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-artifact",
        revision=1,
        portfolio_target=portfolio_target,
        policy=ResearchRiskPolicy(risk_policy_version="approve_or_reject_v1"),
        evaluated_at=_now(),
    )

    contributor_path = write_contributor_set(
        contributor_set, tmp_path / "contributor-sets"
    )
    portfolio_path = write_portfolio_target_decision(
        portfolio_target, tmp_path / "portfolio-targets"
    )
    risk_path = write_risk_target_decision(
        risk_target, tmp_path / "risk-targets"
    )

    assert load_contributor_set(contributor_path) == contributor_set
    assert load_portfolio_target_decision(portfolio_path) == portfolio_target
    assert load_risk_target_decision(risk_path) == risk_target
    with pytest.raises(FileExistsError):
        write_contributor_set(contributor_set, tmp_path / "contributor-sets")
    with pytest.raises(FileExistsError):
        write_portfolio_target_decision(
            portfolio_target, tmp_path / "portfolio-targets"
        )
    with pytest.raises(FileExistsError):
        write_risk_target_decision(risk_target, tmp_path / "risk-targets")


def _aggregated_target():
    return aggregate_strategy_targets(
        portfolio_target_id="portfolio-aggregate",
        revision=1,
        contributor_set=_contributor_set(),
        decisions=(
            _decision(decision_id="momentum-minus-10"),
            _decision(
                decision_id="mean-reversion-4",
                strategy_id="mean-reversion",
                strategy_version="1",
                target_value=Decimal("4"),
            ),
        ),
        evaluated_at=_now(),
    )


def _contributor_set(
    *,
    expected_contributors: tuple[ContributorSpec, ...] = (
        ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ContributorSpec(strategy_id="mean-reversion", strategy_version="1"),
    ),
    max_age_seconds: int = 3600,
) -> ContributorSet:
    return ContributorSet(
        contributor_set_id="aapl-research-v1",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=expected_contributors,
        max_age_seconds=max_age_seconds,
        portfolio_policy_version="sum_active_targets_v1",
        reason="research contributor ownership",
    )


def _decision(
    *,
    decision_id: str,
    strategy_id: str = "momentum",
    strategy_version: str = "2",
    target_value: Decimal | None = Decimal("-10"),
    declared_status: TargetDeclaredStatus = TargetDeclaredStatus.ACTIVE,
    unit: TargetUnit = TargetUnit.SHARES,
) -> StrategyTargetDecision:
    now = _now()
    return StrategyTargetDecision(
        decision_id=decision_id,
        revision=1,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        symbol="AAPL",
        unit=unit,
        target_value=target_value,
        sizing_policy_version="fixed_shares_v1",
        input_data_id="bars-sha256",
        generated_at=now,
        effective_at=now,
        valid_until=now + timedelta(days=1),
        declared_status=declared_status,
        reason="research target",
    )


def _now() -> datetime:
    return datetime(2026, 6, 12, 12, tzinfo=UTC)
