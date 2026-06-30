"""Inspect and execute reviewed activated dry-run operator requests."""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
    run_semantic_target_paper_transition,
)
from quant.execution.target_paper import SemanticPaperTransitionRunResult
from quant.models.activation import (
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationScope,
)
from quant.models.execution import OrderSide, TradingMode, TradingSafetyCheck
from quant.models.operator import (
    ActivatedDryRunOperatorRequest,
    ActivatedDryRunRequestInspection,
    ActivatedSemanticPaperOperatorRequest,
    ActivatedSemanticPaperRequestInspection,
)
from quant.models.targets import (
    ContributorSet,
    PortfolioTargetStatus,
    RiskTargetStatus,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
)
from quant.research.portfolio_targets import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)
from quant.research.target_artifacts import (
    load_contributor_set,
    load_strategy_evaluation,
    load_strategy_target_decision,
)
from quant.workflows.activated_semantic_targets import (
    ActivatedSemanticTargetWorkflowResult,
    run_activated_semantic_target_dry_run_workflow,
    run_activated_semantic_target_paper_workflow,
)
from quant.workflows.activation_consumption_rehearsal import (
    load_and_verify_activation_consumption_rehearsal,
)
from quant.workflows.semantic_target_activation import (
    inspect_semantic_target_activation,
    rehearsal_report_sha256,
)
from quant.workflows.semantic_target_rehearsal import (
    load_and_verify_semantic_target_rehearsal,
)


@dataclass(frozen=True)
class ActivatedDryRunOperatorResult:
    request_artifact_path: Path
    activated_workflow: ActivatedSemanticTargetWorkflowResult


@dataclass(frozen=True)
class ActivatedSemanticPaperOperatorResult:
    request_artifact_path: Path
    activated_workflow: ActivatedSemanticTargetWorkflowResult


@dataclass(frozen=True)
class ActivatedSemanticPaperTransitionOperatorResult:
    request_artifact_path: Path
    transition_result: SemanticPaperTransitionRunResult


