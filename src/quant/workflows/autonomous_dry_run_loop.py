"""Run a finite manually started autonomous semantic-target dry-run loop."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import sleep

from pydantic import BaseModel

from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunLoopManifest,
    AutonomousDryRunLoopRecord,
    AutonomousDryRunRequest,
    AutonomousDryRunStatus,
)
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
    load_autonomous_dry_run_request,
    run_authorized_autonomous_dry_run,
)

Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


def run_finite_autonomous_dry_run_loop(
    *,
    manifest_path: Path,
    output_root: Path,
    clock: Clock = lambda: datetime.now(UTC),
    sleeper: Sleeper = sleep,
) -> AutonomousDryRunLoopRecord:
    """Run one exact finite request list and stop on the first block."""
    manifest = load_autonomous_dry_run_loop_manifest(manifest_path)
    _require_safe_component(manifest.loop_id, "loop ID")
    manifest_digest = _model_sha256(manifest)
    record_path = output_root / "loops" / f"{manifest.loop_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{manifest.loop_id}.lock",
        lock_name=f"finite-autonomous-dry-run-loop:{manifest.loop_id}",
        stale_after_seconds=300,
    ):
        _persist_or_verify_manifest(manifest, output_root)
        if record_path.exists():
            record = load_autonomous_dry_run_loop_record(record_path)
            if record.manifest_sha256 != manifest_digest:
                raise ValueError(
                    "finite-loop ID is already bound to other inputs"
                )
            return record

        authorization_path = Path(manifest.authorization_path)
        if _file_sha256(authorization_path) != manifest.authorization_sha256:
            raise ValueError("finite-loop authorization hash does not match")
        authorization = load_autonomous_dry_run_authorization(
            authorization_path
        )
        requests = []
        for index, request_path_value in enumerate(manifest.request_paths):
            request_path = Path(request_path_value)
            if _file_sha256(request_path) != manifest.request_sha256s[index]:
                raise ValueError("finite-loop request hash does not match")
            requests.append(load_autonomous_dry_run_request(request_path))
        _validate_manifest_scope(manifest, authorization, requests)

        started_at = _aware_now(clock)
        records = []
        for index, request in enumerate(requests):
            record = run_authorized_autonomous_dry_run(
                authorization=authorization,
                request=request,
                output_root=output_root / "autonomous",
                run_at=_aware_now(clock),
            )
            records.append(record)
            if record.status == AutonomousDryRunStatus.BLOCKED:
                break
            if (
                index < len(requests) - 1
                and manifest.interval_seconds > 0
            ):
                sleeper(manifest.interval_seconds)

        stopped_early = len(records) < len(manifest.request_paths)
        blocked = bool(records) and (
            records[-1].status == AutonomousDryRunStatus.BLOCKED
        )
        result = AutonomousDryRunLoopRecord(
            loop_id=manifest.loop_id,
            manifest_sha256=manifest_digest,
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            status=(
                AutonomousDryRunStatus.BLOCKED
                if blocked
                else AutonomousDryRunStatus.SUCCEEDED
            ),
            requested_run_count=len(manifest.request_paths),
            completed_run_ids=tuple(item.run_id for item in records),
            run_statuses=tuple(item.status for item in records),
            started_at=started_at,
            completed_at=_aware_now(clock),
            stopped_early=stopped_early,
            reason=(
                f"finite loop stopped after blocked run: {records[-1].reason}"
                if blocked
                else "finite autonomous dry-run loop completed"
            ),
            run_record_paths=tuple(
                str(
                    output_root
                    / "autonomous"
                    / "runs"
                    / f"{item.run_id}.json"
                )
                for item in records
            ),
        )
        _write_model_exclusive(record_path, result)
        return result


def load_autonomous_dry_run_loop_manifest(
    path: Path,
) -> AutonomousDryRunLoopManifest:
    """Load one finite autonomous dry-run loop manifest."""
    return AutonomousDryRunLoopManifest.model_validate_json(path.read_text())


def load_autonomous_dry_run_loop_record(
    path: Path,
) -> AutonomousDryRunLoopRecord:
    """Load one durable finite autonomous dry-run loop summary."""
    return AutonomousDryRunLoopRecord.model_validate_json(path.read_text())


def write_autonomous_dry_run_loop_manifest(
    manifest: AutonomousDryRunLoopManifest,
    output_root: Path,
) -> Path:
    """Write one immutable finite autonomous dry-run loop manifest."""
    _require_safe_component(manifest.loop_id, "loop ID")
    path = output_root / f"{manifest.loop_id}.json"
    _write_model_exclusive(path, manifest)
    return path


def autonomous_dry_run_loop_manifest_for_paths(
    *,
    loop_id: str,
    authorization_path: Path,
    request_paths: tuple[Path, ...],
    interval_seconds: float,
    created_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> AutonomousDryRunLoopManifest:
    """Build a finite-loop manifest bound to exact input file contents."""
    return AutonomousDryRunLoopManifest(
        loop_id=loop_id,
        authorization_path=str(authorization_path),
        authorization_sha256=_file_sha256(authorization_path),
        request_paths=tuple(str(path) for path in request_paths),
        request_sha256s=tuple(_file_sha256(path) for path in request_paths),
        interval_seconds=interval_seconds,
        created_at=created_at,
        evidence_refs=evidence_refs,
    )


def _persist_or_verify_manifest(
    manifest: AutonomousDryRunLoopManifest,
    output_root: Path,
) -> None:
    path = output_root / "manifests" / f"{manifest.loop_id}.json"
    if path.exists():
        if load_autonomous_dry_run_loop_manifest(path) != manifest:
            raise ValueError("immutable finite-loop manifest conflicts")
        return
    _write_model_exclusive(path, manifest)


def _validate_manifest_scope(
    manifest: AutonomousDryRunLoopManifest,
    authorization: AutonomousDryRunAuthorization,
    requests: list[AutonomousDryRunRequest],
) -> None:
    if len(requests) > authorization.maximum_runs:
        raise ValueError("finite-loop request count exceeds authorization")
    if (
        len(requests) > 1
        and manifest.interval_seconds < authorization.minimum_interval_seconds
    ):
        raise ValueError("finite-loop interval is below authorization minimum")
    run_ids = tuple(item.run_id for item in requests)
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("finite-loop request run IDs must be unique")
    if any(
        item.authorization_id != authorization.authorization_id
        or item.authorization_revision != authorization.revision
        for item in requests
    ):
        raise ValueError("finite-loop request references another authorization")


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "finite autonomous dry-run clock must be timezone-aware"
        )
    return value


def _model_sha256(model: BaseModel) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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
