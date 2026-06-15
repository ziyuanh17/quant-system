"""Run bounded autonomous semantic-target dry-runs without broker capability."""

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRecord,
    AutonomousDryRunRequest,
    AutonomousDryRunStatus,
)
from quant.models.execution import TradingMode, TradingSafetyCheck
from quant.models.execution_lifecycle import ExecutionDryRunStatus
from quant.models.workflow import SemanticTargetWorkflowStatus
from quant.operations import FileLock
from quant.research.portfolio_targets import aggregate_strategy_targets
from quant.workflows.semantic_targets import (
    run_semantic_target_dry_run_workflow,
)


def run_authorized_autonomous_dry_run(
    *,
    authorization: AutonomousDryRunAuthorization,
    request: AutonomousDryRunRequest,
    output_root: Path,
    run_at: datetime | None = None,
) -> AutonomousDryRunRecord:
    """Atomically claim and run one bounded, broker-free dry-run attempt."""
    current_time = run_at or datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("autonomous dry-run clock must be timezone-aware")
    _require_safe_component(authorization.authorization_id, "authorization ID")
    _require_safe_component(request.run_id, "run ID")
    request_digest = _model_sha256(request)
    record_path = output_root / "runs" / f"{request.run_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{authorization.authorization_id}.lock",
        lock_name=f"autonomous-dry-run:{authorization.authorization_id}",
        stale_after_seconds=300,
    ):
        _persist_or_verify_authorization(authorization, output_root)
        if record_path.exists():
            existing = load_autonomous_dry_run_record(record_path)
            if existing.request_sha256 != request_digest:
                raise ValueError(
                    "autonomous run ID is already bound to other inputs"
                )
            return existing

        issues = _authorization_issues(
            authorization, request, output_root, current_time
        )
        if issues:
            record = _blocked_record(
                authorization,
                request,
                request_digest,
                tuple(issues),
                current_time,
            )
            _write_model_exclusive(record_path, record)
            return record

        try:
            result = run_semantic_target_dry_run_workflow(
                orchestration_id=request.orchestration_id,
                contributor_set=request.contributor_set,
                strategy_decisions=request.strategy_decisions,
                strategy_evaluations=request.strategy_evaluations,
                risk_policy=request.risk_policy,
                portfolio_target_id=request.portfolio_target_id,
                portfolio_target_revision=request.portfolio_target_revision,
                risk_target_id=request.risk_target_id,
                risk_target_revision=request.risk_target_revision,
                account=request.account,
                policy=request.execution_policy,
                reference_price=request.reference_price,
                safety_check=TradingSafetyCheck(
                    mode=TradingMode.DRY_RUN,
                    allowed=True,
                ),
                output_root=output_root / "workflows",
                evaluated_at=current_time,
                evidence_refs=(
                    *request.evidence_refs,
                    "autonomous-authorization:"
                    f"{authorization.authorization_id}:"
                    f"{authorization.revision}",
                ),
            )
        except Exception as error:
            record = _blocked_record(
                authorization,
                request,
                request_digest,
                (f"dry-run workflow failed: {error}",),
                current_time,
            )
            _write_model_exclusive(record_path, record)
            return record
        workflow = result.record
        succeeded = (
            workflow.status == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
            and workflow.dry_run_status
            in {
                ExecutionDryRunStatus.WOULD_SUBMIT,
                ExecutionDryRunStatus.ALREADY_SATISFIED,
            }
        )
        record = AutonomousDryRunRecord(
            run_id=request.run_id,
            request_sha256=request_digest,
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            status=(
                AutonomousDryRunStatus.SUCCEEDED
                if succeeded
                else AutonomousDryRunStatus.BLOCKED
            ),
            evaluated_at=current_time,
            orchestration_id=workflow.orchestration_id,
            workflow_status=workflow.status.value,
            dry_run_status=(
                workflow.dry_run_status.value
                if workflow.dry_run_status is not None
                else None
            ),
            reason=(
                "authorized autonomous dry-run completed"
                if succeeded
                else f"autonomous dry-run halted: {workflow.reason}"
            ),
            evidence_refs=workflow.artifact_paths,
        )
        _write_model_exclusive(record_path, record)
        return record


def load_autonomous_dry_run_record(path: Path) -> AutonomousDryRunRecord:
    """Load one durable autonomous dry-run record."""
    return AutonomousDryRunRecord.model_validate_json(path.read_text())


