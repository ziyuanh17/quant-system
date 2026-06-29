"""Execute semantic targets through the gated Alpaca paper API."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from quant.execution.artifacts import write_live_reconciliation_report
from quant.execution.lifecycle_artifacts import (
    current_execution_status,
    execution_plan_path,
    load_execution_plan,
)
from quant.execution.live_broker import LiveBrokerAdapter, LiveBrokerClient
from quant.execution.reconciliation import (
    load_live_order_records,
    reconcile_live_state,
)
from quant.execution.risk import (
    check_projected_order_risk,
    check_short_sale_availability,
)
from quant.execution.safety import evaluate_trading_safety
from quant.execution.target_lifecycle import (
    claim_execution_plan,
    confirm_execution_satisfaction,
    recover_execution_submission,
    refresh_submitted_execution,
    submit_execution_plan,
    target_transition_crosses_zero,
)
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    LiveReconciliationReport,
    TradingMode,
    TradingSafetyCheck,
    TradingSafetyConfig,
)
from quant.models.execution_lifecycle import (
    ExecutionLifecyclePolicy,
    ExecutionPlan,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    PortfolioTargetDecision,
    ResearchRiskPolicy,
    RiskTargetDecision,
    StrategyTargetDecision,
)
from quant.operations import FileLock


@dataclass(frozen=True)
class AlpacaSemanticTargetRunResult:
    plan: ExecutionPlan
    status: ExecutionPlanStatus
    reconciliation: LiveReconciliationReport | None


def run_alpaca_semantic_target_paper(
    *,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_config: TradingSafetyConfig,
    broker_client: LiveBrokerClient,
    artifact_root: Path,
    order_output_dir: Path,
    fill_output_dir: Path,
    snapshot_output_dir: Path,
    reconciliation_output_dir: Path,
    evaluated_at: datetime,
    alpaca_submission_enabled: bool = False,
    evidence_refs: tuple[str, ...] = (),
) -> AlpacaSemanticTargetRunResult:
    """Run one approved semantic target through Alpaca paper, when enabled."""
    if not alpaca_submission_enabled:
        raise ValueError("Alpaca semantic-target submission is not enabled")
    safety_check = evaluate_trading_safety(safety_config)
    if (
        not safety_check.allowed
        or safety_check.mode != TradingMode.LIVE
        or safety_config.broker_name != "alpaca-paper"
    ):
        raise ValueError(
            "Alpaca semantic-target workflow requires an allowed live-shaped "
            "alpaca-paper safety configuration"
        )

    adapter = LiveBrokerAdapter(
        client=broker_client,
        order_output_dir=order_output_dir,
        fill_output_dir=fill_output_dir,
        snapshot_output_dir=snapshot_output_dir,
    )
    account = adapter.account_snapshot()
    try:
        plan = claim_execution_plan(
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            account=account,
            policy=policy,
            artifact_root=artifact_root,
            created_at=evaluated_at,
            evidence_refs=evidence_refs,
        )
    except FileExistsError:
        plan = load_execution_plan(
            execution_plan_path(
                artifact_root,
                risk_target.risk_target_id,
                risk_target.revision,
            )
        )

    with FileLock(
        path=artifact_root
        / "locks"
        / f"{plan.execution_plan_id}-alpaca-paper.lock",
        lock_name=f"alpaca-semantic-paper:{plan.execution_plan_id}",
        stale_after_seconds=300,
    ):
        status = current_execution_status(plan, artifact_root)
        if status == ExecutionPlanStatus.PLANNED:
            status = submit_execution_plan(
                plan=plan,
                risk_target=risk_target,
                portfolio_target=portfolio_target,
                contributor_set=contributor_set,
                strategy_decisions=strategy_decisions,
                risk_policy=risk_policy,
                broker=adapter,
                reference_price=reference_price,
                safety_check=safety_check,
                artifact_root=artifact_root,
                evaluated_at=evaluated_at,
                final_pre_submit_check=lambda: _operational_risk_reasons(
                    plan=plan,
                    broker_client=broker_client,
                    reference_price=reference_price,
                    safety_config=safety_config,
                ),
            )
        elif status in {
            ExecutionPlanStatus.SUBMISSION_PENDING,
            ExecutionPlanStatus.AMBIGUOUS,
        }:
            _remember_plan_context(
                plan=plan,
                broker_client=broker_client,
                order_output_dir=order_output_dir,
                reference_price=reference_price,
                safety_check=safety_check,
            )
            recover_execution_submission(
                plan=plan,
                broker=adapter,
                artifact_root=artifact_root,
                evaluated_at=evaluated_at,
            )
            status = current_execution_status(plan, artifact_root)
        elif status == ExecutionPlanStatus.SUBMITTED:
            _remember_plan_context(
                plan=plan,
                broker_client=broker_client,
                order_output_dir=order_output_dir,
                reference_price=reference_price,
                safety_check=safety_check,
            )
            refresh_submitted_execution(
                plan=plan,
                broker=adapter,
                artifact_root=artifact_root,
                evaluated_at=evaluated_at,
            )
            status = current_execution_status(plan, artifact_root)

        if status in {
            ExecutionPlanStatus.BLOCKED,
            ExecutionPlanStatus.REJECTED,
            ExecutionPlanStatus.CANCELLED,
            ExecutionPlanStatus.AMBIGUOUS,
            ExecutionPlanStatus.SUBMITTED,
        }:
            return AlpacaSemanticTargetRunResult(plan, status, None)
        if status == ExecutionPlanStatus.SATISFIED:
            return AlpacaSemanticTargetRunResult(plan, status, None)
        if status not in {
            ExecutionPlanStatus.FILLED,
            ExecutionPlanStatus.PLANNED,
        }:
            return AlpacaSemanticTargetRunResult(plan, status, None)

        _materialize_order_evidence(
            plan=plan,
            broker_client=broker_client,
            adapter=adapter,
            order_output_dir=order_output_dir,
            reference_price=reference_price,
            safety_check=safety_check,
        )
        adapter.account_snapshot()
        reconciliation = reconcile_live_state(
            client=broker_client,
            order_records_dir=order_output_dir,
            fill_records_dir=fill_output_dir,
            snapshot_records_dir=snapshot_output_dir,
        )
        write_live_reconciliation_report(
            reconciliation,
            reconciliation_output_dir
            / plan.execution_plan_id
            / f"{reconciliation.id}.json",
        )
        status = confirm_execution_satisfaction(
            plan=plan,
            broker=adapter,
            reconciliation=reconciliation,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
        )
        return AlpacaSemanticTargetRunResult(plan, status, reconciliation)


def _operational_risk_reasons(
    *,
    plan: ExecutionPlan,
    broker_client: LiveBrokerClient,
    reference_price: float,
    safety_config: TradingSafetyConfig,
) -> tuple[str, ...]:
    request = plan.order_request
    if request is None:
        return ()
    reasons: list[str] = []
    if target_transition_crosses_zero(
        plan.current_quantity,
        plan.target_quantity,
    ):
        reasons.append(
            "cross-zero reversal requires explicit close/open execution plan"
        )
        return tuple(reasons)
    if (
        safety_config.max_order_notional is not None
        and request.quantity * reference_price
        > safety_config.max_order_notional
    ):
        reasons.append("order notional exceeds max_order_notional")
    account = broker_client.account_snapshot()
    risk = check_projected_order_risk(
        request,
        account=account,
        market_price=reference_price,
        short_policy=safety_config.short_selling_policy,
    )
    if not risk.approved:
        reasons.append(risk.reason or "projected order risk rejected")
    asset = broker_client.asset_trading_details(request.symbol)
    if not asset.tradable:
        reasons.append("asset is not tradable")
    availability = check_short_sale_availability(
        request,
        account=account,
        asset=asset,
    )
    if not availability.approved:
        reasons.append(
            availability.reason or "short sale availability rejected"
        )
    return tuple(dict.fromkeys(reasons))


def _remember_plan_context(
    *,
    plan: ExecutionPlan,
    broker_client: LiveBrokerClient,
    order_output_dir: Path,
    reference_price: float,
    safety_check: TradingSafetyCheck,
) -> None:
    if plan.order_request is None:
        return
    remember = getattr(broker_client, "remember_order_record", None)
    if not callable(remember):
        return
    durable_orders = tuple(
        order
        for order in load_live_order_records(order_output_dir)
        if order.client_order_id == plan.client_order_id
    )
    if len(durable_orders) == 1:
        remember(durable_orders[0])
        return
    if len(durable_orders) > 1:
        raise ValueError("multiple durable orders match the execution plan")
    remember(
        LiveOrderRecord(
            client_order_id=plan.client_order_id,
            broker_name=plan.broker_name,
            account_id=plan.account_id,
            broker_environment=plan.broker_environment,
            request=plan.order_request,
            reference_price=reference_price,
            notional=plan.order_request.quantity * reference_price,
            safety_check=safety_check,
            status=LiveOrderStatus.UNKNOWN,
        )
    )


def _materialize_order_evidence(
    *,
    plan: ExecutionPlan,
    broker_client: LiveBrokerClient,
    adapter: LiveBrokerAdapter,
    order_output_dir: Path,
    reference_price: float,
    safety_check: TradingSafetyCheck,
) -> None:
    if plan.order_request is None:
        return
    _remember_plan_context(
        plan=plan,
        broker_client=broker_client,
        order_output_dir=order_output_dir,
        reference_price=reference_price,
        safety_check=safety_check,
    )
    durable_orders = tuple(
        order
        for order in load_live_order_records(order_output_dir)
        if order.client_order_id == plan.client_order_id
    )
    if len(durable_orders) == 1 and durable_orders[0].broker_order_id:
        adapter.refresh_order_record(durable_orders[0])
        return
    if len(durable_orders) > 1:
        raise ValueError("multiple durable orders match the execution plan")
    orders = adapter.orders_by_client_order_id(plan.client_order_id)
    if len(orders) != 1:
        raise ValueError("Alpaca reconciliation requires one planned order")
    adapter.refresh_order_record(orders[0])
