import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from quant.models.execution_lifecycle import (
    BrokerOrderLookupEvidence,
    ExecutionDriftObservation,
    ExecutionDryRunObservation,
    ExecutionEvent,
    ExecutionPlan,
    ExecutionPlanStatus,
)
from quant.operations import FileLock

_ALLOWED_TRANSITIONS: dict[ExecutionPlanStatus, set[ExecutionPlanStatus]] = {
    ExecutionPlanStatus.PLANNED: {
        ExecutionPlanStatus.SUBMISSION_PENDING,
        ExecutionPlanStatus.BLOCKED,
        ExecutionPlanStatus.SATISFIED,
    },
    ExecutionPlanStatus.SUBMISSION_PENDING: {
        ExecutionPlanStatus.SUBMITTED,
        ExecutionPlanStatus.AMBIGUOUS,
        ExecutionPlanStatus.BLOCKED,
    },
    ExecutionPlanStatus.SUBMITTED: {
        ExecutionPlanStatus.FILLED,
        ExecutionPlanStatus.REJECTED,
        ExecutionPlanStatus.CANCELLED,
        ExecutionPlanStatus.AMBIGUOUS,
    },
    ExecutionPlanStatus.AMBIGUOUS: {
        ExecutionPlanStatus.SUBMITTED,
        ExecutionPlanStatus.BLOCKED,
    },
    ExecutionPlanStatus.FILLED: {
        ExecutionPlanStatus.FILLED,
        ExecutionPlanStatus.SATISFIED,
    },
    ExecutionPlanStatus.REJECTED: set(),
    ExecutionPlanStatus.CANCELLED: set(),
    ExecutionPlanStatus.BLOCKED: set(),
    ExecutionPlanStatus.SATISFIED: set(),
}


def claim_execution_plan_exclusive(
    plan: ExecutionPlan,
    artifact_root: Path,
) -> Path:
    """Atomically claim one risk-target revision before broker interaction."""
    _require_safe_component(plan.risk_target_id)
    claim_key = _risk_target_revision_key(
        plan.risk_target_id, plan.risk_target_revision
    )
    lock_path = artifact_root / "locks" / f"{claim_key}.lock"
    with FileLock(
        path=lock_path,
        lock_name=f"execution-plan:{claim_key}",
        stale_after_seconds=300,
    ):
        path = execution_plan_path(
            artifact_root,
            plan.risk_target_id,
            plan.risk_target_revision,
        )
        _write_model_exclusive(path, plan)
    return path


def execution_plan_path(
    artifact_root: Path,
    risk_target_id: str,
    risk_target_revision: int,
) -> Path:
    _require_safe_component(risk_target_id)
    if risk_target_revision < 1:
        raise ValueError("risk target revision must be positive")
    filename = (
        f"{_risk_target_revision_key(risk_target_id, risk_target_revision)}"
        ".json"
    )
    return artifact_root / "plans" / filename


def load_execution_plan(path: Path) -> ExecutionPlan:
    return ExecutionPlan.model_validate_json(path.read_text())


def append_execution_event(
    *,
    plan: ExecutionPlan,
    artifact_root: Path,
    new_status: ExecutionPlanStatus,
    occurred_at: datetime,
    reason: str,
    evidence_refs: tuple[str, ...] = (),
    broker_order_ids: tuple[str, ...] = (),
) -> ExecutionEvent:
    _require_safe_component(plan.execution_plan_id)
    lock_path = (
        artifact_root / "locks" / f"{plan.execution_plan_id}-events.lock"
    )
    with FileLock(
        path=lock_path,
        lock_name=f"execution-events:{plan.execution_plan_id}",
        stale_after_seconds=300,
    ):
        events = load_execution_events(artifact_root, plan.execution_plan_id)
        previous_status = (
            events[-1].new_status if events else plan.initial_status
        )
        previous_time = events[-1].occurred_at if events else plan.created_at
        if occurred_at < previous_time:
            raise ValueError("execution event timestamps must be monotonic")
        if new_status not in _ALLOWED_TRANSITIONS[previous_status]:
            raise ValueError(
                f"invalid execution transition: {previous_status.value} "
                f"-> {new_status.value}"
            )
        sequence = len(events) + 1
        event = ExecutionEvent(
            event_id=f"{plan.execution_plan_id}:{sequence:06d}",
            execution_plan_id=plan.execution_plan_id,
            sequence=sequence,
            previous_status=previous_status,
            new_status=new_status,
            occurred_at=occurred_at,
            reason=reason,
            evidence_refs=evidence_refs,
            broker_order_ids=broker_order_ids,
        )
        path = _event_dir(artifact_root, plan.execution_plan_id) / (
            f"{sequence:06d}.json"
        )
        _write_model_exclusive(path, event)
    return event


