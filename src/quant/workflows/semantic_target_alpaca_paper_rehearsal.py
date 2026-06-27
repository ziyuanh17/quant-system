"""Rehearse semantic-target Alpaca paper requests with a fake client."""

import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    LIVE_TRADING_CONFIRMATION,
    SINGLE_MARKET_ORDER_POLICY,
    FakeLiveBrokerClient,
    run_alpaca_semantic_target_paper,
)
from quant.models.execution import (
    ShortSellingPolicy,
    TradingMode,
    TradingSafetyConfig,
)
from quant.models.execution_lifecycle import (
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.operator import (
    SemanticTargetAlpacaPaperOperatorRequest,
    SemanticTargetAlpacaPaperRehearsalReport,
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
from quant.research.target_artifacts import (
    load_contributor_set,
    load_portfolio_target_decision,
    load_risk_target_decision,
    load_strategy_target_decision,
    write_contributor_set,
    write_portfolio_target_decision,
    write_risk_target_decision,
    write_strategy_target_decision,
)

SEMANTIC_TARGET_ALPACA_PAPER_REHEARSAL_POLICY = (
    "semantic_target_alpaca_paper_fake_rehearsal_v1"
)


def write_semantic_target_alpaca_paper_operator_request(
    request: SemanticTargetAlpacaPaperOperatorRequest,
    output_root: Path,
) -> Path:
    """Write one reviewed Alpaca paper operator request immutably."""
    return _write_model_exclusive(
        output_root / f"{request.request_id}.json", request
    )


def load_semantic_target_alpaca_paper_operator_request(
    path: Path,
) -> SemanticTargetAlpacaPaperOperatorRequest:
    """Load and validate one reviewed Alpaca paper operator request."""
    return SemanticTargetAlpacaPaperOperatorRequest.model_validate_json(
        path.read_text()
    )


def run_semantic_target_alpaca_paper_fake_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime | None = None,
) -> SemanticTargetAlpacaPaperRehearsalReport:
    """Run a fake-client rehearsal for one Alpaca paper operator request."""
    _require_safe_component(rehearsal_id)
    current_time = evaluated_at or datetime.now(UTC)
    source = _write_reviewed_source(output_root / "inputs", current_time)
    request = _request_for_source(
        request_id=f"{rehearsal_id}-request",
        source=source,
        output_root=output_root / "output",
        evaluated_at=current_time,
    )
    request_path = write_semantic_target_alpaca_paper_operator_request(
        request, output_root / "requests"
    )
    loaded = load_semantic_target_alpaca_paper_operator_request(request_path)
    _verify_request_hashes(loaded)

    contributor_set = load_contributor_set(Path(loaded.contributor_set_path))
    decisions = tuple(
        load_strategy_target_decision(Path(path))
        for path in loaded.strategy_decision_paths
    )
    portfolio_target = load_portfolio_target_decision(
        Path(loaded.portfolio_target_path)
    )
    risk_target = load_risk_target_decision(Path(loaded.risk_target_path))

    client = FakeLiveBrokerClient(
        initial_cash=1_000,
        broker_name="alpaca-paper",
        account_id="acct-fake",
        broker_environment="paper",
    )
    first = run_alpaca_semantic_target_paper(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=loaded.risk_policy,
        policy=loaded.execution_policy,
        reference_price=loaded.reference_price,
        safety_config=loaded.safety_config,
        broker_client=client,
        artifact_root=Path(loaded.output_root) / "lifecycle",
        order_output_dir=Path(loaded.output_root) / "orders",
        fill_output_dir=Path(loaded.output_root) / "fills",
        snapshot_output_dir=Path(loaded.output_root) / "snapshots",
        reconciliation_output_dir=Path(loaded.output_root)
        / "reconciliations",
        evaluated_at=current_time,
        alpaca_submission_enabled=loaded.alpaca_submission_enabled,
        evidence_refs=(str(request_path),),
    )
    second = run_alpaca_semantic_target_paper(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=loaded.risk_policy,
        policy=loaded.execution_policy,
        reference_price=loaded.reference_price,
        safety_config=loaded.safety_config,
        broker_client=client,
        artifact_root=Path(loaded.output_root) / "lifecycle",
        order_output_dir=Path(loaded.output_root) / "orders",
        fill_output_dir=Path(loaded.output_root) / "fills",
        snapshot_output_dir=Path(loaded.output_root) / "snapshots",
        reconciliation_output_dir=Path(loaded.output_root)
        / "reconciliations",
        evaluated_at=current_time + timedelta(seconds=1),
        alpaca_submission_enabled=loaded.alpaca_submission_enabled,
        evidence_refs=(str(request_path),),
    )

    account = client.account_snapshot()
    final_quantity = Decimal("0")
    for position in account.positions:
        if position.symbol == loaded.allowed_symbol:
            final_quantity = Decimal(position.quantity)
            break
    output_path = Path(loaded.output_root)
    order_count = len(tuple((output_path / "orders").rglob("*.json")))
    reconciliation_count = len(
        tuple((output_path / "reconciliations").rglob("*.json"))
    )
    evidence_paths = _evidence_paths(output_root)
    report = SemanticTargetAlpacaPaperRehearsalReport(
        rehearsal_id=rehearsal_id,
        request_path=str(request_path),
        request_sha256=_file_sha256(request_path),
        passed=(
            first.status == ExecutionPlanStatus.SATISFIED
            and second.status == ExecutionPlanStatus.SATISFIED
            and order_count == 1
            and len(client.fills()) == 1
            and final_quantity == Decimal("2")
            and first.reconciliation is not None
            and first.reconciliation.passed
        ),
        first_status=first.status,
        second_status=second.status,
        execution_plan_id=first.plan.execution_plan_id,
        order_count=order_count,
        fill_count=len(client.fills()),
        final_position_quantity=final_quantity,
        reconciliation_report_count=reconciliation_count,
        evidence_paths=tuple(str(path) for path in evidence_paths),
        evidence_sha256s=tuple(_file_sha256(path) for path in evidence_paths),
        prohibited_api_calls=(),
        completed_at=current_time,
    )
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    _write_model_exclusive(report_path, report)
    return report


def load_and_verify_semantic_target_alpaca_paper_rehearsal(
    path: Path,
) -> SemanticTargetAlpacaPaperRehearsalReport:
    """Load one fake-client Alpaca paper rehearsal report and verify hashes."""
    report = SemanticTargetAlpacaPaperRehearsalReport.model_validate_json(
        path.read_text()
    )
    if _file_sha256(Path(report.request_path)) != report.request_sha256:
        raise ValueError("alpaca paper rehearsal request hash mismatch")
    for evidence_path, expected in zip(
        report.evidence_paths, report.evidence_sha256s, strict=True
    ):
        if _file_sha256(Path(evidence_path)) != expected:
            raise ValueError("alpaca paper rehearsal evidence hash mismatch")
    if report.prohibited_api_calls:
        raise ValueError("alpaca paper rehearsal used prohibited API calls")
    if not report.passed:
        raise ValueError("alpaca paper rehearsal did not pass")
    return report


def _write_reviewed_source(
    output_root: Path, evaluated_at: datetime
) -> tuple[Path, tuple[Path, ...], Path, Path, ResearchRiskPolicy]:
    decision = StrategyTargetDecision(
        decision_id="fake-alpaca-paper-target-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id="synthetic-bars-sha256",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="fake-client alpaca paper rehearsal target",
    )
    contributor_set = ContributorSet(
        contributor_set_id="fake-alpaca-paper-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="fake-client alpaca paper rehearsal ownership",
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id="fake-alpaca-paper-portfolio-target",
        revision=1,
        contributor_set=contributor_set,
        decisions=(decision,),
        evaluated_at=evaluated_at,
    )
    risk_policy = ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=Decimal("100"),
    )
    risk_target = evaluate_research_risk_target(
        risk_target_id="fake-alpaca-paper-risk-target",
        revision=1,
        portfolio_target=portfolio_target,
        policy=risk_policy,
        evaluated_at=evaluated_at,
    )
    contributor_path = write_contributor_set(
        contributor_set, output_root / "contributor-sets"
    )
    decision_path = write_strategy_target_decision(
        decision, output_root / "strategy-targets"
    )
    portfolio_path = write_portfolio_target_decision(
        portfolio_target, output_root / "portfolio-targets"
    )
    risk_path = write_risk_target_decision(
        risk_target, output_root / "risk-targets"
    )
    return (
        contributor_path,
        (decision_path,),
        portfolio_path,
        risk_path,
        risk_policy,
    )


