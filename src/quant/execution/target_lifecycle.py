from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from quant.execution.lifecycle_artifacts import (
    append_execution_event,
    claim_execution_plan_exclusive,
    current_execution_status,
    load_execution_events,
    write_broker_lookup_evidence,
    write_execution_drift_observation,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveOrderRecord,
    LiveOrderStatus,
    LiveReconciliationReport,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    BrokerLookupOutcome,
    BrokerOrderLookupEvidence,
    ExecutionDriftObservation,
    ExecutionDriftStatus,
    ExecutionLifecyclePolicy,
    ExecutionPlan,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    PortfolioTargetDecision,
    PortfolioTargetStatus,
    ResearchRiskPolicy,
    RiskTargetDecision,
    RiskTargetStatus,
    StrategyTargetDecision,
    TargetUnit,
)
from quant.research.portfolio_targets import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)

SINGLE_MARKET_ORDER_POLICY = "single_market_order_v1"
ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY = "account_wide_exact_v1"
DETECT_ONLY_DRIFT_POLICY = "detect_only_v1"


class ExecutionLifecycleBroker(Protocol):
    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord: ...

    def account_snapshot(self) -> LiveAccountSnapshot: ...

    def has_open_orders(self) -> bool: ...

    def orders_by_client_order_id(
        self, client_order_id: str
    ) -> tuple[LiveOrderRecord, ...]: ...


class ExecutionLifecycleStateReader(Protocol):
    def account_snapshot(self) -> LiveAccountSnapshot: ...

    def has_open_orders(self) -> bool: ...


