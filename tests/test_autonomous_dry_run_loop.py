"""Test the finite manually started autonomous dry-run loop."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quant.cli import app
from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRequest,
    AutonomousDryRunStatus,
)
from quant.models.execution import LiveAccountSnapshot
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
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
from quant.workflows import (
    autonomous_dry_run_loop_manifest_for_paths,
    run_finite_autonomous_dry_run_loop,
    write_autonomous_dry_run_authorization,
    write_autonomous_dry_run_loop_manifest,
    write_autonomous_dry_run_request,
)


def test_finite_loop_completes_exact_request_list_and_sleeps(tmp_path) -> None:
    manifest_path = _manifest_path(
        tmp_path,
        requests=(
            _request("run-1", _now()),
            _request("run-2", _now() + timedelta(minutes=5)),
        ),
        interval_seconds=30,
    )
    sleeps: list[float] = []
    clock = _Clock(
        _now(),
        _now(),
        _now() + timedelta(minutes=5),
        _now() + timedelta(minutes=5),
    )

    record = run_finite_autonomous_dry_run_loop(
        manifest_path=manifest_path,
        output_root=tmp_path / "output",
        clock=clock,
        sleeper=sleeps.append,
    )

    assert record.status == AutonomousDryRunStatus.SUCCEEDED
    assert record.completed_run_ids == ("run-1", "run-2")
    assert sleeps == [30]
    assert len(tuple((tmp_path / "output" / "loops").glob("*.json"))) == 1
    assert not (tmp_path / "output" / "orders").exists()
    assert not (tmp_path / "output" / "fills").exists()


def test_finite_loop_stops_immediately_after_block(tmp_path) -> None:
    manifest_path = _manifest_path(
        tmp_path,
        requests=(
            _request("blocked", _now(), open_order_ids=("working-1",)),
            _request("must-not-run", _now() + timedelta(minutes=5)),
        ),
    )

    record = run_finite_autonomous_dry_run_loop(
        manifest_path=manifest_path,
        output_root=tmp_path / "output",
        clock=_Clock(_now(), _now(), _now()),
        sleeper=lambda _: None,
    )

    assert record.status == AutonomousDryRunStatus.BLOCKED
    assert record.stopped_early
    assert record.completed_run_ids == ("blocked",)
    assert not (
        tmp_path / "output" / "autonomous" / "runs" / "must-not-run.json"
    ).exists()


def test_finite_loop_restart_returns_one_durable_summary(tmp_path) -> None:
    manifest_path = _manifest_path(
        tmp_path, requests=(_request("run-1", _now()),)
    )
    output_root = tmp_path / "output"

    first = run_finite_autonomous_dry_run_loop(
        manifest_path=manifest_path,
        output_root=output_root,
        clock=_Clock(_now(), _now(), _now()),
        sleeper=lambda _: None,
    )
    second = run_finite_autonomous_dry_run_loop(
        manifest_path=manifest_path,
        output_root=output_root,
        clock=_Clock(_now() + timedelta(hours=1)),
        sleeper=lambda _: None,
    )

    assert first == second
    assert len(tuple((output_root / "loops").glob("*.json"))) == 1
    assert len(tuple((output_root / "autonomous" / "runs").glob("*.json"))) == 1


def test_finite_loop_rejects_tampered_request_before_any_run(tmp_path) -> None:
    manifest_path = _manifest_path(
        tmp_path,
        requests=(
            _request("run-1", _now()),
            _request("run-2", _now() + timedelta(minutes=5)),
        ),
    )
    request_path = tmp_path / "inputs" / "requests" / "run-2.json"
    request_path.write_text(request_path.read_text().replace('"2"', '"3"', 1))

    with pytest.raises(ValueError, match="request hash does not match"):
        run_finite_autonomous_dry_run_loop(
            manifest_path=manifest_path,
            output_root=tmp_path / "output",
            clock=_Clock(_now()),
            sleeper=lambda _: None,
        )

    assert not (tmp_path / "output" / "autonomous").exists()


def test_finite_loop_rejects_interval_below_authorization_before_run(
    tmp_path,
) -> None:
    now = _now()
    inputs = tmp_path / "inputs"
    authorization = _authorization(now).model_copy(
        update={"minimum_interval_seconds": 60}
    )
    authorization_path = write_autonomous_dry_run_authorization(
        authorization, inputs / "authorizations"
    )
    request_paths = tuple(
        write_autonomous_dry_run_request(request, inputs / "requests")
        for request in (
            _request("run-1", now),
            _request("run-2", now + timedelta(minutes=5)),
        )
    )
    manifest_path = write_autonomous_dry_run_loop_manifest(
        autonomous_dry_run_loop_manifest_for_paths(
            loop_id="finite-loop-1",
            authorization_path=authorization_path,
            request_paths=request_paths,
            interval_seconds=0,
            created_at=now,
        ),
        inputs / "manifests",
    )

    with pytest.raises(ValueError, match="interval is below"):
        run_finite_autonomous_dry_run_loop(
            manifest_path=manifest_path,
            output_root=tmp_path / "output",
            clock=_Clock(now),
            sleeper=lambda _: None,
        )

    assert not (tmp_path / "output" / "autonomous").exists()


def test_finite_loop_cli_runs_only_manifest_bounded_dry_runs(tmp_path) -> None:
    now = datetime.now(UTC)
    manifest_path = _manifest_path(
        tmp_path,
        requests=(_request("cli-run", now),),
        now=now,
    )
    output_root = tmp_path / "output"

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "autonomous-finite-loop",
            "--manifest-path",
            str(manifest_path),
            "--output-root",
            str(output_root),
        ],
    )

    assert result.exit_code == 0
    assert "Status: succeeded" in result.output
    assert "Completed: 1/1" in result.output
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()


def test_finite_loop_cli_stops_and_exits_nonzero_on_block(tmp_path) -> None:
    now = datetime.now(UTC)
    manifest_path = _manifest_path(
        tmp_path,
        requests=(
            _request("blocked", now, open_order_ids=("working-1",)),
            _request("must-not-run", now + timedelta(minutes=5)),
        ),
        now=now,
    )
    output_root = tmp_path / "output"

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "autonomous-finite-loop",
            "--manifest-path",
            str(manifest_path),
            "--output-root",
            str(output_root),
        ],
    )

    assert result.exit_code == 1
    assert "Status: blocked" in result.output
    assert "Completed: 1/2" in result.output
    assert not (
        output_root / "autonomous" / "runs" / "must-not-run.json"
    ).exists()


def test_finite_loop_cli_has_no_unbounded_or_broker_selector() -> None:
    result = CliRunner().invoke(
        app, ["dry-run", "autonomous-finite-loop", "--help"]
    )

    assert result.exit_code == 0
    assert "--manifest-path" in result.output
    assert "--output-root" in result.output
    assert "--iterations" not in result.output
    assert "--mode" not in result.output
    assert "broker" not in result.output.lower()
    assert "alpaca" not in result.output.lower()
    assert "paper" not in result.output.lower()


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)


def _manifest_path(
    root: Path,
    *,
    requests: tuple[AutonomousDryRunRequest, ...],
    interval_seconds: float = 0,
    now: datetime | None = None,
) -> Path:
    inputs = root / "inputs"
    current = now or _now()
    authorization_path = write_autonomous_dry_run_authorization(
        _authorization(current), inputs / "authorizations"
    )
    request_paths = tuple(
        write_autonomous_dry_run_request(request, inputs / "requests")
        for request in requests
    )
    manifest = autonomous_dry_run_loop_manifest_for_paths(
        loop_id="finite-loop-1",
        authorization_path=authorization_path,
        request_paths=request_paths,
        interval_seconds=interval_seconds,
        created_at=current,
    )
    return write_autonomous_dry_run_loop_manifest(
        manifest, inputs / "manifests"
    )


def _authorization(now: datetime) -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id="finite-loop-authorization",
        revision=1,
        symbol="AAPL",
        contributor_set_id="finite-loop-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="finite-loop-dry-run",
        account_id="finite-loop-account",
        max_absolute_target_shares=Decimal("10"),
        maximum_runs=10,
        minimum_interval_seconds=0,
        issued_at=now - timedelta(minutes=1),
        effective_at=now - timedelta(seconds=1),
        valid_until=now + timedelta(hours=1),
        issued_by="test-deployment-review",
        reason="finite autonomous dry-run loop test",
        evidence_refs=("review:test",),
    )


def _request(
    run_id: str,
    evaluated_at: datetime,
    *,
    open_order_ids: tuple[str, ...] = (),
) -> AutonomousDryRunRequest:
    decision = StrategyTargetDecision(
        decision_id=f"{run_id}-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"{run_id}-input",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="finite-loop test target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"{run_id}-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="finite-loop test evaluation",
    )
    return AutonomousDryRunRequest(
        run_id=run_id,
        authorization_id="finite-loop-authorization",
        authorization_revision=1,
        orchestration_id=f"{run_id}-orchestration",
        contributor_set=ContributorSet(
            contributor_set_id="finite-loop-contributors",
            revision=1,
            symbol="AAPL",
            unit=TargetUnit.SHARES,
            expected_contributors=(
                ContributorSpec(strategy_id="momentum", strategy_version="2"),
            ),
            max_age_seconds=3600,
            portfolio_policy_version="sum_active_targets_v1",
            reason="finite-loop test ownership",
        ),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id=f"{run_id}-portfolio",
        portfolio_target_revision=1,
        risk_target_id=f"{run_id}-risk",
        risk_target_revision=1,
        account=LiveAccountSnapshot(
            id=f"{run_id}-account",
            broker_name="finite-loop-dry-run",
            account_id="finite-loop-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
            open_order_ids=open_order_ids,
            captured_at=evaluated_at,
        ),
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=100,
        evaluated_at=evaluated_at,
    )


def _now() -> datetime:
    return datetime(2026, 6, 15, 20, tzinfo=UTC)