def inspect_activated_dry_run_operator_request(
    request_path: Path,
    *,
    inspected_at: datetime | None = None,
) -> ActivatedDryRunRequestInspection:
    """Explain a request without writing, consuming, or executing artifacts."""
    request = load_activated_dry_run_operator_request(request_path)
    current_time = inspected_at or datetime.now(UTC)
    issues: list[str] = []
    authorization = SemanticTargetActivationAuthorization.model_validate_json(
        Path(request.authorization_path).read_text()
    )
    activation = inspect_semantic_target_activation(
        evaluation_id=request.activation_evaluation_id,
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=Path(request.rehearsal_report_path),
        evaluated_at=current_time,
    )
    issues.extend(activation.issues)

    try:
        base_rehearsal_passed = load_and_verify_semantic_target_rehearsal(
            Path(request.rehearsal_report_path)
        ).passed
    except (OSError, ValueError):
        base_rehearsal_passed = False
    activation_consumption_rehearsal_passed = False
    try:
        activation_rehearsal = (
            load_and_verify_activation_consumption_rehearsal(
                Path(request.activation_consumption_rehearsal_report_path)
            )
        )
        activation_consumption_rehearsal_passed = (
            activation_rehearsal.passed
            and rehearsal_report_sha256(Path(request.rehearsal_report_path))
            == activation_rehearsal.base_rehearsal_report_sha256
        )
        if not activation_consumption_rehearsal_passed:
            issues.append(
                "activation-consumption rehearsal does not match the "
                "passing base rehearsal"
            )
    except (OSError, ValueError) as error:
        issues.append(
            f"activation-consumption rehearsal verification failed: {error}"
        )

    contributor_set = load_contributor_set(Path(request.contributor_set_path))
    decisions = tuple(
        load_strategy_target_decision(Path(path))
        for path in request.strategy_decision_paths
    )
    evaluations = tuple(
        load_strategy_evaluation(Path(path))
        for path in request.strategy_evaluation_paths
    )
    issues.extend(
        _strategy_evaluation_issues(contributor_set, decisions, evaluations)
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id=request.portfolio_target_id,
        revision=request.portfolio_target_revision,
        contributor_set=contributor_set,
        decisions=decisions,
        evaluated_at=current_time,
    )
    if portfolio_target.status != PortfolioTargetStatus.AGGREGATED:
        issues.append(portfolio_target.reason)
        issues.extend(
            item.reason
            for item in portfolio_target.contribution_evaluations
            if item.target_value is None
        )
    risk_target = evaluate_research_risk_target(
        risk_target_id=request.risk_target_id,
        revision=request.risk_target_revision,
        portfolio_target=portfolio_target,
        policy=request.risk_policy,
        evaluated_at=current_time,
    )
    if risk_target.status != RiskTargetStatus.APPROVED:
        issues.extend(risk_target.reasons)

    target = risk_target.approved_target_value
    if target is not None and target != target.to_integral_value():
        issues.append("operational dry-run requires a whole-share target")
    if request.account.open_order_ids:
        issues.append("account snapshot contains unsettled working orders")
    issues.extend(_execution_policy_issues(request))

    current = next(
        (
            position.quantity
            for position in request.account.positions
            if position.symbol == contributor_set.symbol
        ),
        0,
    )
    side: OrderSide | None = None
    quantity: int | None = None
    notional: float | None = None
    if target is not None and target == target.to_integral_value():
        delta = int(target) - current
        if delta:
            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            quantity = abs(delta)
            notional = quantity * request.reference_price

    valid = not issues
    summary = _inspection_summary(
        valid=valid,
        symbol=contributor_set.symbol,
        current=current,
        target=target,
        side=side,
        quantity=quantity,
    )
    return ActivatedDryRunRequestInspection(
        request_id=request.request_id,
        inspected_at=current_time,
        valid_now=valid,
        issues=tuple(dict.fromkeys(issues)),
        symbol=contributor_set.symbol,
        current_quantity=current,
        approved_target_quantity=target,
        intended_order_side=side,
        intended_order_quantity=quantity,
        intended_order_notional=notional,
        reference_price=request.reference_price,
        authorization_id=authorization.authorization_id,
        authorization_effective_status=activation.effective_status,
        authorization_valid_until=authorization.valid_until,
        base_rehearsal_passed=base_rehearsal_passed,
        activation_consumption_rehearsal_passed=(
            activation_consumption_rehearsal_passed
        ),
        summary=summary,
    )