def claim_execution_plan(
    *,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    account: LiveAccountSnapshot,
    policy: ExecutionLifecyclePolicy,
    artifact_root: Path,
    created_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> ExecutionPlan:
    """Atomically claim the only automatic plan for one risk-target revision."""
    target_quantity = _approved_whole_share_target(risk_target)
    if portfolio_target.status != PortfolioTargetStatus.AGGREGATED:
        raise ValueError("portfolio target must be aggregated")
    if risk_target.portfolio_target_id != portfolio_target.portfolio_target_id:
        raise ValueError("risk target references another portfolio target")
    if risk_target.approved_target_value != portfolio_target.aggregate_value:
        raise ValueError("risk target must approve the exact aggregate")
    if (
        risk_target.symbol != portfolio_target.symbol
        or risk_target.symbol != contributor_set.symbol
        or risk_target.unit != portfolio_target.unit
        or risk_target.unit != contributor_set.unit
    ):
        raise ValueError("target symbol and unit identities must agree")
    if (
        portfolio_target.contributor_set_id
        != contributor_set.contributor_set_id
        or portfolio_target.contributor_set_revision != contributor_set.revision
    ):
        raise ValueError("portfolio target references another contributor set")
    _require_lifecycle_policy(policy)

    current_quantity = _position_quantity(account, risk_target.symbol)
    delta = target_quantity - current_quantity
    order_request = (
        None
        if delta == 0
        else OrderRequest(
            symbol=risk_target.symbol,
            side=OrderSide.BUY if delta > 0 else OrderSide.SELL,
            quantity=abs(delta),
        )
    )
    plan = ExecutionPlan(
        execution_plan_id=(
            f"execution-{risk_target.risk_target_id}-r{risk_target.revision}"
        ),
        risk_target_id=risk_target.risk_target_id,
        risk_target_revision=risk_target.revision,
        portfolio_target_id=portfolio_target.portfolio_target_id,
        contributor_set_id=contributor_set.contributor_set_id,
        contributor_set_revision=contributor_set.revision,
        source_strategy_decision_ids=(
            portfolio_target.contributing_decision_ids
        ),
        account_snapshot_id=account.id,
        broker_name=account.broker_name,
        account_id=account.account_id,
        broker_environment=account.broker_environment,
        symbol=risk_target.symbol,
        current_quantity=current_quantity,
        target_quantity=target_quantity,
        order_request=order_request,
        client_order_id=(
            f"target-{risk_target.risk_target_id}-r{risk_target.revision}"
        ),
        execution_policy_version=policy.execution_policy_version,
        reconciliation_policy_version=policy.reconciliation_policy_version,
        drift_policy_version=policy.drift_policy_version,
        created_at=created_at,
        reason=(
            "approved risk-target revision claimed for fake-broker lifecycle"
        ),
        evidence_refs=evidence_refs,
    )
    claim_execution_plan_exclusive(plan, artifact_root)
    return plan


def submit_execution_plan(
    *,
    plan: ExecutionPlan,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    broker: ExecutionLifecycleBroker,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    artifact_root: Path,
    evaluated_at: datetime,
    expected_trading_mode: TradingMode = TradingMode.LIVE,
    final_pre_submit_check: Callable[[], tuple[str, ...]] | None = None,
) -> ExecutionPlanStatus:
    """Revalidate and submit once, recording uncertainty instead of retrying."""
    if (
        current_execution_status(plan, artifact_root)
        != ExecutionPlanStatus.PLANNED
    ):
        raise ValueError("only a planned execution may be submitted")
    reasons = validate_pre_submission(
        plan=plan,
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        risk_policy=risk_policy,
        broker=broker,
        reference_price=reference_price,
        safety_check=safety_check,
        evaluated_at=evaluated_at,
        expected_trading_mode=expected_trading_mode,
    )
    if not reasons and final_pre_submit_check is not None:
        try:
            reasons = final_pre_submit_check()
        except Exception as exc:
            reasons = (f"final pre-submit check failed: {exc}",)
    if reasons:
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=ExecutionPlanStatus.BLOCKED,
            occurred_at=evaluated_at,
            reason="; ".join(reasons),
        )
        return ExecutionPlanStatus.BLOCKED
    if plan.order_request is None:
        return ExecutionPlanStatus.PLANNED

    append_execution_event(
        plan=plan,
        artifact_root=artifact_root,
        new_status=ExecutionPlanStatus.SUBMISSION_PENDING,
        occurred_at=evaluated_at,
        reason="durable submission intent recorded before broker interaction",
    )
    try:
        order = broker.submit_market_order(
            plan.order_request,
            reference_price=reference_price,
            client_order_id=plan.client_order_id,
            safety_check=safety_check,
        )
    except Exception as exc:
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=ExecutionPlanStatus.AMBIGUOUS,
            occurred_at=evaluated_at,
            reason=f"broker submission outcome is ambiguous: {exc}",
        )
        return ExecutionPlanStatus.AMBIGUOUS

    mismatch = _order_identity_mismatch(plan, order)
    if mismatch is not None:
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=ExecutionPlanStatus.AMBIGUOUS,
            occurred_at=evaluated_at,
            reason=f"broker submission response identity mismatch: {mismatch}",
            evidence_refs=(order.id,),
        )
        return ExecutionPlanStatus.AMBIGUOUS
    append_execution_event(
        plan=plan,
        artifact_root=artifact_root,
        new_status=ExecutionPlanStatus.SUBMITTED,
        occurred_at=evaluated_at,
        reason="broker order recovered from submission response",
        evidence_refs=(order.id,),
        broker_order_ids=(_broker_order_key(order),),
    )
    return _record_terminal_order_status(
        plan=plan,
        order=order,
        artifact_root=artifact_root,
        occurred_at=evaluated_at,
    )


def recover_execution_submission(
    *,
    plan: ExecutionPlan,
    broker: ExecutionLifecycleBroker,
    artifact_root: Path,
    evaluated_at: datetime,
) -> BrokerOrderLookupEvidence:
    """Recover a pending or ambiguous submission without resubmitting."""
    current = current_execution_status(plan, artifact_root)
    if current not in {
        ExecutionPlanStatus.SUBMISSION_PENDING,
        ExecutionPlanStatus.AMBIGUOUS,
    }:
        raise ValueError("only pending or ambiguous submissions can recover")
    evidence, found_order = _lookup_plan_order(
        plan=plan,
        broker=broker,
        evaluated_at=evaluated_at,
    )

    evidence_path = write_broker_lookup_evidence(evidence, artifact_root)
    refs = (str(evidence_path),)
    if evidence.outcome != BrokerLookupOutcome.FOUND:
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=ExecutionPlanStatus.BLOCKED,
            occurred_at=evaluated_at,
            reason=(
                f"submission recovery blocked: {evidence.outcome.value}; "
                "automatic resubmission is prohibited"
            ),
            evidence_refs=refs,
        )
        return evidence

    if found_order is None:
        raise ValueError("found lookup evidence is missing its broker order")
    append_execution_event(
        plan=plan,
        artifact_root=artifact_root,
        new_status=ExecutionPlanStatus.SUBMITTED,
        occurred_at=evaluated_at,
        reason="submission state recovered from broker lookup",
        evidence_refs=refs + (found_order.id,),
        broker_order_ids=(_broker_order_key(found_order),),
    )
    _record_terminal_order_status(
        plan=plan,
        order=found_order,
        artifact_root=artifact_root,
        occurred_at=evaluated_at,
    )
    return evidence


