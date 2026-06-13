from datetime import datetime, timedelta
from decimal import Decimal

from quant.models.targets import (
    ContributionStatus,
    ContributorSet,
    PortfolioTargetDecision,
    PortfolioTargetStatus,
    ResearchRiskPolicy,
    RiskTargetDecision,
    RiskTargetStatus,
    StrategyTargetDecision,
    TargetContributionEvaluation,
    TargetEffectiveStatus,
)
from quant.research.targets import evaluate_target_effective_status

SUM_ACTIVE_TARGETS_POLICY = "sum_active_targets_v1"
APPROVE_OR_REJECT_RISK_POLICY = "approve_or_reject_v1"


def aggregate_strategy_targets(
    *,
    portfolio_target_id: str,
    revision: int,
    contributor_set: ContributorSet,
    decisions: tuple[StrategyTargetDecision, ...],
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> PortfolioTargetDecision:
    """Aggregate exactly the active targets owned by a contributor set."""
    if contributor_set.portfolio_policy_version != SUM_ACTIVE_TARGETS_POLICY:
        raise ValueError("unsupported portfolio policy version")
    evaluations = tuple(
        _evaluate_contributor(contributor_set, decisions, index, evaluated_at)
        for index in range(len(contributor_set.expected_contributors))
    )
    blocked = tuple(
        item
        for item in evaluations
        if item.contribution_status != ContributionStatus.INCLUDED
    )
    if blocked:
        return PortfolioTargetDecision(
            portfolio_target_id=portfolio_target_id,
            revision=revision,
            contributor_set_id=contributor_set.contributor_set_id,
            contributor_set_revision=contributor_set.revision,
            portfolio_policy_version=contributor_set.portfolio_policy_version,
            symbol=contributor_set.symbol,
            unit=contributor_set.unit,
            generated_at=evaluated_at,
            evaluated_at=evaluated_at,
            status=PortfolioTargetStatus.BLOCKED,
            contribution_evaluations=evaluations,
            reason="one or more expected contributors are not eligible",
            evidence_refs=evidence_refs,
        )

    values = tuple(item.target_value for item in evaluations)
    decision_ids = tuple(
        item.decision_id for item in evaluations if item.decision_id is not None
    )
    return PortfolioTargetDecision(
        portfolio_target_id=portfolio_target_id,
        revision=revision,
        contributor_set_id=contributor_set.contributor_set_id,
        contributor_set_revision=contributor_set.revision,
        portfolio_policy_version=contributor_set.portfolio_policy_version,
        symbol=contributor_set.symbol,
        unit=contributor_set.unit,
        generated_at=evaluated_at,
        evaluated_at=evaluated_at,
        status=PortfolioTargetStatus.AGGREGATED,
        aggregate_value=sum(
            (value for value in values if value is not None), Decimal("0")
        ),
        contributing_decision_ids=decision_ids,
        contribution_evaluations=evaluations,
        reason="all expected contributors aggregated",
        evidence_refs=evidence_refs,
    )


def evaluate_research_risk_target(
    *,
    risk_target_id: str,
    revision: int,
    portfolio_target: PortfolioTargetDecision,
    policy: ResearchRiskPolicy,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> RiskTargetDecision:
    """Approve the full aggregate or reject it; never resize it."""
    if policy.risk_policy_version != APPROVE_OR_REJECT_RISK_POLICY:
        raise ValueError("unsupported risk policy version")
    reasons: list[str] = []
    value = portfolio_target.aggregate_value
    if portfolio_target.status != PortfolioTargetStatus.AGGREGATED:
        reasons.append("portfolio target is blocked")
    elif value is None:
        reasons.append("portfolio target has no aggregate value")
    else:
        if not policy.allow_short_targets and value < 0:
            reasons.append("short targets are not allowed")
        if (
            policy.max_absolute_target is not None
            and abs(value) > policy.max_absolute_target
        ):
            reasons.append("absolute target exceeds policy limit")

    approved = not reasons
    return RiskTargetDecision(
        risk_target_id=risk_target_id,
        revision=revision,
        portfolio_target_id=portfolio_target.portfolio_target_id,
        risk_policy_version=policy.risk_policy_version,
        symbol=portfolio_target.symbol,
        unit=portfolio_target.unit,
        generated_at=evaluated_at,
        evaluated_at=evaluated_at,
        status=(
            RiskTargetStatus.APPROVED if approved else RiskTargetStatus.REJECTED
        ),
        approved_target_value=value if approved else None,
        reasons=("portfolio target approved without resizing",)
        if approved
        else tuple(reasons),
        evidence_refs=evidence_refs,
    )


def _evaluate_contributor(
    contributor_set: ContributorSet,
    decisions: tuple[StrategyTargetDecision, ...],
    contributor_index: int,
    evaluated_at: datetime,
) -> TargetContributionEvaluation:
    expected = contributor_set.expected_contributors[contributor_index]
    matches = [
        item
        for item in decisions
        if item.strategy_id == expected.strategy_id
        and item.strategy_version == expected.strategy_version
    ]
    if not matches:
        return TargetContributionEvaluation(
            strategy_id=expected.strategy_id,
            strategy_version=expected.strategy_version,
            contribution_status=ContributionStatus.MISSING,
            reason="expected contributor decision is missing",
        )
    if len(matches) > 1:
        return TargetContributionEvaluation(
            strategy_id=expected.strategy_id,
            strategy_version=expected.strategy_version,
            matched_decision_ids=tuple(
                sorted(item.decision_id for item in matches)
            ),
            contribution_status=ContributionStatus.DUPLICATE,
            reason="multiple decisions match expected contributor",
        )

    decision = matches[0]
    effective_status = evaluate_target_effective_status(
        decision,
        evaluated_at=evaluated_at,
        max_age=timedelta(seconds=contributor_set.max_age_seconds),
    )
    if decision.symbol != contributor_set.symbol:
        status = ContributionStatus.SYMBOL_MISMATCH
        reason = "contributor symbol does not match contributor set"
    elif decision.unit != contributor_set.unit:
        status = ContributionStatus.UNIT_MISMATCH
        reason = "contributor unit does not match contributor set"
    elif effective_status != TargetEffectiveStatus.ACTIVE:
        status = ContributionStatus(effective_status.value)
        reason = f"contributor effective status is {effective_status.value}"
    else:
        status = ContributionStatus.INCLUDED
        reason = "active contributor included"

    return TargetContributionEvaluation(
        strategy_id=expected.strategy_id,
        strategy_version=expected.strategy_version,
        matched_decision_ids=(decision.decision_id,),
        decision_id=decision.decision_id,
        effective_status=effective_status,
        contribution_status=status,
        target_value=decision.target_value
        if status == ContributionStatus.INCLUDED
        else None,
        reason=reason,
    )