def load_execution_events(
    artifact_root: Path,
    execution_plan_id: str,
) -> tuple[ExecutionEvent, ...]:
    events = tuple(
        ExecutionEvent.model_validate_json(path.read_text())
        for path in sorted(
            _event_dir(artifact_root, execution_plan_id).glob("*.json")
        )
    )
    submitted_broker_order_id: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence:
            raise ValueError("execution event sequence is not contiguous")
        if event.execution_plan_id != execution_plan_id:
            raise ValueError("execution event references another plan")
        if expected_sequence == 1:
            if event.previous_status != ExecutionPlanStatus.PLANNED:
                raise ValueError("first execution event must follow planned")
        else:
            previous = events[expected_sequence - 2]
            if event.previous_status != previous.new_status:
                raise ValueError("execution event status chain is invalid")
            if event.occurred_at < previous.occurred_at:
                raise ValueError("execution event timestamps are not monotonic")
        if event.new_status not in _ALLOWED_TRANSITIONS[event.previous_status]:
            raise ValueError("execution event transition is invalid")
        if event.new_status == ExecutionPlanStatus.SUBMITTED:
            broker_order_id = event.broker_order_ids[0]
            if (
                submitted_broker_order_id is not None
                and broker_order_id != submitted_broker_order_id
            ):
                raise ValueError("submitted broker order identity changed")
            submitted_broker_order_id = broker_order_id
        if (
            submitted_broker_order_id is not None
            and event.broker_order_ids
            and any(
                broker_order_id != submitted_broker_order_id
                for broker_order_id in event.broker_order_ids
            )
        ):
            raise ValueError("execution event references another broker order")
    return events


def current_execution_status(
    plan: ExecutionPlan,
    artifact_root: Path,
) -> ExecutionPlanStatus:
    events = load_execution_events(artifact_root, plan.execution_plan_id)
    return events[-1].new_status if events else plan.initial_status


def write_broker_lookup_evidence(
    evidence: BrokerOrderLookupEvidence,
    artifact_root: Path,
) -> Path:
    _require_safe_component(evidence.execution_plan_id)
    _require_safe_component(evidence.evidence_id)
    path = (
        artifact_root
        / "recovery-evidence"
        / evidence.execution_plan_id
        / f"{evidence.evidence_id}.json"
    )
    _write_model_exclusive(path, evidence)
    return path


def load_broker_lookup_evidence(path: Path) -> BrokerOrderLookupEvidence:
    return BrokerOrderLookupEvidence.model_validate_json(path.read_text())


def write_execution_drift_observation(
    observation: ExecutionDriftObservation,
    artifact_root: Path,
) -> Path:
    _require_safe_component(observation.execution_plan_id)
    _require_safe_component(observation.observation_id)
    path = (
        artifact_root
        / "drift-observations"
        / observation.execution_plan_id
        / f"{observation.observation_id}.json"
    )
    _write_model_exclusive(path, observation)
    return path


def load_execution_drift_observation(path: Path) -> ExecutionDriftObservation:
    return ExecutionDriftObservation.model_validate_json(path.read_text())


def write_execution_dry_run_observation(
    observation: ExecutionDryRunObservation,
    artifact_root: Path,
) -> Path:
    path = execution_dry_run_observation_path(
        artifact_root,
        observation.execution_plan_id,
        observation.observation_id,
    )
    _write_model_exclusive(path, observation)
    return path


def execution_dry_run_observation_path(
    artifact_root: Path,
    execution_plan_id: str,
    observation_id: str,
) -> Path:
    _require_safe_component(execution_plan_id)
    _require_safe_component(observation_id)
    return (
        artifact_root
        / "dry-run-observations"
        / execution_plan_id
        / f"{observation_id}.json"
    )


def load_execution_dry_run_observation(
    path: Path,
) -> ExecutionDryRunObservation:
    return ExecutionDryRunObservation.model_validate_json(path.read_text())


def _event_dir(artifact_root: Path, execution_plan_id: str) -> Path:
    _require_safe_component(execution_plan_id)
    return artifact_root / "events" / execution_plan_id


def _require_safe_component(value: str) -> None:
    if value in {".", ".."} or Path(value).name != value:
        raise ValueError("artifact identity must be one safe path component")


def _risk_target_revision_key(risk_target_id: str, revision: int) -> str:
    return f"{risk_target_id}-r{revision}"


def _write_model_exclusive(path: Path, model: BaseModel) -> None:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(descriptor, "wb") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