def refresh_submitted_execution(
    *,
    plan: ExecutionPlan,
    broker: ExecutionLifecycleBroker,
    artifact_root: Path,
    evaluated_at: datetime,
) -> BrokerOrderLookupEvidence:
    """Refresh a submitted order without creating or resubmitting an order."""
    if (
        current_execution_status(plan, artifact_root)
        != ExecutionPlanStatus.SUBMITTED
    ):
        raise ValueError("only submitted executions can be refreshed")
    expected_broker_order_id = _submitted_broker_order_id(plan, artifact_root)
    evidence, found_order = _lookup_plan_order(
        plan=plan,
        broker=broker,
        evaluated_at=evaluated_at,
        expected_broker_order_id=expected_broker_order_id,
    )
    evidence_path = write_broker_lookup_evidence(evidence, artifact_root)
    refs = (str(evidence_path),)
    if found_order is None:
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=ExecutionPlanStatus.AMBIGUOUS,
            occurred_at=evaluated_at,
            reason=(
                f"submitted-order refresh is ambiguous: "
                f"{evidence.outcome.value}"
            ),
            evidence_refs=refs,
        )
        return evidence

    _record_terminal_order_status(
        plan=plan,
        order=found_order,
        artifact_root=artifact_root,
        occurred_at=evaluated_at,
    )
    return evidence


def validate_pre_submission(
    *,
    plan: ExecutionPlan,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    broker: ExecutionLifecycleStateReader,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    evaluated_at: datetime,
    expected_trading_mode: TradingMode = TradingMode.LIVE,
) -> tuple[str, ...]:
    reasons: list[str] = []
    try:
        _require_plan_policy(plan)
        target_quantity = _approved_whole_share_target(risk_target)
    except ValueError as exc:
        reasons.append(str(exc))
        return tuple(reasons)
    if (
        plan.risk_target_id != risk_target.risk_target_id
        or plan.risk_target_revision != risk_target.revision
    ):
        reasons.append("plan references another risk-target revision")
    if plan.portfolio_target_id != portfolio_target.portfolio_target_id:
        reasons.append("plan references another portfolio target")
    if risk_target.portfolio_target_id != portfolio_target.portfolio_target_id:
        reasons.append("risk target references another portfolio target")
    if (
        risk_target.symbol != plan.symbol
        or risk_target.symbol != portfolio_target.symbol
        or risk_target.symbol != contributor_set.symbol
        or risk_target.unit != portfolio_target.unit
        or risk_target.unit != contributor_set.unit
    ):
        reasons.append("target symbol and unit identities changed")
    if (
        plan.contributor_set_id != contributor_set.contributor_set_id
        or plan.contributor_set_revision != contributor_set.revision
    ):
        reasons.append("plan references another contributor-set revision")
    if (
        portfolio_target.contributor_set_id
        != contributor_set.contributor_set_id
        or portfolio_target.contributor_set_revision != contributor_set.revision
    ):
        reasons.append("portfolio target references another contributor set")
    if portfolio_target.status != PortfolioTargetStatus.AGGREGATED:
        reasons.append("portfolio target is not aggregated")
    if reference_price <= 0:
        reasons.append("reference price must be positive")
    if not safety_check.allowed or safety_check.mode != expected_trading_mode:
        reasons.append(
            f"{expected_trading_mode.value} safety check is not allowed"
        )
    if broker.has_open_orders():
        reasons.append("broker has unsettled working orders")
    account = broker.account_snapshot()
    if not _account_matches_plan(plan, account):
        reasons.append("broker account identity changed after plan creation")
    if _position_quantity(account, plan.symbol) != plan.current_quantity:
        reasons.append("broker position changed after plan creation")
    if plan.target_quantity != target_quantity:
        reasons.append("approved target changed after plan creation")

    try:
        recomputed_portfolio = aggregate_strategy_targets(
            portfolio_target_id="pre-submission-validation",
            revision=1,
            contributor_set=contributor_set,
            decisions=strategy_decisions,
            evaluated_at=evaluated_at,
        )
    except ValueError as exc:
        reasons.append(f"portfolio revalidation failed: {exc}")
        return tuple(reasons)
    if (
        recomputed_portfolio.status != PortfolioTargetStatus.AGGREGATED
        or recomputed_portfolio.aggregate_value
        != portfolio_target.aggregate_value
        or recomputed_portfolio.contributing_decision_ids
        != plan.source_strategy_decision_ids
    ):
        reasons.append("strategy or portfolio target revalidation changed")
    try:
        recomputed_risk = evaluate_research_risk_target(
            risk_target_id="pre-submission-validation",
            revision=1,
            portfolio_target=recomputed_portfolio,
            policy=risk_policy,
            evaluated_at=evaluated_at,
        )
    except ValueError as exc:
        reasons.append(f"risk revalidation failed: {exc}")
        return tuple(reasons)
    if (
        recomputed_risk.status != RiskTargetStatus.APPROVED
        or recomputed_risk.approved_target_value
        != risk_target.approved_target_value
        or recomputed_risk.risk_policy_version
        != risk_target.risk_policy_version
    ):
        reasons.append("risk-target approval revalidation changed")
    return tuple(reasons)