def _request_for_source(
    *,
    request_id: str,
    source: tuple[Path, tuple[Path, ...], Path, Path, ResearchRiskPolicy],
    output_root: Path,
    evaluated_at: datetime,
) -> SemanticTargetAlpacaPaperOperatorRequest:
    contributor_path, decision_paths, portfolio_path, risk_path, risk_policy = (
        source
    )
    return SemanticTargetAlpacaPaperOperatorRequest(
        request_id=request_id,
        contributor_set_path=str(contributor_path),
        contributor_set_sha256=_file_sha256(contributor_path),
        strategy_decision_paths=tuple(str(path) for path in decision_paths),
        strategy_decision_sha256s=tuple(
            _file_sha256(path) for path in decision_paths
        ),
        portfolio_target_path=str(portfolio_path),
        portfolio_target_sha256=_file_sha256(portfolio_path),
        risk_target_path=str(risk_path),
        risk_target_sha256=_file_sha256(risk_path),
        risk_policy=risk_policy,
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=100,
        safety_config=TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
            max_order_notional=1_000,
            broker_name="alpaca-paper",
            short_selling_policy=ShortSellingPolicy(),
        ),
        output_root=str(output_root),
        evaluated_at=evaluated_at,
        alpaca_submission_enabled=True,
        allowed_symbol="AAPL",
        allowed_max_quantity=Decimal("2"),
        evidence_refs=(SEMANTIC_TARGET_ALPACA_PAPER_REHEARSAL_POLICY,),
    )


def _verify_request_hashes(
    request: SemanticTargetAlpacaPaperOperatorRequest,
) -> None:
    _require_hash(
        Path(request.contributor_set_path), request.contributor_set_sha256
    )
    for path, expected in zip(
        request.strategy_decision_paths,
        request.strategy_decision_sha256s,
        strict=True,
    ):
        _require_hash(Path(path), expected)
    _require_hash(
        Path(request.portfolio_target_path), request.portfolio_target_sha256
    )
    _require_hash(Path(request.risk_target_path), request.risk_target_sha256)


def _evidence_paths(output_root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in output_root.rglob("*")
            if path.is_file() and "reports" not in path.parts
        )
    )


def _write_model_exclusive(path: Path, model: BaseModel) -> Path:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path


def _require_hash(path: Path, expected: str) -> None:
    if _file_sha256(path) != expected:
        raise ValueError(f"artifact hash mismatch: {path}")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require_safe_component(value: str) -> None:
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("rehearsal ID must be a safe path component")
