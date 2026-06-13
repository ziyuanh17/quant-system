from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    LIVE_TRADING_CONFIRMATION,
    SINGLE_MARKET_ORDER_POLICY,
    FakeLiveBrokerClient,
    run_alpaca_semantic_target_paper,
)
from quant.models.execution import (
    AssetTradingDetails,
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    OrderRequest,
    ShortSellingPolicy,
    TradingMode,
    TradingSafetyCheck,
    TradingSafetyConfig,
)
from quant.models.execution_lifecycle import (
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    ContributorSpec,
    ResearchRiskPolicy,
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.research import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)


def test_alpaca_semantic_target_requires_explicit_activation(tmp_path) -> None:
    source = _source()
    client = _client()

    with pytest.raises(ValueError, match="submission is not enabled"):
        _run(source, client, tmp_path, enabled=False)

    assert client.fills() == ()


def test_alpaca_semantic_target_reaches_reconciled_satisfaction(
    tmp_path,
) -> None:
    source = _source()
    client = _client()

    result = _run(source, client, tmp_path)

    assert result.status == ExecutionPlanStatus.SATISFIED
    assert result.reconciliation is not None
    assert result.reconciliation.passed
    assert len(client.fills()) == 1
    assert client.account_snapshot().positions[0].quantity == 2
    assert len(tuple((tmp_path / "reconciliations").rglob("*.json"))) == 1


def test_alpaca_semantic_target_blocks_operational_notional(tmp_path) -> None:
    source = _source()
    client = _client()

    result = _run(source, client, tmp_path, max_order_notional=100)

    assert result.status == ExecutionPlanStatus.BLOCKED
    assert client.fills() == ()


def test_alpaca_semantic_target_blocks_short_when_disabled(tmp_path) -> None:
    source = _source(target_value=Decimal("-2"))
    client = _client()

    result = _run(source, client, tmp_path)

    assert result.status == ExecutionPlanStatus.BLOCKED
    assert client.fills() == ()


def test_alpaca_semantic_target_recovers_ambiguous_submission(
    tmp_path,
) -> None:
    source = _source()
    client = _client()

    first = _run(source, _SubmitThenRaise(client), tmp_path)
    second = _run(source, client, tmp_path)

    assert first.status == ExecutionPlanStatus.AMBIGUOUS
    assert second.status == ExecutionPlanStatus.SATISFIED
    assert len(client.fills()) == 1


def test_alpaca_semantic_target_failed_reconciliation_prevents_satisfaction(
    tmp_path,
) -> None:
    source = _source()
    client = _client()

    result = _run(source, _MissingFillClient(client), tmp_path)

    assert result.status == ExecutionPlanStatus.FILLED
    assert result.reconciliation is not None
    assert not result.reconciliation.passed
    assert len(client.fills()) == 1


def test_alpaca_semantic_target_blocks_untradable_asset(tmp_path) -> None:
    source = _source()
    client = _client()

    result = _run(source, _UntradableClient(client), tmp_path)

    assert result.status == ExecutionPlanStatus.BLOCKED
    assert client.fills() == ()


def test_alpaca_semantic_target_blocks_when_operational_risk_unavailable(
    tmp_path,
) -> None:
    source = _source()
    client = _client()

    result = _run(source, _UnavailableAssetClient(client), tmp_path)

    assert result.status == ExecutionPlanStatus.BLOCKED
    assert client.fills() == ()


class _SubmitThenRaise:
    def __init__(self, delegate: FakeLiveBrokerClient) -> None:
        self.delegate = delegate

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        self.delegate.submit_market_order(
            request,
            reference_price=reference_price,
            client_order_id=client_order_id,
            safety_check=safety_check,
        )
        raise RuntimeError("simulated response loss")

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


class _MissingFillClient:
    def __init__(self, delegate: FakeLiveBrokerClient) -> None:
        self.delegate = delegate
        self.fill_calls = 0

    def fills(self) -> tuple[LiveFillRecord, ...]:
        self.fill_calls += 1
        return self.delegate.fills() if self.fill_calls == 1 else ()

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


class _UntradableClient:
    def __init__(self, delegate: FakeLiveBrokerClient) -> None:
        self.delegate = delegate

    def asset_trading_details(self, symbol: str) -> AssetTradingDetails:
        return AssetTradingDetails(
            symbol=symbol,
            tradable=False,
            shortable=False,
            easy_to_borrow=False,
        )

    def account_snapshot(self) -> LiveAccountSnapshot:
        return self.delegate.account_snapshot()

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


class _UnavailableAssetClient:
    def __init__(self, delegate: FakeLiveBrokerClient) -> None:
        self.delegate = delegate

    def asset_trading_details(self, symbol: str) -> AssetTradingDetails:
        raise RuntimeError("asset service unavailable")

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


def _run(
    source,
    client,
    root,
    *,
    enabled: bool = True,
    max_order_notional: float = 1_000,
):
    contributor_set, decisions, portfolio_target, risk_policy, risk_target = (
        source
    )
    return run_alpaca_semantic_target_paper(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        policy=_policy(),
        reference_price=100,
        safety_config=TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
            max_order_notional=max_order_notional,
            broker_name="alpaca-paper",
            short_selling_policy=ShortSellingPolicy(),
        ),
        broker_client=client,
        artifact_root=root / "lifecycle",
        order_output_dir=root / "orders",
        fill_output_dir=root / "fills",
        snapshot_output_dir=root / "snapshots",
        reconciliation_output_dir=root / "reconciliations",
        evaluated_at=_now(),
        alpaca_submission_enabled=enabled,
    )


def _client() -> FakeLiveBrokerClient:
    return FakeLiveBrokerClient(
        initial_cash=1_000,
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
    )


def _source(target_value: Decimal = Decimal("2")):
    decision = StrategyTargetDecision(
        decision_id="decision-1",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target_value,
        sizing_policy_version="fixed_shares_v1",
        input_data_id="bars-sha256",
        generated_at=_now(),
        effective_at=_now(),
        valid_until=_now() + timedelta(days=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="research target",
    )
    contributor_set = ContributorSet(
        contributor_set_id="aapl-v1",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="research ownership",
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id="portfolio-1",
        revision=1,
        contributor_set=contributor_set,
        decisions=(decision,),
        evaluated_at=_now(),
    )
    risk_policy = ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=Decimal("100"),
    )
    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-1",
        revision=1,
        portfolio_target=portfolio_target,
        policy=risk_policy,
        evaluated_at=_now(),
    )
    return (
        contributor_set,
        (decision,),
        portfolio_target,
        risk_policy,
        risk_target,
    )


def _policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=(
            ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
        ),
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _now() -> datetime:
    return datetime(2026, 6, 13, 12, tzinfo=UTC)