def confirm_execution_satisfaction(
    *,
    plan: ExecutionPlan,
    broker: ExecutionLifecycleBroker,
    reconciliation: LiveReconciliationReport,
    artifact_root: Path,
    evaluated_at: datetime,
) -> ExecutionPlanStatus:
    """Mark satisfaction only after exact broker and reconciliation evidence."""
    current = current_execution_status(plan, artifact_root)
    eligible = current == ExecutionPlanStatus.FILLED or (
        current == ExecutionPlanStatus.PLANNED and plan.order_request is None
    )
    if not eligible:
        raise ValueError("execution is not eligible for satisfaction")
    reasons: list[str] = []
    if plan.reconciliation_policy_version != (
        ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
    ):
        reasons.append("unsupported reconciliation policy version")
    if not reconciliation.passed:
        reasons.append("account-wide reconciliation failed")
    evidence_not_before = plan.created_at
    if current == ExecutionPlanStatus.FILLED:
        filled_events = tuple(
            event
            for event in load_execution_events(
                artifact_root, plan.execution_plan_id
            )
            if event.new_status == ExecutionPlanStatus.FILLED
        )
        evidence_not_before = filled_events[-1].occurred_at
    if reconciliation.created_at < evidence_not_before:
        reasons.append("account-wide reconciliation predates execution state")
    if broker.has_open_orders():
        reasons.append("broker has unsettled working orders")
    snapshot = broker.account_snapshot()
    if not _account_matches_plan(plan, snapshot):
        reasons.append("broker account identity differs from execution plan")
    if (
        reconciliation.broker_name != snapshot.broker_name
        or reconciliation.account_id != snapshot.account_id
        or reconciliation.broker_environment != snapshot.broker_environment
    ):
        reasons.append("reconciliation evidence belongs to another account")
    if _position_quantity(snapshot, plan.symbol) != plan.target_quantity:
        reasons.append("broker position does not equal approved target")
    if reasons:
        if current == ExecutionPlanStatus.FILLED:
            append_execution_event(
                plan=plan,
                artifact_root=artifact_root,
                new_status=ExecutionPlanStatus.FILLED,
                occurred_at=evaluated_at,
                reason="satisfaction blocked: " + "; ".join(reasons),
                evidence_refs=(reconciliation.id,),
            )
            return ExecutionPlanStatus.FILLED
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=ExecutionPlanStatus.BLOCKED,
            occurred_at=evaluated_at,
            reason="satisfaction blocked: " + "; ".join(reasons),
            evidence_refs=(reconciliation.id,),
        )
        return ExecutionPlanStatus.BLOCKED

    append_execution_event(
        plan=plan,
        artifact_root=artifact_root,
        new_status=ExecutionPlanStatus.SATISFIED,
        occurred_at=evaluated_at,
        reason="approved target satisfied after account-wide reconciliation",
        evidence_refs=(reconciliation.id,),
    )
    return ExecutionPlanStatus.SATISFIED