def inspect_activated_semantic_paper_operator_request(
    request_path: Path,
    *,
    inspected_at: datetime | None = None,
) -> ActivatedSemanticPaperRequestInspection:
    """Explain a semantic-paper request without writing any artifacts."""
    request = load_activated_semantic_paper_operator_request(request_path)
    current_time = inspected_at or datetime.now(UTC)
    issues: list[str] = []
    authorization = SemanticTargetActivationAuthorization.model_validate_json(
        Path(request.authorization_path).read_text()
    )
    activation = inspect_semantic_target_activation(
        evaluation_id=request.activation_evaluation_id,
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.SEMANTIC_PAPER,
        rehearsal_report_path=Path(request.rehearsal_report_path),
        evaluated_at=current_time,
    )
    issues.extend(activation.issues)

    try:
        base_rehearsal_passed = load_and_verify_semantic_target_rehearsal(
            Path(request.rehearsal_report_path)
        ).passed
    except (OSError, ValueError):
        base_rehearsal_passed = False
    activation_consumption_rehearsal_passed = False
    try:
        activation_rehearsal = (
            load_and_verify_activation_consumption_rehearsal(
                Path(request.activation_consumption_rehearsal_report_path)
            )
        )
        activation_consumption_rehearsal_passed = (
            activation_rehearsal.passed
            and rehearsal_report_sha256(Path(request.rehearsal_report_path))
            == activation_rehearsal.base_rehearsal_report_sha256
        )
        if not activation_consumption_rehearsal_passed:
            issues.append(
                "activation-consumption rehearsal does not match the "
                "passing base rehearsal"
            )
    except (OSError, ValueError) as error:
        issues.append(
            f"activation-consumption rehearsal verification failed: {error}"
        )

    contributor_set = load_contributor_set(Path(request.contributor_set_path))
    decisions = tuple(
        load_strategy_target_decision(Path(path))
        for path in request.strategy_decision_paths
    )
    evaluations = tuple(
        load_strategy_evaluation(Path(path))
        for path in request.strategy_evaluation_paths
    )
    issues.extend(
        _strategy_evaluation_issues(contributor_set, decisions, evaluations)
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id=request.portfolio_target_id,
        revision=request.portfolio_target_revision,
        contributor_set=contributor_set,
        decisions=decisions,
        evaluated_at=current_time,
    )
    if portfolio_target.status != PortfolioTargetStatus.AGGREGATED:
        issues.append(portfolio_target.reason)
        issues.extend(
            item.reason
            for item in portfolio_target.contribution_evaluations
            if item.target_value is None
        )
    risk_target = evaluate_research_risk_target(
        risk_target_id=request.risk_target_id,
        revision=request.risk_target_revision,
        portfolio_target=portfolio_target,
        policy=request.risk_policy,
        evaluated_at=current_time,
    )
    if risk_target.status != RiskTargetStatus.APPROVED:
        issues.extend(risk_target.reasons)

    target = risk_target.approved_target_value
    if target is not None and target != target.to_integral_value():
        issues.append(
            "operational semantic paper requires a whole-share target"
        )
    issues.extend(_execution_policy_issues(request))

    current = next(
        (
            position.quantity
            for position in request.initial_positions
            if position.symbol == contributor_set.symbol
        ),
        0,
    )
    side: OrderSide | None = None
    quantity: int | None = None
    notional: float | None = None
    if target is not None and target == target.to_integral_value():
        delta = int(target) - current
        if delta:
            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            quantity = abs(delta)
            notional = quantity * request.reference_price

    valid = not issues
    summary = _inspection_summary(
        valid=valid,
        symbol=contributor_set.symbol,
        current=current,
        target=target,
        side=side,
        quantity=quantity,
        mode_label="semantic paper would submit",
    )
    return ActivatedSemanticPaperRequestInspection(
        request_id=request.request_id,
        inspected_at=current_time,
        valid_now=valid,
        issues=tuple(dict.fromkeys(issues)),
        symbol=contributor_set.symbol,
        current_quantity=current,
        approved_target_quantity=target,
        intended_order_side=side,
        intended_order_quantity=quantity,
        intended_order_notional=notional,
        reference_price=request.reference_price,
        initial_cash=request.initial_cash,
        authorization_id=authorization.authorization_id,
        authorization_effective_status=activation.effective_status,
        authorization_valid_until=authorization.valid_until,
        base_rehearsal_passed=base_rehearsal_passed,
        activation_consumption_rehearsal_passed=(
            activation_consumption_rehearsal_passed
        ),
        summary=summary,
    )


