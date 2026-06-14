"""Execute reviewed activated dry-run operator requests."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from quant.models.activation import SemanticTargetActivationAuthorization
from quant.models.execution import TradingMode, TradingSafetyCheck
from quant.models.operator import ActivatedDryRunOperatorRequest
from quant.research.target_artifacts import (
    load_contributor_set,
    load_strategy_evaluation,
    load_strategy_target_decision,
)
from quant.workflows.activated_semantic_targets import (
    ActivatedSemanticTargetWorkflowResult,
    run_activated_semantic_target_dry_run_workflow,
)
from quant.workflows.activation_consumption_rehearsal import (
    load_and_verify_activation_consumption_rehearsal,
)
from quant.workflows.semantic_target_activation import rehearsal_report_sha256


@dataclass(frozen=True)
class ActivatedDryRunOperatorResult:
    request_artifact_path: Path
    activated_workflow: ActivatedSemanticTargetWorkflowResult


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


def load_activated_dry_run_operator_request(
    path: Path,
) -> ActivatedDryRunOperatorRequest:
    return ActivatedDryRunOperatorRequest.model_validate_json(path.read_text())


def write_activated_dry_run_operator_request(
    request: ActivatedDryRunOperatorRequest,
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


def _allowed_dry_run_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.DRY_RUN, allowed=True)


def _write_model_exclusive(
    path: Path, request: ActivatedDryRunOperatorRequest
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
