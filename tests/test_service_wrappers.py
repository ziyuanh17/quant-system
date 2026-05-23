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