def _authorization_issues(
    authorization: AutonomousDryRunAuthorization,
    request: AutonomousDryRunRequest,
    output_root: Path,
    run_at: datetime,
) -> list[str]:
    issues: list[str] = []
    if request.authorization_id != authorization.authorization_id or (
        request.authorization_revision != authorization.revision
    ):
        issues.append("request references another authorization revision")
    if run_at < authorization.effective_at:
        issues.append("authorization is not yet effective")
    if run_at >= authorization.valid_until:
        issues.append("authorization is expired")
    contributor_set = request.contributor_set
    if (
        contributor_set.contributor_set_id != authorization.contributor_set_id
        or contributor_set.revision != authorization.contributor_set_revision
    ):
        issues.append("contributor-set revision is not authorized")
    if contributor_set.symbol != authorization.symbol:
        issues.append("symbol is not authorized")
    expected = tuple(
        (item.strategy_id, item.strategy_version)
        for item in contributor_set.expected_contributors
    )
    if set(expected) != set(authorization.allowed_strategies):
        issues.append("contributor strategies are not authorized")
    for decision in request.strategy_decisions:
        if (
            (decision.strategy_id, decision.strategy_version)
            not in authorization.allowed_strategies
            or decision.symbol != authorization.symbol
        ):
            issues.append("a strategy decision is outside authorization")
    if request.account.broker_environment != TradingMode.DRY_RUN.value:
        issues.append("account snapshot is not marked dry_run")
    if (
        request.account.broker_name != authorization.broker_name
        or request.account.account_id != authorization.account_id
    ):
        issues.append("account identity is not authorized")
    if request.risk_policy.max_absolute_target is None or (
        request.risk_policy.max_absolute_target
        > authorization.max_absolute_target_shares
    ):
        issues.append("risk policy exceeds authorized target limit")

    prior = _prior_records(output_root, authorization)
    if len(prior) >= authorization.maximum_runs:
        issues.append("authorization maximum run count reached")
    if prior:
        latest = max(prior, key=lambda item: item.evaluated_at)
        elapsed = (run_at - latest.evaluated_at).total_seconds()
        if latest.status != AutonomousDryRunStatus.SUCCEEDED:
            issues.append("a prior autonomous run is blocked")
        if elapsed < authorization.minimum_interval_seconds:
            issues.append("minimum interval since prior run has not elapsed")

    portfolio = aggregate_strategy_targets(
        portfolio_target_id=request.portfolio_target_id,
        revision=request.portfolio_target_revision,
        contributor_set=contributor_set,
        decisions=request.strategy_decisions,
        evaluated_at=run_at,
    )
    if portfolio.aggregate_value is not None and (
        abs(portfolio.aggregate_value)
        > authorization.max_absolute_target_shares
    ):
        issues.append("aggregate target exceeds authorization limit")
    if (
        portfolio.aggregate_value is not None
        and portfolio.aggregate_value < 0
        and not authorization.allow_short_targets
    ):
        issues.append("short targets are not authorized")
    return issues


def _prior_records(
    output_root: Path,
    authorization: AutonomousDryRunAuthorization,
) -> tuple[AutonomousDryRunRecord, ...]:
    run_root = output_root / "runs"
    if not run_root.exists():
        return ()
    return tuple(
        record
        for path in sorted(run_root.glob("*.json"))
        if (
            record := load_autonomous_dry_run_record(path)
        ).authorization_id
        == authorization.authorization_id
        and record.authorization_revision == authorization.revision
    )


def _persist_or_verify_authorization(
    authorization: AutonomousDryRunAuthorization,
    output_root: Path,
) -> None:
    path = (
        output_root
        / "authorizations"
        / authorization.authorization_id
        / f"{authorization.revision}.json"
    )
    if path.exists():
        existing = AutonomousDryRunAuthorization.model_validate_json(
            path.read_text()
        )
        if existing != authorization:
            raise ValueError("immutable autonomous authorization conflicts")
        return
    _write_model_exclusive(path, authorization)


def _blocked_record(
    authorization: AutonomousDryRunAuthorization,
    request: AutonomousDryRunRequest,
    request_digest: str,
    issues: tuple[str, ...],
    run_at: datetime,
) -> AutonomousDryRunRecord:
    return AutonomousDryRunRecord(
        run_id=request.run_id,
        request_sha256=request_digest,
        authorization_id=authorization.authorization_id,
        authorization_revision=authorization.revision,
        status=AutonomousDryRunStatus.BLOCKED,
        evaluated_at=run_at,
        reason="; ".join(issues),
        evidence_refs=request.evidence_refs,
    )


def _model_sha256(model: BaseModel) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return sha256(payload).hexdigest()


def _write_model_exclusive(path: Path, model: BaseModel) -> None:
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


def _require_safe_component(value: str, label: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a safe path component")
