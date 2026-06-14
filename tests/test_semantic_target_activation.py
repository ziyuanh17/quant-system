from datetime import UTC, datetime, timedelta

import pytest

from quant.models.activation import (
    ActivationDecision,
    ActivationEffectiveStatus,
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationScope,
)
from quant.workflows import (
    SEMANTIC_TARGET_ORCHESTRATION_POLICY,
    SEMANTIC_TARGET_REHEARSAL_POLICY,
    evaluate_semantic_target_activation,
    load_semantic_target_activation_authorization,
    rehearsal_report_sha256,
    run_semantic_target_local_rehearsal,
    write_semantic_target_activation_authorization,
)


def test_activation_allows_reviewed_local_scopes_and_is_restart_safe(
    tmp_path,
) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)
    output_root = tmp_path / "activation"

    first = evaluate_semantic_target_activation(
        evaluation_id="evaluation-dry-run",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=report_path,
        output_root=output_root,
        evaluated_at=_now(),
    )
    second = evaluate_semantic_target_activation(
        evaluation_id="evaluation-dry-run",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=report_path,
        output_root=output_root,
        evaluated_at=_now(),
    )

    assert first == second
    assert first.decision == ActivationDecision.ALLOWED
    assert first.effective_status == ActivationEffectiveStatus.ACTIVE
    assert first.issues == ()
    assert len(tuple((output_root / "evaluations").glob("*.json"))) == 1
    assert len(tuple((output_root / "authorizations").rglob("*.json"))) == 1


def test_activation_v1_blocks_alpaca_even_when_authorized(tmp_path) -> None:
    report_path, authorization = _authorized_rehearsal(
        tmp_path,
        scopes=(SemanticTargetActivationScope.ALPACA_PAPER,),
    )

    evaluation = evaluate_semantic_target_activation(
        evaluation_id="evaluation-alpaca",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.ALPACA_PAPER,
        rehearsal_report_path=report_path,
        output_root=tmp_path / "activation",
        evaluated_at=_now(),
    )

    assert evaluation.decision == ActivationDecision.BLOCKED
    assert "not supported by activation gate v1" in evaluation.issues[0]


@pytest.mark.parametrize(
    ("evaluated_at", "expected_status"),
    (
        (
            datetime(2026, 6, 13, 14, 59, tzinfo=UTC),
            ActivationEffectiveStatus.NOT_YET_EFFECTIVE,
        ),
        (
            datetime(2026, 6, 14, 15, tzinfo=UTC),
            ActivationEffectiveStatus.EXPIRED,
        ),
    ),
)
def test_activation_blocks_outside_authorization_interval(
    tmp_path,
    evaluated_at,
    expected_status,
) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)

    evaluation = evaluate_semantic_target_activation(
        evaluation_id=f"evaluation-{expected_status.value}",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=report_path,
        output_root=tmp_path / "activation",
        evaluated_at=evaluated_at,
    )

    assert evaluation.decision == ActivationDecision.BLOCKED
    assert evaluation.effective_status == expected_status


def test_activation_durably_blocks_changed_rehearsal_report(tmp_path) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)
    report_path.write_text(
        report_path.read_text().replace(
            '"passed": true', '"passed": false', 1
        )
    )

    evaluation = evaluate_semantic_target_activation(
        evaluation_id="evaluation-tampered",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=report_path,
        output_root=tmp_path / "activation",
        evaluated_at=_now(),
    )

    assert evaluation.decision == ActivationDecision.BLOCKED
    assert any("verification failed" in issue for issue in evaluation.issues)
    assert (
        tmp_path / "activation" / "evaluations" / "evaluation-tampered.json"
    ).is_file()


def test_activation_durably_blocks_missing_rehearsal_evidence(tmp_path) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)
    evidence_path = next(
        (tmp_path / "rehearsal" / "scenarios").rglob("orchestrations/*.json")
    )
    evidence_path.unlink()

    evaluation = evaluate_semantic_target_activation(
        evaluation_id="evaluation-missing-evidence",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.SEMANTIC_PAPER,
        rehearsal_report_path=report_path,
        output_root=tmp_path / "activation",
        evaluated_at=_now(),
    )

    assert evaluation.decision == ActivationDecision.BLOCKED
    assert any("evidence is missing" in issue for issue in evaluation.issues)