def run_activated_dry_run_operator_request(
    *,
    request_path: Path,
    activation_root: Path,
    output_root: Path,
) -> ActivatedDryRunOperatorResult:
    """Load, preserve, and execute one reviewed activated dry-run request."""
    request = load_activated_dry_run_operator_request(request_path)
    request_artifact_path = _persist_or_verify_request(request, output_root)
    activation_rehearsal_path = Path(
        request.activation_consumption_rehearsal_report_path
    )
    activation_rehearsal = load_and_verify_activation_consumption_rehearsal(
        activation_rehearsal_path
    )
    if (
        not activation_rehearsal.passed
        or rehearsal_report_sha256(Path(request.rehearsal_report_path))
        != activation_rehearsal.base_rehearsal_report_sha256
    ):
        raise ValueError(
            "operator request does not match passing activation rehearsal"
        )
    authorization = SemanticTargetActivationAuthorization.model_validate_json(
        Path(request.authorization_path).read_text()
    )
    result = run_activated_semantic_target_dry_run_workflow(
        activation_evaluation_id=request.activation_evaluation_id,
        authorization=authorization,
        rehearsal_report_path=Path(request.rehearsal_report_path),
        activation_root=activation_root,
        orchestration_id=request.orchestration_id,
        contributor_set=load_contributor_set(
            Path(request.contributor_set_path)
        ),
        strategy_decisions=tuple(
            load_strategy_target_decision(Path(path))
            for path in request.strategy_decision_paths
        ),
        strategy_evaluations=tuple(
            load_strategy_evaluation(Path(path))
            for path in request.strategy_evaluation_paths
        ),
        risk_policy=request.risk_policy,
        portfolio_target_id=request.portfolio_target_id,
        portfolio_target_revision=request.portfolio_target_revision,
        risk_target_id=request.risk_target_id,
        risk_target_revision=request.risk_target_revision,
        account=request.account,
        policy=request.execution_policy,
        reference_price=request.reference_price,
        safety_check=_allowed_dry_run_check(),
        output_root=output_root,
        evaluated_at=request.evaluated_at,
        evidence_refs=(
            *request.evidence_refs,
            str(request_artifact_path),
            str(activation_rehearsal_path),
        ),
    )
    return ActivatedDryRunOperatorResult(
        request_artifact_path=request_artifact_path,
        activated_workflow=result,
    )


def run_activated_semantic_paper_operator_request(
    *,
    request_path: Path,
    activation_root: Path,
    output_root: Path,
) -> ActivatedSemanticPaperOperatorResult:
    """Load, preserve, and execute one reviewed local semantic-paper request."""
    request = load_activated_semantic_paper_operator_request(request_path)
    request_artifact_path = _persist_or_verify_paper_request(
        request, output_root
    )
    activation_rehearsal_path = Path(
        request.activation_consumption_rehearsal_report_path
    )
    _verify_paper_request_activation_evidence(request)
    authorization = SemanticTargetActivationAuthorization.model_validate_json(
        Path(request.authorization_path).read_text()
    )
    result = run_activated_semantic_target_paper_workflow(
        activation_evaluation_id=request.activation_evaluation_id,
        authorization=authorization,
        rehearsal_report_path=Path(request.rehearsal_report_path),
        activation_root=activation_root,
        orchestration_id=request.orchestration_id,
        contributor_set=load_contributor_set(
            Path(request.contributor_set_path)
        ),
        strategy_decisions=tuple(
            load_strategy_target_decision(Path(path))
            for path in request.strategy_decision_paths
        ),
        strategy_evaluations=tuple(
            load_strategy_evaluation(Path(path))
            for path in request.strategy_evaluation_paths
        ),
        risk_policy=request.risk_policy,
        portfolio_target_id=request.portfolio_target_id,
        portfolio_target_revision=request.portfolio_target_revision,
        risk_target_id=request.risk_target_id,
        risk_target_revision=request.risk_target_revision,
        policy=request.execution_policy,
        reference_price=request.reference_price,
        safety_check=_allowed_paper_check(),
        output_root=output_root,
        initial_cash=request.initial_cash,
        initial_positions=request.initial_positions,
        evaluated_at=request.evaluated_at,
        evidence_refs=(
            *request.evidence_refs,
            str(request_artifact_path),
            str(activation_rehearsal_path),
        ),
    )
    return ActivatedSemanticPaperOperatorResult(
        request_artifact_path=request_artifact_path,
        activated_workflow=result,
    )


