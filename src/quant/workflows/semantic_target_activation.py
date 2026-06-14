import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.activation import (
    ActivationDecision,
    ActivationEffectiveStatus,
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationEvaluation,
    SemanticTargetActivationScope,
)
from quant.operations import FileLock
from quant.workflows.semantic_target_rehearsal import (
    SEMANTIC_TARGET_REHEARSAL_POLICY,
    load_and_verify_semantic_target_rehearsal,
)

SEMANTIC_TARGET_ORCHESTRATION_POLICY = (
    "controlled_semantic_target_orchestration_v1"
)
SUPPORTED_ACTIVATION_SCOPES = frozenset(
    {
        SemanticTargetActivationScope.DRY_RUN,
        SemanticTargetActivationScope.SEMANTIC_PAPER,
    }
)


def rehearsal_report_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_semantic_target_activation_authorization(
    authorization: SemanticTargetActivationAuthorization,
    output_root: Path,
) -> Path:
    path = (
        output_root
        / "authorizations"
        / authorization.authorization_id
        / f"{authorization.revision}.json"
    )
    _write_model_exclusive(path, authorization)
    return path


def load_semantic_target_activation_authorization(
    path: Path,
) -> SemanticTargetActivationAuthorization:
    return SemanticTargetActivationAuthorization.model_validate_json(
        path.read_text()
    )


def evaluate_semantic_target_activation(
    *,
    evaluation_id: str,
    authorization: SemanticTargetActivationAuthorization,
    requested_scope: SemanticTargetActivationScope,
    rehearsal_report_path: Path,
    output_root: Path,
    evaluated_at: datetime,
) -> SemanticTargetActivationEvaluation:
    """Persist a fail-closed activation decision without activating a path."""
    _require_safe_component(evaluation_id, "evaluation ID")
    _require_safe_component(authorization.authorization_id, "authorization ID")
    _persist_or_verify_authorization(authorization, output_root)
    evaluation_path = output_root / "evaluations" / f"{evaluation_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{evaluation_id}.lock",
        lock_name=f"semantic-target-activation:{evaluation_id}",
        stale_after_seconds=300,
    ):
        if evaluation_path.exists():
            existing = load_semantic_target_activation_evaluation(
                evaluation_path
            )
            expected = _evaluate(
                evaluation_id=evaluation_id,
                authorization=authorization,
                requested_scope=requested_scope,
                rehearsal_report_path=rehearsal_report_path,
                evaluated_at=evaluated_at,
            )
            if existing != expected:
                raise ValueError(
                    "activation evaluation ID is already bound to other inputs"
                )
            return existing

        evaluation = _evaluate(
            evaluation_id=evaluation_id,
            authorization=authorization,
            requested_scope=requested_scope,
            rehearsal_report_path=rehearsal_report_path,
            evaluated_at=evaluated_at,
        )
        _write_model_exclusive(evaluation_path, evaluation)
        return evaluation


def load_semantic_target_activation_evaluation(
    path: Path,
) -> SemanticTargetActivationEvaluation:
    return SemanticTargetActivationEvaluation.model_validate_json(
        path.read_text()
    )


def _evaluate(
    *,
    evaluation_id: str,
    authorization: SemanticTargetActivationAuthorization,
    requested_scope: SemanticTargetActivationScope,
    rehearsal_report_path: Path,
    evaluated_at: datetime,
) -> SemanticTargetActivationEvaluation:
    issues: list[str] = []
    effective_status = _effective_status(authorization, evaluated_at)
    if effective_status != ActivationEffectiveStatus.ACTIVE:
        issues.append(f"authorization is {effective_status.value}")
    if requested_scope not in authorization.allowed_scopes:
        issues.append("requested scope is not authorized")
    if requested_scope not in SUPPORTED_ACTIVATION_SCOPES:
        issues.append("requested scope is not supported by activation gate v1")
    if (
        authorization.orchestration_policy_version
        != SEMANTIC_TARGET_ORCHESTRATION_POLICY
    ):
        issues.append("orchestration policy version is not supported")
    if (
        authorization.rehearsal_policy_version
        != SEMANTIC_TARGET_REHEARSAL_POLICY
    ):
        issues.append("rehearsal policy version is not supported")

    actual_digest = ""
    try:
        actual_digest = rehearsal_report_sha256(rehearsal_report_path)
        report = load_and_verify_semantic_target_rehearsal(
            rehearsal_report_path
        )
    except (OSError, ValueError) as error:
        issues.append(f"rehearsal evidence verification failed: {error}")
    else:
        if not report.passed:
            issues.append("rehearsal report did not pass")
        if report.rehearsal_id != authorization.rehearsal_id:
            issues.append("rehearsal identity does not match authorization")
        if (
            report.rehearsal_policy_version
            != authorization.rehearsal_policy_version
        ):
            issues.append("rehearsal policy does not match authorization")
        if actual_digest != authorization.rehearsal_report_sha256:
            issues.append(
                "rehearsal report digest does not match authorization"
            )

    return SemanticTargetActivationEvaluation(
        evaluation_id=evaluation_id,
        authorization_id=authorization.authorization_id,
        authorization_revision=authorization.revision,
        requested_scope=requested_scope,
        evaluated_at=evaluated_at,
        effective_status=effective_status,
        decision=(
            ActivationDecision.BLOCKED
            if issues
            else ActivationDecision.ALLOWED
        ),
        rehearsal_id=authorization.rehearsal_id,
        rehearsal_report_sha256=actual_digest or "0" * 64,
        issues=tuple(issues),
        evidence_refs=(
            str(rehearsal_report_path),
            *authorization.evidence_refs,
        ),
    )


def _effective_status(
    authorization: SemanticTargetActivationAuthorization,
    evaluated_at: datetime,
) -> ActivationEffectiveStatus:
    if evaluated_at < authorization.effective_at:
        return ActivationEffectiveStatus.NOT_YET_EFFECTIVE
    if evaluated_at >= authorization.valid_until:
        return ActivationEffectiveStatus.EXPIRED
    return ActivationEffectiveStatus.ACTIVE


def _persist_or_verify_authorization(
    authorization: SemanticTargetActivationAuthorization,
    output_root: Path,
) -> None:
    path = (
        output_root
        / "authorizations"
        / authorization.authorization_id
        / f"{authorization.revision}.json"
    )
    with FileLock(
        path=(
            output_root
            / "locks"
            / (
                f"{authorization.authorization_id}-"
                f"{authorization.revision}-authorization.lock"
            )
        ),
        lock_name=(
            f"semantic-target-authorization:{authorization.authorization_id}:"
            f"{authorization.revision}"
        ),
        stale_after_seconds=300,
    ):
        if path.exists():
            if load_semantic_target_activation_authorization(path) != (
                authorization
            ):
                raise ValueError(
                    "immutable activation authorization conflicts with input"
                )
            return
        write_semantic_target_activation_authorization(
            authorization, output_root
        )


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
