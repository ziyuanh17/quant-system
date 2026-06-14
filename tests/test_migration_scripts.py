"""Test migration scripts behavior and safety invariants."""

import subprocess
import tarfile
from pathlib import Path


def test_migration_audit_reports_secret_presence_without_values(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / ".env").write_text(
        "QUANT_ALPACA_PAPER_API_KEY=very-secret-key\n"
        "QUANT_ALPACA_PAPER_SECRET_KEY=very-secret-secret\n"
        "QUANT_BROKER=alpaca-paper\n"
    )

    result = subprocess.run(
        [
            "bash",
            "scripts/migration/audit_host.sh",
            str(runtime_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "QUANT_ALPACA_PAPER_API_KEY=present" in result.stdout
    assert "QUANT_ALPACA_PAPER_SECRET_KEY=present" in result.stdout
    assert "very-secret-key" not in result.stdout
    assert "very-secret-secret" not in result.stdout


def test_runtime_state_export_includes_operational_artifacts_not_secrets(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    output_dir = tmp_path / "output"
    (runtime_root / "data" / "live" / "reconciliation").mkdir(parents=True)
    (runtime_root / "data" / "workflows" / "alpaca-paper-refresh").mkdir(
        parents=True
    )
    (runtime_root / "logs").mkdir()
    (runtime_root / "site").mkdir()
    (runtime_root / ".env").write_text("SECRET=do-not-export\n")
    reconciliation_path = (
        runtime_root / "data" / "live" / "reconciliation" / "latest.json"
    )
    reconciliation_path.write_text('{"status":"passed"}\n')
    (
        runtime_root
        / "data"
        / "workflows"
        / "alpaca-paper-refresh"
        / "run.json"
    ).write_text('{"status":"succeeded"}\n')
    (runtime_root / "logs" / "wrapper.log").write_text("ok\n")
    (runtime_root / "site" / "status.json").write_text('{"status":"healthy"}\n')

    result = subprocess.run(
        [
            "bash",
            "scripts/migration/export_runtime_state.sh",
            str(runtime_root),
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    archive_path = Path(result.stdout.strip())
    assert archive_path.exists()
    assert archive_path.with_suffix(archive_path.suffix + ".sha256").exists()

    with tarfile.open(archive_path) as archive:
        names = set(archive.getnames())

    assert "data/live/reconciliation/latest.json" in names
    assert "data/workflows/alpaca-paper-refresh/run.json" in names
    assert "logs/wrapper.log" in names
    assert "site/status.json" in names
    assert ".env" not in names