def run_activated_semantic_paper_transition_operator_request(
    *,
    request_path: Path,
    output_root: Path,
) -> ActivatedSemanticPaperTransitionOperatorResult:
    """Run one reviewed local semantic-paper request through transition legs."""
    request = load_activated_semantic_paper_operator_request(request_path)
    request_artifact_path = _persist_or_verify_paper_request(
        request, output_root
    )
    _verify_paper_request_activation_evidence(request)
    contributor_set = load_contributor_set(Path(request.contributor_set_path))
    strategy_decisions = tuple(
        load_strategy_target_decision(Path(path))
        for path in request.strategy_decision_paths
    )
    evaluations = tuple(
        load_strategy_evaluation(Path(path))
        for path in request.strategy_evaluation_paths
    )
    evaluation_issues = _strategy_evaluation_issues(
        contributor_set, strategy_decisions, evaluations
    )
    if evaluation_issues:
        raise ValueError("; ".join(evaluation_issues))
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id=request.portfolio_target_id,
        revision=request.portfolio_target_revision,
        contributor_set=contributor_set,
        decisions=strategy_decisions,
        evaluated_at=request.evaluated_at,
    )
    risk_target = evaluate_research_risk_target(
        risk_target_id=request.risk_target_id,
        revision=request.risk_target_revision,
        portfolio_target=portfolio_target,
        policy=request.risk_policy,
        evaluated_at=request.evaluated_at,
    )
    transition_root = output_root / "semantic-paper-transition"
    transition_result = run_semantic_target_paper_transition(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        risk_policy=request.risk_policy,
        policy=request.execution_policy,
        reference_price=request.reference_price,
        safety_check=_allowed_paper_check(),
        state_path=transition_root / "state.json",
        artifact_root=transition_root / "lifecycle",
        order_output_dir=transition_root / "orders",
        fill_output_dir=transition_root / "fills",
        snapshot_output_dir=transition_root / "snapshots",
        reconciliation_output_dir=transition_root / "reconciliations",
        initial_cash=request.initial_cash,
        initial_positions=request.initial_positions,
        evaluated_at=request.evaluated_at,
        evidence_refs=(
            *request.evidence_refs,
            str(request_artifact_path),
            str(request.activation_consumption_rehearsal_report_path),
        ),
    )
    return ActivatedSemanticPaperTransitionOperatorResult(
        request_artifact_path=request_artifact_path,
        transition_result=transition_result,
    )


def load_activated_dry_run_operator_request(
    path: Path,
) -> ActivatedDryRunOperatorRequest:
    return ActivatedDryRunOperatorRequest.model_validate_json(path.read_text())


def load_activated_semantic_paper_operator_request(
    path: Path,
) -> ActivatedSemanticPaperOperatorRequest:
    return ActivatedSemanticPaperOperatorRequest.model_validate_json(
        path.read_text()
    )


def write_activated_dry_run_operator_request(
    request: ActivatedDryRunOperatorRequest,
    output_root: Path,
) -> Path:
    path = output_root / f"{request.request_id}.json"
    _write_model_exclusive(path, request)
    return path


def write_activated_semantic_paper_operator_request(
    request: ActivatedSemanticPaperOperatorRequest,
    output_root: Path,
) -> Path:
    path = output_root / f"{request.request_id}.json"
    _write_model_exclusive(path, request)
    return path


def _persist_or_verify_request(
    request: ActivatedDryRunOperatorRequest,
    output_root: Path,
) -> Path:
    path = output_root / "operator-requests" / f"{request.request_id}.json"
    if path.exists():
        if load_activated_dry_run_operator_request(path) != request:
            raise ValueError(
                "immutable activated dry-run operator request conflicts"
            )
        return path
    _write_model_exclusive(path, request)
    return path


def _persist_or_verify_paper_request(
    request: ActivatedSemanticPaperOperatorRequest,
    output_root: Path,
) -> Path:
    path = output_root / "operator-requests" / f"{request.request_id}.json"
    if path.exists():
        if load_activated_semantic_paper_operator_request(path) != request:
            raise ValueError(
                "immutable activated semantic-paper operator request conflicts"
            )
        return path
    _write_model_exclusive(path, request)
    return path


