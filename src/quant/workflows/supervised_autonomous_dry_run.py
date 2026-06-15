"""Run a bounded API-only supervisor for recurring autonomous dry-runs."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from math import ceil
from pathlib import Path
from time import sleep

from pydantic import BaseModel

from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRequest,
    AutonomousDryRunStatus,
    SupervisedDryRunCycleEvent,
    SupervisedDryRunCycleOutcome,
    SupervisedDryRunHealthCheck,
    SupervisedDryRunHealthStatus,
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceRecord,
    SupervisedDryRunServiceStatus,
)
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import run_authorized_autonomous_dry_run

Clock = Callable[[], datetime]
HealthProvider = Callable[[int, datetime], SupervisedDryRunHealthCheck]
RequestProvider = Callable[[int, datetime], AutonomousDryRunRequest]
ShutdownCheck = Callable[[], bool]
Sleeper = Callable[[float], None]


def run_supervised_autonomous_dry_run_service(
    *,
    policy: SupervisedDryRunServicePolicy,
    authorization: AutonomousDryRunAuthorization,
    request_provider: RequestProvider,
    health_provider: HealthProvider,
    shutdown_requested: ShutdownCheck,
    output_root: Path,
    clock: Clock = lambda: datetime.now(UTC),
    sleeper: Sleeper = sleep,
) -> SupervisedDryRunServiceRecord:
    """Run healthy cycles until a bound or fail-closed stop is reached."""
    _validate_policy(policy, authorization)
    _require_safe_component(policy.service_id, "service ID")
    policy_digest = _model_sha256(policy)
    service_root = output_root / "services" / policy.service_id
    with FileLock(
        path=output_root / "locks" / f"{policy.service_id}.lock",
        lock_name=f"supervised-autonomous-dry-run:{policy.service_id}",
        stale_after_seconds=ceil(
            policy.maximum_runtime_seconds + policy.interval_seconds + 300
        ),
    ):
        _persist_or_verify_policy(policy, service_root)
        record_path = service_root / "record.json"
        if record_path.exists():
            record = load_supervised_dry_run_service_record(record_path)
            if record.policy_sha256 != policy_digest:
                raise ValueError(
                    "supervised service ID is bound to other inputs"
                )
            return record

        events = load_supervised_dry_run_cycle_events(
            service_root, policy.service_id, policy_digest
        )
        started_at = events[0].occurred_at if events else _aware_now(clock)
        terminal = _terminal_record_from_events(
            policy,
            authorization,
            policy_digest,
            service_root,
            events,
            started_at,
        )
        if terminal is not None:
            _write_model_exclusive(record_path, terminal)
            return terminal

        next_cycle = len(events) + 1
        while next_cycle <= policy.maximum_cycles:
            now = _aware_now(clock)
            if (
                now - started_at
            ).total_seconds() >= policy.maximum_runtime_seconds:
                event = _append_cycle_event(
                    service_root=service_root,
                    policy=policy,
                    policy_digest=policy_digest,
                    cycle_index=next_cycle,
                    occurred_at=now,
                    outcome=SupervisedDryRunCycleOutcome.RUNTIME_STOP,
                    reason="supervised service maximum runtime reached",
                )
                events = (*events, event)
                break
            if shutdown_requested():
                event = _append_cycle_event(
                    service_root=service_root,
                    policy=policy,
                    policy_digest=policy_digest,
                    cycle_index=next_cycle,
                    occurred_at=now,
                    outcome=SupervisedDryRunCycleOutcome.SHUTDOWN_STOP,
                    reason="explicit supervised service shutdown requested",
                )
                events = (*events, event)
                break
            try:
                health = health_provider(next_cycle, now)
                _validate_health_check(health, policy, next_cycle, now)
                health_path = _persist_or_verify_health_check(
                    service_root, health
                )
                if health.status != SupervisedDryRunHealthStatus.HEALTHY:
                    event = _append_cycle_event(
                        service_root=service_root,
                        policy=policy,
                        policy_digest=policy_digest,
                        cycle_index=next_cycle,
                        occurred_at=now,
                        outcome=SupervisedDryRunCycleOutcome.HEALTH_STOP,
                        reason=(
                            "supervised service stopped on "
                            f"{health.status.value} health"
                        ),
                        health_check_id=health.check_id,
                        evidence_refs=(str(health_path), *health.evidence_refs),
                    )
                    events = (*events, event)
                    break
                request = request_provider(next_cycle, now)
                _validate_request(request, authorization, events)
                run = run_authorized_autonomous_dry_run(
                    authorization=authorization,
                    request=request,
                    output_root=output_root / "autonomous",
                    run_at=now,
                )
                outcome = (
                    SupervisedDryRunCycleOutcome.SUCCEEDED
                    if run.status == AutonomousDryRunStatus.SUCCEEDED
                    else SupervisedDryRunCycleOutcome.BLOCKED
                )
                event = _append_cycle_event(
                    service_root=service_root,
                    policy=policy,
                    policy_digest=policy_digest,
                    cycle_index=next_cycle,
                    occurred_at=now,
                    outcome=outcome,
                    reason=run.reason,
                    health_check_id=health.check_id,
                    run_id=run.run_id,
                    run_status=run.status,
                    evidence_refs=(str(health_path), *run.evidence_refs),
                )
            except Exception as error:
                event = _append_cycle_event(
                    service_root=service_root,
                    policy=policy,
                    policy_digest=policy_digest,
                    cycle_index=next_cycle,
                    occurred_at=now,
                    outcome=SupervisedDryRunCycleOutcome.ERROR_STOP,
                    reason=f"supervised service cycle failed: {error}",
                )
            events = (*events, event)
            if event.outcome != SupervisedDryRunCycleOutcome.SUCCEEDED:
                break
            next_cycle += 1
            if (
                next_cycle <= policy.maximum_cycles
                and policy.interval_seconds > 0
            ):
                sleeper(policy.interval_seconds)

        record = _record_for_events(
            policy,
            authorization,
            policy_digest,
            service_root,
            events,
            started_at,
        )
        _write_model_exclusive(record_path, record)
        return record


def load_supervised_dry_run_cycle_events(
    service_root: Path,
    service_id: str,
    policy_sha256: str,
) -> tuple[SupervisedDryRunCycleEvent, ...]:
    """Load and validate the append-only supervised cycle history."""
    events = tuple(
        SupervisedDryRunCycleEvent.model_validate_json(path.read_text())
        for path in sorted((service_root / "events").glob("*.json"))
    )
    for sequence, event in enumerate(events, start=1):
        if event.sequence != sequence or event.cycle_index != sequence:
            raise ValueError(
                "supervised cycle event sequence is not contiguous"
            )
        if (
            event.service_id != service_id
            or event.policy_sha256 != policy_sha256
        ):
            raise ValueError(
                "supervised cycle event references another service"
            )
        if (
            sequence > 1
            and event.occurred_at < events[sequence - 2].occurred_at
        ):
            raise ValueError(
                "supervised cycle event timestamps are not monotonic"
            )
        if (
            sequence < len(events)
            and event.outcome != SupervisedDryRunCycleOutcome.SUCCEEDED
        ):
            raise ValueError("supervised cycle history continues after a stop")
    return events


def load_supervised_dry_run_service_record(
    path: Path,
) -> SupervisedDryRunServiceRecord:
    """Load one final supervised dry-run service summary."""
    return SupervisedDryRunServiceRecord.model_validate_json(path.read_text())


def _append_cycle_event(
    *,
    service_root: Path,
    policy: SupervisedDryRunServicePolicy,
    policy_digest: str,
    cycle_index: int,
    occurred_at: datetime,
    outcome: SupervisedDryRunCycleOutcome,
    reason: str,
    health_check_id: str | None = None,
    run_id: str | None = None,
    run_status: AutonomousDryRunStatus | None = None,
    evidence_refs: tuple[str, ...] = (),
) -> SupervisedDryRunCycleEvent:
    existing = load_supervised_dry_run_cycle_events(
        service_root, policy.service_id, policy_digest
    )
    sequence = len(existing) + 1
    if cycle_index != sequence:
        raise ValueError("supervised cycle index must follow durable history")
    if existing and occurred_at < existing[-1].occurred_at:
        raise ValueError("supervised cycle event timestamp moved backward")
    event = SupervisedDryRunCycleEvent(
        event_id=f"{policy.service_id}:{sequence:06d}",
        service_id=policy.service_id,
        policy_sha256=policy_digest,
        sequence=sequence,
        cycle_index=cycle_index,
        occurred_at=occurred_at,
        outcome=outcome,
        reason=reason,
        health_check_id=health_check_id,
        run_id=run_id,
        run_status=run_status,
        evidence_refs=evidence_refs,
    )
    _write_model_exclusive(
        service_root / "events" / f"{sequence:06d}.json", event
    )
    return event


def _record_for_events(
    policy: SupervisedDryRunServicePolicy,
    authorization: AutonomousDryRunAuthorization,
    policy_digest: str,
    service_root: Path,
    events: tuple[SupervisedDryRunCycleEvent, ...],
    started_at: datetime,
) -> SupervisedDryRunServiceRecord:
    completed = len(events) == policy.maximum_cycles and all(
        item.outcome == SupervisedDryRunCycleOutcome.SUCCEEDED
        for item in events
    )
    return SupervisedDryRunServiceRecord(
        service_id=policy.service_id,
        policy_sha256=policy_digest,
        authorization_id=authorization.authorization_id,
        authorization_revision=authorization.revision,
        status=(
            SupervisedDryRunServiceStatus.COMPLETED
            if completed
            else SupervisedDryRunServiceStatus.STOPPED
        ),
        completed_cycles=sum(
            item.outcome == SupervisedDryRunCycleOutcome.SUCCEEDED
            for item in events
        ),
        started_at=started_at,
        completed_at=events[-1].occurred_at,
        reason=(
            "supervised dry-run service completed its bounded cycle count"
            if completed
            else events[-1].reason
        ),
        cycle_event_paths=tuple(
            str(service_root / "events" / f"{item.sequence:06d}.json")
            for item in events
        ),
        run_ids=tuple(
            item.run_id for item in events if item.run_id is not None
        ),
    )


def _terminal_record_from_events(
    policy: SupervisedDryRunServicePolicy,
    authorization: AutonomousDryRunAuthorization,
    policy_digest: str,
    service_root: Path,
    events: tuple[SupervisedDryRunCycleEvent, ...],
    started_at: datetime,
) -> SupervisedDryRunServiceRecord | None:
    if not events:
        return None
    if (
        len(events) == policy.maximum_cycles
        or events[-1].outcome != SupervisedDryRunCycleOutcome.SUCCEEDED
    ):
        return _record_for_events(
            policy,
            authorization,
            policy_digest,
            service_root,
            events,
            started_at,
        )
    return None


def _validate_policy(
    policy: SupervisedDryRunServicePolicy,
    authorization: AutonomousDryRunAuthorization,
) -> None:
    if (
        policy.authorization_id != authorization.authorization_id
        or policy.authorization_revision != authorization.revision
    ):
        raise ValueError("supervised policy references another authorization")
    if policy.maximum_cycles > authorization.maximum_runs:
        raise ValueError("supervised cycles exceed authorization maximum runs")
    if (
        policy.maximum_cycles > 1
        and policy.interval_seconds < authorization.minimum_interval_seconds
    ):
        raise ValueError("supervised interval is below authorization minimum")


def _validate_health_check(
    health: SupervisedDryRunHealthCheck,
    policy: SupervisedDryRunServicePolicy,
    cycle_index: int,
    checked_at: datetime,
) -> None:
    if (
        health.service_id != policy.service_id
        or health.cycle_index != cycle_index
    ):
        raise ValueError("health check references another service cycle")
    if health.checked_at != checked_at:
        raise ValueError("health check timestamp must match cycle time")


def _validate_request(
    request: AutonomousDryRunRequest,
    authorization: AutonomousDryRunAuthorization,
    events: tuple[SupervisedDryRunCycleEvent, ...],
) -> None:
    if (
        request.authorization_id != authorization.authorization_id
        or request.authorization_revision != authorization.revision
    ):
        raise ValueError("fresh request references another authorization")
    prior_run_ids = {item.run_id for item in events if item.run_id is not None}
    if request.run_id in prior_run_ids:
        raise ValueError(
            "fresh request run ID was already used by this service"
        )


def _persist_or_verify_health_check(
    service_root: Path, health: SupervisedDryRunHealthCheck
) -> Path:
    _require_safe_component(health.check_id, "health check ID")
    path = service_root / "health-checks" / f"{health.check_id}.json"
    if path.exists():
        existing = SupervisedDryRunHealthCheck.model_validate_json(
            path.read_text()
        )
        if existing != health:
            raise ValueError("immutable supervised health check conflicts")
        return path
    _write_model_exclusive(path, health)
    return path


def _persist_or_verify_policy(
    policy: SupervisedDryRunServicePolicy, service_root: Path
) -> None:
    path = service_root / "policy.json"
    if path.exists():
        if (
            SupervisedDryRunServicePolicy.model_validate_json(path.read_text())
            != policy
        ):
            raise ValueError("immutable supervised service policy conflicts")
        return
    _write_model_exclusive(path, policy)


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("supervised dry-run clock must be timezone-aware")
    return value


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