def observe_execution_drift(
    *,
    plan: ExecutionPlan,
    broker: ExecutionLifecycleBroker,
    artifact_root: Path,
    observed_at: datetime,
) -> ExecutionDriftObservation:
    """Persist detect-only drift evidence without changing broker state."""
    if (
        current_execution_status(plan, artifact_root)
        != ExecutionPlanStatus.SATISFIED
    ):
        raise ValueError("drift observation requires a satisfied execution")
    if plan.drift_policy_version != DETECT_ONLY_DRIFT_POLICY:
        raise ValueError("unsupported drift policy version")
    snapshot = broker.account_snapshot()
    broker_quantity = _position_quantity(snapshot, plan.symbol)
    if not _account_matches_plan(plan, snapshot):
        status = ExecutionDriftStatus.INDETERMINATE
        reason = "broker account identity differs from execution plan"
    elif snapshot.open_order_ids:
        status = ExecutionDriftStatus.INDETERMINATE
        reason = "working orders prevent reliable drift classification"
    elif broker_quantity != plan.target_quantity:
        status = ExecutionDriftStatus.DETECTED
        reason = "broker position diverged from satisfied approved target"
    else:
        status = ExecutionDriftStatus.CLEAR
        reason = "broker position still equals satisfied approved target"
    observation = ExecutionDriftObservation(
        observation_id=f"{plan.execution_plan_id}:{observed_at.isoformat()}",
        execution_plan_id=plan.execution_plan_id,
        drift_policy_version=plan.drift_policy_version,
        symbol=plan.symbol,
        broker_name=snapshot.broker_name,
        account_id=snapshot.account_id,
        broker_environment=snapshot.broker_environment,
        approved_target_quantity=plan.target_quantity,
        broker_position_quantity=broker_quantity,
        open_order_ids=snapshot.open_order_ids,
        status=status,
        observed_at=observed_at,
        reason=reason,
    )
    write_execution_drift_observation(observation, artifact_root)
    return observation


def _record_terminal_order_status(
    *,
    plan: ExecutionPlan,
    order: LiveOrderRecord,
    artifact_root: Path,
    occurred_at: datetime,
) -> ExecutionPlanStatus:
    status_map = {
        LiveOrderStatus.FILLED: ExecutionPlanStatus.FILLED,
        LiveOrderStatus.REJECTED: ExecutionPlanStatus.REJECTED,
        LiveOrderStatus.CANCELLED: ExecutionPlanStatus.CANCELLED,
        LiveOrderStatus.UNKNOWN: ExecutionPlanStatus.AMBIGUOUS,
    }
    lifecycle_status = status_map.get(
        order.status, ExecutionPlanStatus.SUBMITTED
    )
    if lifecycle_status != ExecutionPlanStatus.SUBMITTED:
        append_execution_event(
            plan=plan,
            artifact_root=artifact_root,
            new_status=lifecycle_status,
            occurred_at=occurred_at,
            reason=f"broker order status is {order.status.value}",
            evidence_refs=(order.id,),
            broker_order_ids=(_broker_order_key(order),),
        )
    return lifecycle_status


def _order_identity_mismatch(
    plan: ExecutionPlan,
    order: LiveOrderRecord,
) -> str | None:
    if order.client_order_id != plan.client_order_id:
        return "client order ID differs"
    if plan.order_request is None or order.request != plan.order_request:
        return "order request differs"
    if (
        order.broker_name != plan.broker_name
        or order.account_id != plan.account_id
        or order.broker_environment != plan.broker_environment
    ):
        return "broker account identity differs"
    return None


def _account_matches_plan(
    plan: ExecutionPlan,
    account: LiveAccountSnapshot,
) -> bool:
    return (
        account.broker_name == plan.broker_name
        and account.account_id == plan.account_id
        and account.broker_environment == plan.broker_environment
    )


def _lookup_evidence(
    *,
    plan: ExecutionPlan,
    outcome: BrokerLookupOutcome,
    orders: tuple[LiveOrderRecord, ...],
    evaluated_at: datetime,
    reason: str,
    order_identity_results: tuple[str, ...] | None = None,
) -> BrokerOrderLookupEvidence:
    return BrokerOrderLookupEvidence(
        evidence_id=f"{plan.execution_plan_id}:{evaluated_at.isoformat()}",
        execution_plan_id=plan.execution_plan_id,
        client_order_id=plan.client_order_id,
        outcome=outcome,
        order_record_ids=tuple(order.id for order in orders),
        broker_order_ids=tuple(
            order.broker_order_id or order.client_order_id for order in orders
        ),
        order_statuses=tuple(order.status for order in orders),
        order_identity_results=order_identity_results
        if order_identity_results is not None
        else tuple(_order_identity_result(plan, order) for order in orders),
        occurred_at=evaluated_at,
        reason=reason,
    )