def _verify_paper_request_activation_evidence(
    request: ActivatedSemanticPaperOperatorRequest,
) -> None:
    activation_rehearsal_path = Path(
        request.activation_consumption_rehearsal_report_path
    )
    activation_rehearsal = load_and_verify_activation_consumption_rehearsal(
        activation_rehearsal_path
    )
    if (
        not activation_rehearsal.passed
        or rehearsal_report_sha256(Path(request.rehearsal_report_path))
        != activation_rehearsal.base_rehearsal_report_sha256
    ):
        raise ValueError(
            "operator request does not match passing activation rehearsal"
        )


def _allowed_dry_run_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.DRY_RUN, allowed=True)


def _allowed_paper_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.PAPER, allowed=True)


def _strategy_evaluation_issues(
    contributor_set: ContributorSet,
    decisions: tuple[StrategyTargetDecision, ...],
    evaluations: tuple[StrategyEvaluation, ...],
) -> tuple[str, ...]:
    expected = {
        (item.strategy_id, item.strategy_version)
        for item in contributor_set.expected_contributors
    }
    seen: set[tuple[str, str]] = set()
    decision_by_id = {item.decision_id: item for item in decisions}
    issues: list[str] = []
    if len(decision_by_id) != len(decisions):
        issues.append("strategy decision IDs are not unique")
    for evaluation in evaluations:
        identity = (evaluation.strategy_id, evaluation.strategy_version)
        if (
            identity not in expected
            or evaluation.symbol != contributor_set.symbol
        ):
            issues.append(
                "a strategy evaluation is outside the contributor set"
            )
        if identity in seen:
            issues.append("a contributor has more than one strategy evaluation")
        seen.add(identity)
        if evaluation.outcome != StrategyEvaluationOutcome.UNAVAILABLE:
            decision = decision_by_id.get(
                evaluation.effective_target_decision_id or ""
            )
            if decision is None or (
                decision.strategy_id,
                decision.strategy_version,
                decision.symbol,
            ) != (
                evaluation.strategy_id,
                evaluation.strategy_version,
                evaluation.symbol,
            ):
                issues.append(
                    "a strategy evaluation does not reference its "
                    "effective decision"
                )
    if seen != expected:
        issues.append("every expected contributor requires one evaluation")
    return tuple(issues)


def _execution_policy_issues(
    request: (
        ActivatedDryRunOperatorRequest | ActivatedSemanticPaperOperatorRequest
    ),
) -> tuple[str, ...]:
    policy = request.execution_policy
    issues: list[str] = []
    if policy.execution_policy_version != SINGLE_MARKET_ORDER_POLICY:
        issues.append("execution policy version is not supported")
    if (
        policy.reconciliation_policy_version
        != ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
    ):
        issues.append("reconciliation policy version is not supported")
    if policy.drift_policy_version != DETECT_ONLY_DRIFT_POLICY:
        issues.append("drift policy version is not supported")
    return tuple(issues)


def _inspection_summary(
    *,
    valid: bool,
    symbol: str,
    current: int,
    target: Decimal | None,
    side: OrderSide | None,
    quantity: int | None,
    mode_label: str = "dry-run would record",
) -> str:
    if not valid:
        return "The request is blocked and must not be run."
    if target is None:
        return "The request has no approved target."
    if side is None or quantity is None:
        return f"{symbol} is already at the approved target of {target} shares."
    return (
        f"The {mode_label} an intended {side.value.upper()} "
        f"of {quantity} {symbol} shares, moving from {current} to {target}."
    )


def _write_model_exclusive(
    path: Path,
    request: (
        ActivatedDryRunOperatorRequest | ActivatedSemanticPaperOperatorRequest
    ),
) -> None:
    payload = (
        json.dumps(request.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
