"""Rehearse semantic-target Alpaca paper requests with a fake client."""

import json
import os
from dataclasses import dataclass
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
    AlpacaSemanticTargetRunResult,
    FakeLiveBrokerClient,
    LiveBrokerClient,
    current_execution_status,
    execution_plan_path,
    latest_live_account_snapshot,
    load_execution_events,
    load_execution_plan,
    load_live_fill_records,
    load_live_order_records,
    run_alpaca_semantic_target_paper,
)
from quant.models.execution import (
    LiveReconciliationReport,
    LiveReconciliationStatus,
    ShortSellingPolicy,
    TradingMode,
    TradingSafetyConfig,
)
from quant.models.execution_lifecycle import (
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.operator import (
    ActivatedSemanticPaperOperatorRequest,
    SemanticTargetAlpacaPaperOperatorRequest,
    SemanticTargetAlpacaPaperReadinessReport,
    SemanticTargetAlpacaPaperRehearsalReport,
    SemanticTargetAlpacaPaperRunVerificationReport,
)
from quant.models.targets import (
    ContributorSet,
    ContributorSpec,
    PortfolioTargetDecision,
    ResearchRiskPolicy,
    RiskTargetDecision,
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
from quant.workflows.activated_dry_run_operator import (
    load_activated_semantic_paper_operator_request,
)

SEMANTIC_TARGET_ALPACA_PAPER_REHEARSAL_POLICY = (
    "semantic_target_alpaca_paper_fake_rehearsal_v1"
)


@dataclass(frozen=True)
class SemanticTargetAlpacaPaperRequestBundle:
    """Paths and summary for one prepared Alpaca paper request."""

    request_path: Path
    output_root: Path
    paper_output_root: Path
    contributor_set_path: Path
    strategy_decision_paths: tuple[Path, ...]
    strategy_evaluation_paths: tuple[Path, ...]
    portfolio_target_path: Path
    risk_target_path: Path
    source_request_path: Path
    symbol: str
    approved_target_quantity: Decimal
    reference_price: float
    max_order_notional: Decimal
    valid_until: datetime


@dataclass(frozen=True)
class SemanticTargetAlpacaPaperRequestInspection:
    """Read-only local preflight result for one Alpaca paper request."""

    request_id: str
    inspected_at: datetime
    valid_now: bool
    issues: tuple[str, ...]
    symbol: str
    approved_target_quantity: Decimal | None
    reference_price: float
    reviewed_max_quantity: Decimal
    reviewed_max_notional: Decimal | None
    valid_until: datetime
    output_root: Path
    market_session_open: bool
    summary: str


@dataclass(frozen=True)
class SemanticTargetAlpacaPaperRunVerification:
    """Read-only verification of one semantic-target Alpaca paper run."""

    request_id: str
    verified_at: datetime
    passed: bool
    issues: tuple[str, ...]
    symbol: str
    approved_target_quantity: Decimal | None
    output_root: Path
    execution_plan_id: str | None
    final_status: ExecutionPlanStatus | None
    event_count: int
    order_count: int
    fill_count: int
    snapshot_count: int
    reconciliation_report_count: int
    final_position_quantity: Decimal | None
    summary: str


ALPACA_PAPER_REQUIRED_ENV_NAMES = (
    "QUANT_ALPACA_PAPER_API_KEY",
    "QUANT_ALPACA_PAPER_SECRET_KEY",
    "QUANT_ALPACA_PAPER_ACCOUNT_ID",
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


def write_semantic_target_alpaca_paper_run_verification_report(
    *,
    verification: SemanticTargetAlpacaPaperRunVerification,
    request_path: Path,
    output_path: Path,
) -> Path:
    """Write one immutable broker-free Alpaca paper verification report."""
    report = _verification_report_for_result(
        verification=verification,
        request_path=request_path,
    )
    return _write_model_exclusive(output_path, report)


def load_semantic_target_alpaca_paper_run_verification_report(
    path: Path,
) -> SemanticTargetAlpacaPaperRunVerificationReport:
    """Load one persisted Alpaca paper run verification report."""
    return SemanticTargetAlpacaPaperRunVerificationReport.model_validate_json(
        path.read_text()
    )


def load_and_verify_semantic_target_alpaca_paper_run_verification_report(
    path: Path,
) -> SemanticTargetAlpacaPaperRunVerificationReport:
    """Load one Alpaca paper verification report and verify its request hash."""
    report = load_semantic_target_alpaca_paper_run_verification_report(path)
    _require_hash(Path(report.request_path), report.request_sha256)
    if not report.passed:
        raise ValueError("Alpaca paper verification report did not pass")
    if report.issues:
        raise ValueError("Alpaca paper verification report contains issues")
    return report


def evaluate_semantic_target_alpaca_paper_readiness(
    *,
    request_path: Path,
    evaluated_at: datetime,
    market_session_open: bool,
    credentials_present: bool,
    planned_verification_report_path: Path | None = None,
) -> SemanticTargetAlpacaPaperReadinessReport:
    """Evaluate broker-free readiness for one Alpaca paper test."""
    inspection = inspect_semantic_target_alpaca_paper_operator_request(
        request_path,
        inspected_at=evaluated_at,
        market_session_open=market_session_open,
    )
    issues = list(inspection.issues)
    if not credentials_present:
        issues.append("Alpaca paper credential environment is incomplete")
    if (
        planned_verification_report_path is not None
        and planned_verification_report_path.exists()
    ):
        issues.append("planned verification report path already exists")
    deduped_issues = tuple(dict.fromkeys(issues))
    ready = not deduped_issues
    return SemanticTargetAlpacaPaperReadinessReport(
        report_id=f"{inspection.request_id}-readiness",
        request_id=inspection.request_id,
        request_path=str(request_path),
        request_sha256=_file_sha256(request_path),
        evaluated_at=evaluated_at,
        ready=ready,
        issues=deduped_issues,
        symbol=inspection.symbol,
        approved_target_quantity=inspection.approved_target_quantity,
        valid_until=inspection.valid_until,
        paper_output_root=str(inspection.output_root),
        market_session_open=market_session_open,
        credentials_present=credentials_present,
        required_env_names=ALPACA_PAPER_REQUIRED_ENV_NAMES,
        planned_verification_report_path=(
            str(planned_verification_report_path)
            if planned_verification_report_path is not None
            else None
        ),
        summary=(
            "ready for one Alpaca paper test"
            if ready
            else "blocked before Alpaca paper test"
        ),
    )


def write_semantic_target_alpaca_paper_readiness_report(
    report: SemanticTargetAlpacaPaperReadinessReport,
    output_path: Path,
) -> Path:
    """Write one immutable broker-free Alpaca paper readiness report."""
    return _write_model_exclusive(output_path, report)


def load_semantic_target_alpaca_paper_readiness_report(
    path: Path,
) -> SemanticTargetAlpacaPaperReadinessReport:
    """Load one broker-free Alpaca paper readiness report."""
    return SemanticTargetAlpacaPaperReadinessReport.model_validate_json(
        path.read_text()
    )


def inspect_semantic_target_alpaca_paper_operator_request(
    path: Path,
    *,
    inspected_at: datetime | None = None,
    market_session_open: bool,
) -> SemanticTargetAlpacaPaperRequestInspection:
    """Inspect one Alpaca paper request without broker access."""
    current_time = inspected_at or datetime.now(UTC)
    request = load_semantic_target_alpaca_paper_operator_request(path)
    issues: list[str] = []
    try:
        _verify_request_hashes(request)
    except (OSError, ValueError) as exc:
        issues.append(f"artifact hash verification failed: {exc}")

    contributor_set = load_contributor_set(Path(request.contributor_set_path))
    portfolio_target = load_portfolio_target_decision(
        Path(request.portfolio_target_path)
    )
    risk_target = load_risk_target_decision(Path(request.risk_target_path))
    decisions = tuple(
        load_strategy_target_decision(Path(item))
        for item in request.strategy_decision_paths
    )

    try:
        _verify_request_scope(
            request=request,
            contributor_set=contributor_set,
            portfolio_target=portfolio_target,
            risk_target=risk_target,
        )
    except ValueError as exc:
        issues.append(str(exc))

    approved_target = risk_target.approved_target_value
    if current_time > request.valid_until:
        issues.append("alpaca paper request is expired")
    if request.safety_config.max_order_notional is None:
        issues.append("max_order_notional is missing")
        max_notional = None
    else:
        max_notional = Decimal(str(request.safety_config.max_order_notional))
    if approved_target is not None and max_notional is not None:
        notional = abs(approved_target) * Decimal(str(request.reference_price))
        if notional > max_notional:
            issues.append("approved target notional exceeds maximum")
    if not market_session_open:
        issues.append("regular US equity session is closed")
    decision_symbols = {item.symbol for item in decisions}
    if decision_symbols != {request.allowed_symbol}:
        issues.append("strategy decision symbols are outside request scope")

    valid_now = not issues
    summary = (
        "ready for one Alpaca paper command"
        if valid_now
        else "blocked before Alpaca paper command"
    )
    return SemanticTargetAlpacaPaperRequestInspection(
        request_id=request.request_id,
        inspected_at=current_time,
        valid_now=valid_now,
        issues=tuple(dict.fromkeys(issues)),
        symbol=request.allowed_symbol,
        approved_target_quantity=approved_target,
        reference_price=request.reference_price,
        reviewed_max_quantity=request.allowed_max_quantity,
        reviewed_max_notional=max_notional,
        valid_until=request.valid_until,
        output_root=Path(request.output_root),
        market_session_open=market_session_open,
        summary=summary,
    )


def verify_semantic_target_alpaca_paper_run(
    path: Path,
    *,
    verified_at: datetime | None = None,
) -> SemanticTargetAlpacaPaperRunVerification:
    """Verify one completed semantic-target Alpaca paper run from artifacts."""
    current_time = verified_at or datetime.now(UTC)
    request = load_semantic_target_alpaca_paper_operator_request(path)
    issues: list[str] = []
    contributor_set: ContributorSet | None = None
    portfolio_target: PortfolioTargetDecision | None = None
    risk_target: RiskTargetDecision | None = None
    decisions: tuple[StrategyTargetDecision, ...] = ()
    try:
        _verify_request_hashes(request)
        contributor_set = load_contributor_set(
            Path(request.contributor_set_path)
        )
        portfolio_target = load_portfolio_target_decision(
            Path(request.portfolio_target_path)
        )
        risk_target = load_risk_target_decision(Path(request.risk_target_path))
        decisions = tuple(
            load_strategy_target_decision(Path(item))
            for item in request.strategy_decision_paths
        )
        _verify_request_scope(
            request=request,
            contributor_set=contributor_set,
            portfolio_target=portfolio_target,
            risk_target=risk_target,
        )
    except (OSError, ValueError) as exc:
        issues.append(f"request validation failed: {exc}")

    output_root = Path(request.output_root)
    if not output_root.exists():
        issues.append("paper output root is missing")
    decision_symbols = {item.symbol for item in decisions}
    if decisions and decision_symbols != {request.allowed_symbol}:
        issues.append("strategy decision symbols are outside request scope")

    approved_target = (
        risk_target.approved_target_value if risk_target is not None else None
    )
    plan_id: str | None = None
    final_status: ExecutionPlanStatus | None = None
    event_count = 0
    orders = ()
    fills = ()
    snapshots = ()
    reconciliations: tuple[LiveReconciliationReport, ...] = ()
    final_quantity: Decimal | None = None

    if risk_target is not None:
        plan_path = execution_plan_path(
            output_root / "lifecycle",
            risk_target.risk_target_id,
            risk_target.revision,
        )
        try:
            plan = load_execution_plan(plan_path)
            plan_id = plan.execution_plan_id
            final_status = current_execution_status(
                plan, output_root / "lifecycle"
            )
            events = load_execution_events(
                output_root / "lifecycle", plan.execution_plan_id
            )
            event_count = len(events)
            if any(event.occurred_at > request.valid_until for event in events):
                issues.append(
                    "execution lifecycle continued after request expiration"
                )
            if final_status != ExecutionPlanStatus.SATISFIED:
                issues.append(
                    "execution lifecycle is not satisfied: "
                    f"{final_status.value}"
                )
            if plan.symbol != request.allowed_symbol:
                issues.append("execution plan symbol is outside request scope")
            if approved_target is not None and Decimal(
                plan.target_quantity
            ) != approved_target:
                issues.append("execution plan target differs from risk target")
        except (OSError, ValueError) as exc:
            issues.append(f"execution lifecycle verification failed: {exc}")

    try:
        orders = load_live_order_records(output_root / "orders")
        fills = load_live_fill_records(output_root / "fills")
        snapshots = tuple(sorted((output_root / "snapshots").glob("*.json")))
        reconciliations = _load_live_reconciliation_reports(
            output_root / "reconciliations"
        )
    except (OSError, ValueError) as exc:
        issues.append(f"paper evidence loading failed: {exc}")

    if len(orders) != 1:
        issues.append(
            f"expected exactly one order artifact, found {len(orders)}"
        )
    if len(fills) != 1:
        issues.append(f"expected exactly one fill artifact, found {len(fills)}")
    if not reconciliations:
        issues.append("expected at least one reconciliation report")
    elif reconciliations[-1].status != LiveReconciliationStatus.PASSED:
        issues.append(
            "latest reconciliation report is not passed: "
            f"{reconciliations[-1].status.value}"
        )

    snapshot = latest_live_account_snapshot(output_root / "snapshots")
    if snapshot is not None:
        final_quantity = Decimal("0")
        for position in snapshot.positions:
            if position.symbol == request.allowed_symbol:
                final_quantity = Decimal(str(position.quantity))
                break
    if approved_target is not None and final_quantity != approved_target:
        issues.append("final broker snapshot position differs from risk target")

    for artifact_path in _paper_run_artifact_paths(output_root):
        if not _is_relative_to(artifact_path, output_root):
            issues.append(
                f"paper evidence path is outside output root: {artifact_path}"
            )

    deduped_issues = tuple(dict.fromkeys(issues))
    passed = not deduped_issues
    return SemanticTargetAlpacaPaperRunVerification(
        request_id=request.request_id,
        verified_at=current_time,
        passed=passed,
        issues=deduped_issues,
        symbol=request.allowed_symbol,
        approved_target_quantity=approved_target,
        output_root=output_root,
        execution_plan_id=plan_id,
        final_status=final_status,
        event_count=event_count,
        order_count=len(orders),
        fill_count=len(fills),
        snapshot_count=len(snapshots),
        reconciliation_report_count=len(reconciliations),
        final_position_quantity=final_quantity,
        summary=(
            "verified semantic-target Alpaca paper run"
            if passed
            else "blocked semantic-target Alpaca paper evidence"
        ),
    )


def prepare_semantic_target_alpaca_paper_request(
    *,
    request_id: str,
    source_request_path: Path,
    output_root: Path,
    paper_output_root: Path,
    max_order_notional: Decimal,
    allowed_max_quantity: Decimal,
    valid_for_seconds: int,
    evaluated_at: datetime | None = None,
) -> SemanticTargetAlpacaPaperRequestBundle:
    """Prepare one broker-free reviewed Alpaca paper request."""
    _require_safe_component(request_id)
    if max_order_notional <= 0:
        raise ValueError("max_order_notional must be positive")
    if allowed_max_quantity <= 0:
        raise ValueError("allowed_max_quantity must be positive")
    if valid_for_seconds <= 0:
        raise ValueError("valid_for_seconds must be positive")

    source = load_activated_semantic_paper_operator_request(
        source_request_path
    )
    current_time = evaluated_at or source.evaluated_at
    copied = _copy_source_request_artifacts(
        source=source,
        output_root=output_root / "inputs",
    )
    contributor_set = load_contributor_set(copied.contributor_set_path)
    decisions = tuple(
        load_strategy_target_decision(path)
        for path in copied.strategy_decision_paths
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id=f"{request_id}-portfolio-target",
        revision=1,
        contributor_set=contributor_set,
        decisions=decisions,
        evaluated_at=current_time,
        evidence_refs=(str(source_request_path),),
    )
    if portfolio_target.status.value != "aggregated":
        raise ValueError(f"portfolio target blocked: {portfolio_target.reason}")
    portfolio_target_path = _write_or_verify_portfolio_target_decision(
        portfolio_target, output_root / "inputs" / "portfolio-targets"
    )
    risk_target = evaluate_research_risk_target(
        risk_target_id=f"{request_id}-risk-target",
        revision=1,
        portfolio_target=portfolio_target,
        policy=source.risk_policy,
        evaluated_at=current_time,
        evidence_refs=(str(portfolio_target_path), str(source_request_path)),
    )
    if risk_target.status.value != "approved":
        raise ValueError(
            "risk target rejected: " + "; ".join(risk_target.reasons)
        )
    if risk_target.approved_target_value is None:
        raise ValueError("approved risk target is missing target quantity")
    approved_target = risk_target.approved_target_value
    if approved_target != approved_target.to_integral_value():
        raise ValueError("Alpaca paper request requires whole-share target")
    if abs(approved_target) > allowed_max_quantity:
        raise ValueError("approved target exceeds allowed maximum quantity")
    notional = abs(approved_target) * Decimal(str(source.reference_price))
    if notional > max_order_notional:
        raise ValueError("approved target notional exceeds maximum")
    risk_target_path = _write_or_verify_risk_target_decision(
        risk_target, output_root / "inputs" / "risk-targets"
    )

    request = SemanticTargetAlpacaPaperOperatorRequest(
        request_id=request_id,
        contributor_set_path=str(copied.contributor_set_path),
        contributor_set_sha256=_file_sha256(copied.contributor_set_path),
        strategy_decision_paths=tuple(
            str(path) for path in copied.strategy_decision_paths
        ),
        strategy_decision_sha256s=tuple(
            _file_sha256(path) for path in copied.strategy_decision_paths
        ),
        portfolio_target_path=str(portfolio_target_path),
        portfolio_target_sha256=_file_sha256(portfolio_target_path),
        risk_target_path=str(risk_target_path),
        risk_target_sha256=_file_sha256(risk_target_path),
        risk_policy=source.risk_policy,
        execution_policy=source.execution_policy,
        reference_price=source.reference_price,
        safety_config=TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
            max_order_notional=float(max_order_notional),
            broker_name="alpaca-paper",
            short_selling_policy=ShortSellingPolicy(),
        ),
        output_root=str(paper_output_root),
        evaluated_at=current_time,
        valid_until=current_time + timedelta(seconds=valid_for_seconds),
        alpaca_submission_enabled=True,
        allowed_symbol=contributor_set.symbol,
        allowed_max_quantity=allowed_max_quantity,
        evidence_refs=(
            "prepared:semantic-target-alpaca-paper-request",
            str(source_request_path),
        ),
    )
    request_path = _write_or_verify_alpaca_paper_operator_request(
        request, output_root / "inputs" / "requests"
    )
    return SemanticTargetAlpacaPaperRequestBundle(
        request_path=request_path,
        output_root=output_root,
        paper_output_root=paper_output_root,
        contributor_set_path=copied.contributor_set_path,
        strategy_decision_paths=copied.strategy_decision_paths,
        strategy_evaluation_paths=copied.strategy_evaluation_paths,
        portfolio_target_path=portfolio_target_path,
        risk_target_path=risk_target_path,
        source_request_path=source_request_path,
        symbol=contributor_set.symbol,
        approved_target_quantity=approved_target,
        reference_price=source.reference_price,
        max_order_notional=max_order_notional,
        valid_until=request.valid_until,
    )


def run_semantic_target_alpaca_paper_operator_request(
    *,
    request_path: Path,
    broker_client: LiveBrokerClient,
    evaluated_at: datetime | None = None,
) -> AlpacaSemanticTargetRunResult:
    """Run one reviewed semantic-target request against Alpaca paper."""
    current_time = evaluated_at or datetime.now(UTC)
    request = load_semantic_target_alpaca_paper_operator_request(request_path)
    if current_time > request.valid_until:
        raise ValueError("alpaca paper request is expired")
    _verify_request_hashes(request)

    contributor_set = load_contributor_set(Path(request.contributor_set_path))
    decisions = tuple(
        load_strategy_target_decision(Path(path))
        for path in request.strategy_decision_paths
    )
    portfolio_target = load_portfolio_target_decision(
        Path(request.portfolio_target_path)
    )
    risk_target = load_risk_target_decision(Path(request.risk_target_path))
    _verify_request_scope(
        request=request,
        contributor_set=contributor_set,
        portfolio_target=portfolio_target,
        risk_target=risk_target,
    )

    output_root = Path(request.output_root)
    preserved_request_path = _preserve_request(
        request_path=request_path,
        output_root=output_root,
        request_id=request.request_id,
    )
    evidence_refs = tuple(
        dict.fromkeys(
            (
                str(request_path),
                str(preserved_request_path),
                *request.evidence_refs,
            )
        )
    )
    return run_alpaca_semantic_target_paper(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=request.risk_policy,
        policy=request.execution_policy,
        reference_price=request.reference_price,
        safety_config=request.safety_config,
        broker_client=broker_client,
        artifact_root=output_root / "lifecycle",
        order_output_dir=output_root / "orders",
        fill_output_dir=output_root / "fills",
        snapshot_output_dir=output_root / "snapshots",
        reconciliation_output_dir=output_root / "reconciliations",
        evaluated_at=current_time,
        alpaca_submission_enabled=request.alpaca_submission_enabled,
        evidence_refs=evidence_refs,
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
        valid_until=evaluated_at + timedelta(minutes=30),
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


@dataclass(frozen=True)
class _CopiedSourceArtifacts:
    contributor_set_path: Path
    strategy_decision_paths: tuple[Path, ...]
    strategy_evaluation_paths: tuple[Path, ...]


def _copy_source_request_artifacts(
    *,
    source: ActivatedSemanticPaperOperatorRequest,
    output_root: Path,
) -> _CopiedSourceArtifacts:
    contributor_path = _copy_file(
        Path(source.contributor_set_path),
        output_root / "contributor-sets" / "source-contributor-set.json",
    )
    decision_paths = tuple(
        _copy_file(
            Path(path),
            output_root / "strategy-targets" / f"{index}.json",
        )
        for index, path in enumerate(source.strategy_decision_paths)
    )
    evaluation_paths = tuple(
        _copy_file(
            Path(path),
            output_root / "strategy-evaluations" / f"{index}.json",
        )
        for index, path in enumerate(source.strategy_evaluation_paths)
    )
    return _CopiedSourceArtifacts(
        contributor_set_path=contributor_path,
        strategy_decision_paths=decision_paths,
        strategy_evaluation_paths=evaluation_paths,
    )


def _copy_file(source: Path, destination: Path) -> Path:
    payload = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != payload:
            raise FileExistsError(f"conflicting copied artifact: {destination}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    with os.fdopen(os.open(destination, flags, 0o644), "wb") as handle:
        handle.write(payload)
    return destination


def _write_or_verify_portfolio_target_decision(
    decision: PortfolioTargetDecision, output_root: Path
) -> Path:
    path = (
        output_root
        / decision.portfolio_target_id
        / f"{decision.revision}.json"
    )
    if path.exists():
        if load_portfolio_target_decision(path) != decision:
            raise FileExistsError(f"conflicting portfolio target: {path}")
        return path
    return write_portfolio_target_decision(decision, output_root)


def _write_or_verify_risk_target_decision(
    decision: RiskTargetDecision, output_root: Path
) -> Path:
    path = output_root / decision.risk_target_id / f"{decision.revision}.json"
    if path.exists():
        if load_risk_target_decision(path) != decision:
            raise FileExistsError(f"conflicting risk target: {path}")
        return path
    return write_risk_target_decision(decision, output_root)


def _write_or_verify_alpaca_paper_operator_request(
    request: SemanticTargetAlpacaPaperOperatorRequest, output_root: Path
) -> Path:
    path = output_root / f"{request.request_id}.json"
    if path.exists():
        if load_semantic_target_alpaca_paper_operator_request(path) != request:
            raise FileExistsError(f"conflicting Alpaca paper request: {path}")
        return path
    return write_semantic_target_alpaca_paper_operator_request(
        request, output_root
    )


def _verify_request_scope(
    *,
    request: SemanticTargetAlpacaPaperOperatorRequest,
    contributor_set: ContributorSet,
    portfolio_target: PortfolioTargetDecision,
    risk_target: RiskTargetDecision,
) -> None:
    if contributor_set.symbol != request.allowed_symbol:
        raise ValueError("contributor set symbol is outside request scope")
    if portfolio_target.symbol != request.allowed_symbol:
        raise ValueError("portfolio target symbol is outside request scope")
    if risk_target.symbol != request.allowed_symbol:
        raise ValueError("risk target symbol is outside request scope")
    if risk_target.approved_target_value is None:
        raise ValueError("alpaca paper request requires approved risk target")
    if risk_target.approved_target_value != (
        risk_target.approved_target_value.to_integral_value()
    ):
        raise ValueError("alpaca paper request requires whole-share target")
    if abs(risk_target.approved_target_value) > request.allowed_max_quantity:
        raise ValueError("risk target quantity exceeds request maximum")


def _preserve_request(
    *, request_path: Path, output_root: Path, request_id: str
) -> Path:
    destination = output_root / "requests" / f"{request_id}.json"
    payload = request_path.read_bytes()
    if destination.exists():
        if destination.read_bytes() != payload:
            raise FileExistsError(
                f"conflicting preserved request exists: {destination}"
            )
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    with os.fdopen(os.open(destination, flags, 0o644), "wb") as handle:
        handle.write(payload)
    return destination


def _evidence_paths(output_root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in output_root.rglob("*")
            if path.is_file() and "reports" not in path.parts
        )
    )


def _load_live_reconciliation_reports(
    reconciliation_dir: Path,
) -> tuple[LiveReconciliationReport, ...]:
    reports = tuple(
        LiveReconciliationReport.model_validate_json(path.read_text())
        for path in sorted(reconciliation_dir.rglob("*.json"))
    )
    return tuple(sorted(reports, key=lambda report: report.created_at))


def _verification_report_for_result(
    *,
    verification: SemanticTargetAlpacaPaperRunVerification,
    request_path: Path,
) -> SemanticTargetAlpacaPaperRunVerificationReport:
    return SemanticTargetAlpacaPaperRunVerificationReport(
        report_id=f"{verification.request_id}-verification",
        request_id=verification.request_id,
        request_path=str(request_path),
        request_sha256=_file_sha256(request_path),
        verified_at=verification.verified_at,
        passed=verification.passed,
        issues=verification.issues,
        symbol=verification.symbol,
        approved_target_quantity=verification.approved_target_quantity,
        output_root=str(verification.output_root),
        execution_plan_id=verification.execution_plan_id,
        final_status=verification.final_status,
        event_count=verification.event_count,
        order_count=verification.order_count,
        fill_count=verification.fill_count,
        snapshot_count=verification.snapshot_count,
        reconciliation_report_count=(
            verification.reconciliation_report_count
        ),
        final_position_quantity=verification.final_position_quantity,
        summary=verification.summary,
    )


def _paper_run_artifact_paths(output_root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for directory in (
                output_root / "lifecycle",
                output_root / "orders",
                output_root / "fills",
                output_root / "snapshots",
                output_root / "reconciliations",
                output_root / "requests",
            )
            for path in directory.rglob("*.json")
        )
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


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