@pytest.mark.parametrize(
    ("authorization_update", "expected_issue"),
    (
        (
            {"orchestration_policy_version": "unsupported-orchestration"},
            "orchestration policy version is not supported",
        ),
        (
            {"rehearsal_policy_version": "unsupported-rehearsal"},
            "rehearsal policy version is not supported",
        ),
        (
            {"rehearsal_report_sha256": "f" * 64},
            "rehearsal report digest does not match authorization",
        ),
    ),
)
def test_activation_blocks_policy_or_digest_mismatch(
    tmp_path,
    authorization_update,
    expected_issue,
) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)
    changed = authorization.model_copy(update=authorization_update)

    evaluation = evaluate_semantic_target_activation(
        evaluation_id="evaluation-mismatch",
        authorization=changed,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=report_path,
        output_root=tmp_path / "activation",
        evaluated_at=_now(),
    )

    assert evaluation.decision == ActivationDecision.BLOCKED
    assert expected_issue in evaluation.issues


def test_activation_authorization_is_immutable(tmp_path) -> None:
    _, authorization = _authorized_rehearsal(tmp_path)
    output_root = tmp_path / "activation"
    path = write_semantic_target_activation_authorization(
        authorization, output_root
    )

    assert load_semantic_target_activation_authorization(path) == authorization
    with pytest.raises(FileExistsError):
        write_semantic_target_activation_authorization(
            authorization, output_root
        )


def test_activation_evaluation_identity_cannot_be_reused(tmp_path) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)
    output_root = tmp_path / "activation"
    evaluate_semantic_target_activation(
        evaluation_id="evaluation-1",
        authorization=authorization,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        rehearsal_report_path=report_path,
        output_root=output_root,
        evaluated_at=_now(),
    )

    with pytest.raises(ValueError, match="already bound"):
        evaluate_semantic_target_activation(
            evaluation_id="evaluation-1",
            authorization=authorization,
            requested_scope=SemanticTargetActivationScope.SEMANTIC_PAPER,
            rehearsal_report_path=report_path,
            output_root=output_root,
            evaluated_at=_now(),
        )


def test_activation_rejects_unsafe_evaluation_identity(tmp_path) -> None:
    report_path, authorization = _authorized_rehearsal(tmp_path)

    with pytest.raises(ValueError, match="safe path component"):
        evaluate_semantic_target_activation(
            evaluation_id="../unsafe",
            authorization=authorization,
            requested_scope=SemanticTargetActivationScope.DRY_RUN,
            rehearsal_report_path=report_path,
            output_root=tmp_path / "activation",
            evaluated_at=_now(),
        )


def test_activation_authorization_requires_timezone_aware_dates() -> None:
    with pytest.raises(ValueError, match="timezone"):
        SemanticTargetActivationAuthorization(
            authorization_id="authorization-1",
            revision=1,
            allowed_scopes=(SemanticTargetActivationScope.DRY_RUN,),
            orchestration_policy_version=SEMANTIC_TARGET_ORCHESTRATION_POLICY,
            rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
            rehearsal_id="rehearsal-1",
            rehearsal_report_sha256="f" * 64,
            issued_at=datetime(2026, 6, 13, 14, 59),
            effective_at=datetime(2026, 6, 13, 15),
            valid_until=datetime(2026, 6, 14, 15),
            issued_by="test-operator",
            reason="test",
            evidence_refs=("review:test",),
        )


def _authorized_rehearsal(
    root,
    *,
    scopes: tuple[SemanticTargetActivationScope, ...] = (
        SemanticTargetActivationScope.DRY_RUN,
        SemanticTargetActivationScope.SEMANTIC_PAPER,
    ),
):
    rehearsal_root = root / "rehearsal"
    report = run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-activation-1",
        output_root=rehearsal_root,
        evaluated_at=_now(),
    )
    report_path = rehearsal_root / "reports" / f"{report.rehearsal_id}.json"
    authorization = SemanticTargetActivationAuthorization(
        authorization_id="authorization-1",
        revision=1,
        allowed_scopes=scopes,
        orchestration_policy_version=SEMANTIC_TARGET_ORCHESTRATION_POLICY,
        rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
        rehearsal_id=report.rehearsal_id,
        rehearsal_report_sha256=rehearsal_report_sha256(report_path),
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now(),
        valid_until=_now() + timedelta(days=1),
        issued_by="test-operator",
        reason="reviewed local activation boundary",
        evidence_refs=("review:test",),
    )
    return report_path, authorization


def _now() -> datetime:
    return datetime(2026, 6, 13, 15, tzinfo=UTC)
