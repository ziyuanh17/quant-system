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
