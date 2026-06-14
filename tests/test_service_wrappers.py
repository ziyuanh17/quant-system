"""Test service wrappers behavior and safety invariants."""

import subprocess
from pathlib import Path


def test_dry_run_refresh_wrapper_uses_dry_run_workflow() -> None:
    script = Path("scripts/run_dry_run_refresh.sh").read_text()

    assert '"dry-run-refresh"' in script
    assert (
        'dry_run_output_dir="${QUANT_DRY_RUN_OUTPUT_DIR:-data/dry_run/orders}"'
        in script
    )
    assert (
        'dry_run_workflow_output_dir="${QUANT_DRY_RUN_WORKFLOW_OUTPUT_DIR:-'
        'data/workflows/dry-run-refresh}"'
    ) in script
    assert (
        'dry_run_comparison_output_path="${QUANT_DRY_RUN_COMPARISON_OUTPUT_PATH:-'
        'data/dry_run/comparison/latest.json}"'
    ) in script
    assert '"--publish-status-path" "$dry_run_publish_status_path"' in script
    assert (
        '"--health-run-records-dir" "$dry_run_health_run_records_dir"'
        in script
    )


def test_alpaca_paper_refresh_wrapper_uses_explicit_workflow() -> None:
    script_path = Path("scripts/run_alpaca_paper_refresh.sh")
    script = script_path.read_text()

    assert script_path.stat().st_mode & 0o111
    assert '"alpaca-paper-refresh"' in script
    assert '"--from-env"' in script
    assert (
        'alpaca_paper_workflow_output_dir="${'
        'QUANT_ALPACA_PAPER_WORKFLOW_OUTPUT_DIR:-'
        'data/workflows/alpaca-paper-refresh}"'
    ) in script
    assert (
        'alpaca_paper_lock_path="${QUANT_ALPACA_PAPER_LOCK_PATH:-'
        'data/locks/alpaca-paper-refresh.lock}"'
    ) in script
    assert (
        'alpaca_paper_order_output_dir="${QUANT_ALPACA_PAPER_ORDER_OUTPUT_DIR:-'
        'data/live/orders}"'
    ) in script
    assert (
        'alpaca_paper_reconciliation_output_path="${'
        'QUANT_ALPACA_PAPER_RECONCILIATION_OUTPUT_PATH:-'
        'data/live/reconciliation/latest.json}"'
    ) in script
    assert 'log_file="$log_dir/alpaca-paper-refresh-' in script


def test_alpaca_paper_refresh_wrapper_can_publish_dashboard_status() -> None:
    script = Path("scripts/run_alpaca_paper_refresh.sh").read_text()

    assert (
        'alpaca_paper_publish_status_after_run="${'
        'QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN:-false}"'
    ) in script
    assert (
        'alpaca_paper_publish_status_path="${'
        'QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH:-site/status.json}"'
    ) in script
    assert '"publish-status"' in script
    assert '"--check-alpaca-paper"' in script
    assert '"--no-check-paper-service"' in script
    assert '"--no-check-comparison"' in script
    assert (
        '"--alpaca-paper-workflow-records-dir" '
        '"$alpaca_paper_workflow_output_dir"'
    ) in script
    assert (
        '"--alpaca-paper-reconciliation-report-path" '
        '"$alpaca_paper_reconciliation_output_path"'
    ) in script


def test_alpaca_paper_refresh_wrapper_has_preflight_only_mode() -> None:
    script = Path("scripts/run_alpaca_paper_refresh.sh").read_text()

    assert (
        'alpaca_paper_preflight_only="${'
        'QUANT_ALPACA_PAPER_PREFLIGHT_ONLY:-false}"'
    ) in script
    assert 'preflight_only=$alpaca_paper_preflight_only' in script
    assert 'if [[ "$alpaca_paper_preflight_only" == "true" ]]; then' in script
    assert "preflight completed without broker submission" in script


def test_alpaca_paper_refresh_wrapper_publishes_status_after_failure(
    tmp_path,
) -> None:
    wrapper_path = tmp_path / "scripts" / "run_alpaca_paper_refresh.sh"
    wrapper_path.parent.mkdir()
    wrapper_path.write_text(
        Path("scripts/run_alpaca_paper_refresh.sh").read_text()
    )
    fake_quant = tmp_path / "fake-quant.sh"
    calls_path = tmp_path / "calls.log"
    fake_quant.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$CALLS_PATH"\n'
        '[[ "$*" == *"workflow alpaca-paper-refresh"* ]] && exit 1\n'
        "exit 0\n"
    )
    fake_quant.chmod(0o755)

    result = subprocess.run(
        ["bash", str(wrapper_path)],
        env={
            "PATH": "/usr/bin:/bin",
            "CALLS_PATH": str(calls_path),
            "QUANT_CMD": str(fake_quant),
            "QUANT_LOG_DIR": str(tmp_path / "logs"),
            "QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN": "true",
            "QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH": str(
                tmp_path / "site" / "status.json"
            ),
        },
        capture_output=True,
        text=True,
    )

    calls = calls_path.read_text()
    assert result.returncode == 1
    assert "workflow alpaca-paper-refresh" in calls
    assert "ops publish-status" in calls
