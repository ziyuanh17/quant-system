"""Prepare reviewed local semantic-paper canary request artifacts."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from quant.data import load_price_csv, validate_market_bars_csv
from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
    decide_latest_signal,
)
from quant.models.activation import (
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationScope,
)
from quant.models.execution import PaperSignalAction, Position
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
from quant.models.operator import ActivatedSemanticPaperOperatorRequest
from quant.models.targets import (
    ContributorSet,
    ContributorSpec,
    ResearchRiskPolicy,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.research.target_artifacts import (
    write_contributor_set,
    write_strategy_evaluation,
    write_strategy_target_decision,
)
from quant.strategies import MomentumConfig, MomentumStrategy
from quant.workflows.activated_dry_run_operator import (
    write_activated_semantic_paper_operator_request,
)
from quant.workflows.activation_consumption_rehearsal import (
    run_activation_consumption_local_rehearsal,
)
from quant.workflows.semantic_target_activation import (
    SEMANTIC_TARGET_ORCHESTRATION_POLICY,
    rehearsal_report_sha256,
    write_semantic_target_activation_authorization,
)
from quant.workflows.semantic_target_rehearsal import (
    SEMANTIC_TARGET_REHEARSAL_POLICY,
)


@dataclass(frozen=True)
class MomentumSemanticPaperCanaryRequestBundle:
    """Paths and decision summary for one generated canary request."""

    request_path: Path
    output_root: Path
    activation_rehearsal_report_path: Path
    base_rehearsal_report_path: Path
    authorization_path: Path
    contributor_set_path: Path
    strategy_decision_path: Path
    strategy_evaluation_path: Path
    signal_action: PaperSignalAction
    signal_date: str
    reference_price: float
    target_quantity: int


def prepare_momentum_semantic_paper_canary_request(
    *,
    request_id: str,
    data_path: Path,
    symbol: str,
    quantity: int,
    current_position: int,
    initial_cash: float,
    output_root: Path,
    evaluated_at: datetime | None = None,
    current_average_price: float | None = None,
    fast_window: int = 5,
    slow_window: int = 20,
    min_rows: int = 1,
    max_absolute_target: Decimal = Decimal("100"),
    valid_for_seconds: int = 3600,
) -> MomentumSemanticPaperCanaryRequestBundle:
    """Translate latest legacy momentum signal into a reviewed paper request."""
    _require_safe_component(request_id)
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    if initial_cash < 0:
        raise ValueError("initial_cash must be non-negative")
    if valid_for_seconds <= 0:
        raise ValueError("valid_for_seconds must be positive")

    report = validate_market_bars_csv(data_path, symbol, min_rows=min_rows)
    if not report.passed:
        raise ValueError(f"market bars validation failed for {symbol}")

    current_time = evaluated_at or datetime.now(UTC)
    prices = load_price_csv(data_path, symbol)
    strategy = MomentumStrategy(
        MomentumConfig(fast_window=fast_window, slow_window=slow_window)
    )
    signal = decide_latest_signal(
        strategy_name=strategy.name,
        prices=prices,
        signals=strategy.generate_signals(prices),
    )
    target_quantity = _target_from_signal(
        signal.action,
        quantity=quantity,
        current_position=current_position,
    )
    reference_price = signal.market_price
    average_price = (
        reference_price
        if current_average_price is None
        else current_average_price
    )
    initial_positions = _initial_positions(
        symbol=symbol,
        quantity=current_position,
        average_price=average_price,
        last_price=reference_price,
    )

    inputs_root = output_root / "inputs"
    activation_rehearsal_root = inputs_root / "activation-rehearsal"
    activation_rehearsal = run_activation_consumption_local_rehearsal(
        rehearsal_id=f"{request_id}-activation-rehearsal",
        output_root=activation_rehearsal_root,
        evaluated_at=current_time,
    )
    activation_rehearsal_report_path = (
        activation_rehearsal_root
        / "reports"
        / f"{activation_rehearsal.rehearsal_id}.json"
    )
    base_rehearsal_report_path = Path(
        activation_rehearsal.base_rehearsal_report_path
    )
    authorization = SemanticTargetActivationAuthorization(
        authorization_id=f"{request_id}-authorization",
        revision=1,
        allowed_scopes=(SemanticTargetActivationScope.SEMANTIC_PAPER,),
        orchestration_policy_version=SEMANTIC_TARGET_ORCHESTRATION_POLICY,
        rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
        rehearsal_id=activation_rehearsal.base_rehearsal_id,
        rehearsal_report_sha256=rehearsal_report_sha256(
            base_rehearsal_report_path
        ),
        issued_at=current_time,
        effective_at=current_time,
        valid_until=current_time + timedelta(seconds=valid_for_seconds),
        issued_by="local-canary-generator",
        reason="translated legacy momentum local semantic-paper canary",
        evidence_refs=(str(data_path),),
    )
    authorization_path = write_semantic_target_activation_authorization(
        authorization, inputs_root / "authorizations"
    )
    contributor_set = ContributorSet(
        contributor_set_id=f"{request_id}-contributors",
        revision=1,
        symbol=symbol,
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=valid_for_seconds,
        portfolio_policy_version="sum_active_targets_v1",
        reason="single translated legacy momentum canary contributor",
    )
    contributor_set_path = write_contributor_set(
        contributor_set, inputs_root / "contributor-sets"
    )
    decision = StrategyTargetDecision(
        decision_id=f"{request_id}-target-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol=symbol,
        unit=TargetUnit.SHARES,
        target_value=Decimal(target_quantity),
        sizing_policy_version="legacy_momentum_canary_v1",
        input_data_id=f"{data_path.name}:{_file_sha256(data_path)}",
        generated_at=current_time,
        effective_at=current_time,
        valid_until=current_time + timedelta(seconds=valid_for_seconds),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason=(
            f"translated latest legacy momentum {signal.action.value} signal "
            f"from {signal.signal_date}"
        ),
        evidence_refs=(signal.idempotency_key,),
    )
    strategy_decision_path = write_strategy_target_decision(
        decision, inputs_root / "strategy-targets"
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"{request_id}-strategy-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=current_time,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="canary evaluation references translated momentum target",
        evidence_refs=(signal.idempotency_key,),
    )
    strategy_evaluation_path = write_strategy_evaluation(
        evaluation, inputs_root / "strategy-evaluations"
    )
    request = ActivatedSemanticPaperOperatorRequest(
        request_id=request_id,
        activation_evaluation_id=f"{request_id}-activation-evaluation",
        orchestration_id=f"{request_id}-orchestration",
        authorization_path=str(authorization_path),
        rehearsal_report_path=str(base_rehearsal_report_path),
        activation_consumption_rehearsal_report_path=str(
            activation_rehearsal_report_path
        ),
        contributor_set_path=str(contributor_set_path),
        strategy_decision_paths=(str(strategy_decision_path),),
        strategy_evaluation_paths=(str(strategy_evaluation_path),),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=max_absolute_target,
        ),
        portfolio_target_id=f"{request_id}-portfolio-target",
        portfolio_target_revision=1,
        risk_target_id=f"{request_id}-risk-target",
        risk_target_revision=1,
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=reference_price,
        initial_cash=initial_cash,
        initial_positions=initial_positions,
        evaluated_at=current_time,
        evidence_refs=("prepared:legacy-momentum-canary",),
    )
    request_path = write_activated_semantic_paper_operator_request(
        request, inputs_root / "requests"
    )
    return MomentumSemanticPaperCanaryRequestBundle(
        request_path=request_path,
        output_root=output_root,
        activation_rehearsal_report_path=activation_rehearsal_report_path,
        base_rehearsal_report_path=base_rehearsal_report_path,
        authorization_path=authorization_path,
        contributor_set_path=contributor_set_path,
        strategy_decision_path=strategy_decision_path,
        strategy_evaluation_path=strategy_evaluation_path,
        signal_action=signal.action,
        signal_date=signal.signal_date,
        reference_price=reference_price,
        target_quantity=target_quantity,
    )


def _target_from_signal(
    action: PaperSignalAction,
    *,
    quantity: int,
    current_position: int,
) -> int:
    if action == PaperSignalAction.BUY:
        return quantity
    if action == PaperSignalAction.SELL:
        return 0
    return current_position


def _initial_positions(
    *,
    symbol: str,
    quantity: int,
    average_price: float,
    last_price: float,
) -> tuple[Position, ...]:
    if quantity == 0:
        return ()
    return (
        Position(
            symbol=symbol,
            quantity=quantity,
            average_price=average_price,
            last_price=last_price,
        ),
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_safe_component(value: str) -> None:
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("request_id must be a safe path component")