def _lookup_plan_order(
    *,
    plan: ExecutionPlan,
    broker: ExecutionLifecycleBroker,
    evaluated_at: datetime,
    expected_broker_order_id: str | None = None,
) -> tuple[BrokerOrderLookupEvidence, LiveOrderRecord | None]:
    try:
        orders = broker.orders_by_client_order_id(plan.client_order_id)
    except Exception as exc:
        return (
            _lookup_evidence(
                plan=plan,
                outcome=BrokerLookupOutcome.UNAVAILABLE,
                orders=(),
                evaluated_at=evaluated_at,
                reason=f"broker lookup unavailable: {exc}",
            ),
            None,
        )
    identity_results = tuple(
        _order_identity_result(plan, order, expected_broker_order_id)
        for order in orders
    )
    if len(orders) == 1 and identity_results == ("match",):
        outcome = BrokerLookupOutcome.FOUND
        reason = "broker order found by deterministic client order ID"
        found_order = orders[0]
    elif not orders:
        outcome = BrokerLookupOutcome.NOT_FOUND
        reason = "broker lookup proved no visible matching order"
        found_order = None
    else:
        outcome = BrokerLookupOutcome.CONFLICTING
        reason = "broker lookup returned conflicting matching orders"
        found_order = None
    return (
        _lookup_evidence(
            plan=plan,
            outcome=outcome,
            orders=orders,
            evaluated_at=evaluated_at,
            reason=reason,
            order_identity_results=identity_results,
        ),
        found_order,
    )


def _submitted_broker_order_id(
    plan: ExecutionPlan,
    artifact_root: Path,
) -> str:
    submitted_events = tuple(
        event
        for event in load_execution_events(
            artifact_root, plan.execution_plan_id
        )
        if event.new_status == ExecutionPlanStatus.SUBMITTED
    )
    if not submitted_events or len(submitted_events[-1].broker_order_ids) != 1:
        raise ValueError("submitted execution lacks one broker order identity")
    return submitted_events[-1].broker_order_ids[0]


def _broker_order_key(order: LiveOrderRecord) -> str:
    return order.broker_order_id or order.client_order_id


def _order_identity_result(
    plan: ExecutionPlan,
    order: LiveOrderRecord,
    expected_broker_order_id: str | None = None,
) -> str:
    mismatch = _order_identity_mismatch(plan, order)
    if mismatch is not None:
        return mismatch
    if (
        expected_broker_order_id is not None
        and _broker_order_key(order) != expected_broker_order_id
    ):
        return "broker order ID differs"
    return "match"


def _approved_whole_share_target(risk_target: RiskTargetDecision) -> int:
    if risk_target.status != RiskTargetStatus.APPROVED:
        raise ValueError("risk target is not approved")
    if risk_target.unit != TargetUnit.SHARES:
        raise ValueError("operational execution requires share targets")
    value = risk_target.approved_target_value
    if value is None:
        raise ValueError("approved risk target has no value")
    if value != value.to_integral_value():
        raise ValueError("operational execution rejects fractional shares")
    return int(value)


def _position_quantity(account: LiveAccountSnapshot, symbol: str) -> int:
    return next(
        (
            position.quantity
            for position in account.positions
            if position.symbol == symbol
        ),
        0,
    )


def _require_lifecycle_policy(policy: ExecutionLifecyclePolicy) -> None:
    if policy.execution_policy_version != SINGLE_MARKET_ORDER_POLICY:
        raise ValueError("unsupported execution policy version")
    if policy.reconciliation_policy_version != (
        ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
    ):
        raise ValueError("unsupported reconciliation policy version")
    if policy.drift_policy_version != DETECT_ONLY_DRIFT_POLICY:
        raise ValueError("unsupported drift policy version")


def _require_plan_policy(plan: ExecutionPlan) -> None:
    _require_lifecycle_policy(
        ExecutionLifecyclePolicy(
            execution_policy_version=plan.execution_policy_version,
            reconciliation_policy_version=plan.reconciliation_policy_version,
            drift_policy_version=plan.drift_policy_version,
        )
    )
