"""Test the activated semantic-target dry-run operator CLI boundary."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from quant.cli import app
from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.activation import (
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationScope,
)
from quant.models.execution import LiveAccountSnapshot
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
from quant.models.operator import ActivatedDryRunOperatorRequest
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
from quant.workflows import (
    SEMANTIC_TARGET_ORCHESTRATION_POLICY,
    SEMANTIC_TARGET_REHEARSAL_POLICY,
    rehearsal_report_sha256,
    run_activation_consumption_local_rehearsal,
    write_activated_dry_run_operator_request,
    write_semantic_target_activation_authorization,
)


def test_activated_dry_run_cli_succeeds_and_is_restart_safe(tmp_path) -> None:
    request_path = _request_path(tmp_path)
    args = _command_args(tmp_path, request_path)

    first = CliRunner().invoke(app, args)
    second = CliRunner().invoke(app, args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Activation decision: allowed" in first.output
    assert "Workflow status: dry_run_observed" in first.output
    assert "Dry-run status: would_submit" in first.output
    output_root = tmp_path / "output"
    assert len(tuple((output_root / "orchestrations").glob("*.json"))) == 1
    assert (
        len(
            tuple(
                (
                    output_root / "lifecycle" / "dry-run-observations"
                ).rglob("*.json")
            )
        )
        == 1
    )


def test_inspect_activated_dry_run_request_explains_without_writing(
    tmp_path,
) -> None:
    request_path = _request_path(tmp_path)
    files_before = tuple(sorted(tmp_path.rglob("*")))

    result = CliRunner().invoke(app, _inspect_args(request_path))

    assert result.exit_code == 0
    assert "Valid now: yes" in result.output
    assert "Current position: 0 shares" in result.output
    assert "Approved target: 2 shares" in result.output
    assert "Intended order: BUY 2 shares" in result.output
    assert "Inspection created no activation or execution artifacts." in (
        result.output
    )
    assert tuple(sorted(tmp_path.rglob("*"))) == files_before


def test_inspect_activated_dry_run_request_reports_block_without_writing(
    tmp_path,
) -> None:
    request_path = _request_path(tmp_path, open_order_ids=("working-1",))
    files_before = tuple(sorted(tmp_path.rglob("*")))

    result = CliRunner().invoke(app, _inspect_args(request_path))

    assert result.exit_code == 1
    assert "Valid now: no" in result.output
    assert "account snapshot contains unsettled working orders" in result.output
    assert tuple(sorted(tmp_path.rglob("*"))) == files_before


def test_inspection_does_not_consume_request_activation(tmp_path) -> None:
    request_path = _request_path(tmp_path)

    inspection = CliRunner().invoke(app, _inspect_args(request_path))
    execution = CliRunner().invoke(app, _command_args(tmp_path, request_path))

    assert inspection.exit_code == 0
    assert execution.exit_code == 0
    assert "Activation decision: allowed" in execution.output


def test_activated_dry_run_cli_blocks_expired_authorization_before_targets(
    tmp_path,
) -> None:
    request_path = _request_path(tmp_path, valid_until=_now())

    result = CliRunner().invoke(app, _command_args(tmp_path, request_path))

    assert result.exit_code == 1
    assert "Activation decision: blocked" in result.output
    assert "authorization is expired" in result.output
    assert (
        tmp_path / "output" / "operator-requests" / "request-1.json"
    ).is_file()
    assert not (tmp_path / "output" / "strategy-targets").exists()
    assert not (tmp_path / "output" / "lifecycle").exists()


def test_activated_dry_run_cli_rejects_missing_request_without_artifacts(
    tmp_path,
) -> None:
    result = CliRunner().invoke(
        app,
        _command_args(tmp_path, tmp_path / "missing.json"),
    )

    assert result.exit_code == 2
    assert not (tmp_path / "activation").exists()
    assert not (tmp_path / "output").exists()


def test_activated_dry_run_cli_requires_activation_rehearsal_evidence(
    tmp_path,
) -> None:
    request_path = _request_path(tmp_path)
    request_path.write_text(
        request_path.read_text().replace(
            str(tmp_path / "inputs" / "activation-rehearsal"),
            str(tmp_path / "missing-activation-rehearsal"),
        )
    )

    result = CliRunner().invoke(app, _command_args(tmp_path, request_path))

    assert result.exit_code == 2
    assert (tmp_path / "output" / "operator-requests").exists()
    assert not (tmp_path / "activation").exists()
    assert not (tmp_path / "output" / "strategy-targets").exists()


def test_activated_dry_run_cli_has_no_mode_or_broker_selector() -> None:
    result = CliRunner().invoke(app, ["dry-run", "activated-target", "--help"])

    assert result.exit_code == 0
    assert "--mode" not in result.output
    assert "alpaca" not in result.output.lower()
    assert "paper" not in result.output.lower()
    assert "broker" not in result.output.lower()


def test_activated_dry_run_inspection_has_only_request_selector() -> None:
    result = CliRunner().invoke(
        app, ["dry-run", "inspect-activated-target", "--help"]
    )

    assert result.exit_code == 0
    assert "--request-path" in result.output
    assert "--activation-root" not in result.output
    assert "--output-root" not in result.output
    assert "--mode" not in result.output
    assert "broker" not in result.output.lower()


def test_activated_dry_run_cli_exits_nonzero_for_blocked_observation(
    tmp_path,
) -> None:
    request_path = _request_path(tmp_path, open_order_ids=("working-1",))

    result = CliRunner().invoke(app, _command_args(tmp_path, request_path))

    assert result.exit_code == 1
    assert "Activation decision: allowed" in result.output
    assert "Dry-run status: blocked" in result.output


def test_activated_dry_run_request_rejects_unsafe_identifiers(tmp_path) -> None:
    request_path = _request_path(tmp_path)
    payload = request_path.read_text().replace(
        '"request_id": "request-1"', '"request_id": "../unsafe"'
    )
    request_path.write_text(payload)

    result = CliRunner().invoke(app, _command_args(tmp_path, request_path))

    assert result.exit_code == 2
    assert "safe path components" in result.output
    assert not (tmp_path / "activation").exists()
    assert not (tmp_path / "output").exists()


def _command_args(root: Path, request_path: Path) -> list[str]:
    return [
        "dry-run",
        "activated-target",
        "--request-path",
        str(request_path),
        "--activation-root",
        str(root / "activation"),
        "--output-root",
        str(root / "output"),
    ]


def _inspect_args(request_path: Path) -> list[str]:
    return [
        "dry-run",
        "inspect-activated-target",
        "--request-path",
        str(request_path),
    ]


def _request_path(
    root: Path,
    *,
    valid_until: datetime | None = None,
    open_order_ids: tuple[str, ...] = (),
) -> Path:
    inputs = root / "inputs"
    activation_rehearsal_root = inputs / "activation-rehearsal"
    activation_rehearsal = run_activation_consumption_local_rehearsal(
        rehearsal_id="operator-activation-rehearsal",
        output_root=activation_rehearsal_root,
        evaluated_at=_now(),
    )
    activation_rehearsal_path = (
        activation_rehearsal_root
        / "reports"
        / f"{activation_rehearsal.rehearsal_id}.json"
    )
    report_path = Path(activation_rehearsal.base_rehearsal_report_path)
    base_report_id = activation_rehearsal.base_rehearsal_id
    authorization = SemanticTargetActivationAuthorization(
        authorization_id="operator-authorization",
        revision=1,
        allowed_scopes=(SemanticTargetActivationScope.DRY_RUN,),
        orchestration_policy_version=SEMANTIC_TARGET_ORCHESTRATION_POLICY,
        rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
        rehearsal_id=base_report_id,
        rehearsal_report_sha256=rehearsal_report_sha256(report_path),
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now() - timedelta(seconds=1),
        valid_until=valid_until or _now() + timedelta(hours=1),
        issued_by="test-operator",
        reason="reviewed activated dry-run request",
        evidence_refs=("review:test",),
    )
    authorization_path = write_semantic_target_activation_authorization(
        authorization, inputs / "authorizations"
    )
    contributor_set = ContributorSet(
        contributor_set_id="operator-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="reviewed operator contributor ownership",
    )
    contributor_path = write_contributor_set(
        contributor_set, inputs / "contributor-sets"
    )
    decision = StrategyTargetDecision(
        decision_id="operator-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id="operator-input-bars",
        generated_at=_now(),
        effective_at=_now(),
        valid_until=_now() + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="reviewed operator target",
    )
    decision_path = write_strategy_target_decision(
        decision, inputs / "strategy-targets"
    )
    evaluation = StrategyEvaluation(
        evaluation_id="operator-strategy-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=_now(),
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="reviewed operator evaluation",
    )
    evaluation_path = write_strategy_evaluation(
        evaluation, inputs / "strategy-evaluations"
    )
    request = ActivatedDryRunOperatorRequest(
        request_id="request-1",
        activation_evaluation_id="operator-activation-evaluation",
        orchestration_id="operator-dry-run",
        authorization_path=str(authorization_path),
        rehearsal_report_path=str(report_path),
        activation_consumption_rehearsal_report_path=str(
            activation_rehearsal_path
        ),
        contributor_set_path=str(contributor_path),
        strategy_decision_paths=(str(decision_path),),
        strategy_evaluation_paths=(str(evaluation_path),),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id="operator-portfolio-target",
        portfolio_target_revision=1,
        risk_target_id="operator-risk-target",
        risk_target_revision=1,
        account=LiveAccountSnapshot(
            id="operator-account",
            broker_name="reviewed-local-snapshot",
            account_id="operator-local-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
            open_order_ids=open_order_ids,
            captured_at=_now(),
        ),
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=100,
        evaluated_at=_now(),
        evidence_refs=("operator-review:test",),
    )
    return write_activated_dry_run_operator_request(
        request, inputs / "requests"
    )


def _now() -> datetime:
    return datetime.now(UTC)
