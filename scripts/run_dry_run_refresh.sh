#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

quant_cmd="${QUANT_CMD:-.venv/bin/quant}"
strategy="${QUANT_STRATEGY:-momentum}"
symbol="${QUANT_SYMBOL:-AAPL}"
provider="${QUANT_PROVIDER:-yfinance}"
start="${QUANT_START:-2024-01-01}"
end="${QUANT_END:-}"
quantity="${QUANT_QUANTITY:-1}"
iterations="${QUANT_ITERATIONS:-1}"
interval_seconds="${QUANT_INTERVAL_SECONDS:-0}"
min_rows="${QUANT_MIN_ROWS:-1}"
raw_dir="${QUANT_RAW_DIR:-data/raw}"
normalized_dir="${QUANT_NORMALIZED_DIR:-data/normalized}"
validation_dir="${QUANT_VALIDATION_DIR:-data/validation}"
metadata_dir="${QUANT_METADATA_DIR:-data/metadata}"
signal_output_dir="${QUANT_SIGNAL_OUTPUT_DIR:-data/paper/signals}"
state_path="${QUANT_STATE_PATH:-data/paper/state/default.json}"
log_dir="${QUANT_LOG_DIR:-logs}"

dry_run_output_dir="${QUANT_DRY_RUN_OUTPUT_DIR:-data/dry_run/orders}"
dry_run_run_output_dir="${QUANT_DRY_RUN_RUN_OUTPUT_DIR:-data/scheduler/dry-run}"
dry_run_workflow_output_dir="${QUANT_DRY_RUN_WORKFLOW_OUTPUT_DIR:-data/workflows/dry-run-refresh}"
dry_run_lock_path="${QUANT_DRY_RUN_LOCK_PATH:-data/locks/dry-run-refresh.lock}"
dry_run_comparison_output_path="${QUANT_DRY_RUN_COMPARISON_OUTPUT_PATH:-data/dry_run/comparison/latest.json}"
dry_run_broker_name="${QUANT_DRY_RUN_BROKER_NAME:-dry-run}"
dry_run_publish_status_path="${QUANT_DRY_RUN_PUBLISH_STATUS_PATH:-}"
dry_run_health_run_records_dir="${QUANT_DRY_RUN_HEALTH_RUN_RECORDS_DIR:-}"
lock_stale_after_seconds="${QUANT_LOCK_STALE_AFTER_SECONDS:-7200}"

mkdir -p "$log_dir"
log_file="$log_dir/dry-run-refresh-$(date -u +%Y%m%dT%H%M%SZ).log"

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "log_file=$log_file"
  echo "symbol=$symbol"
  echo "provider=$provider"
  echo "start=$start"
  echo "dry_run_output_dir=$dry_run_output_dir"
  echo "comparison_output_path=$dry_run_comparison_output_path"
  echo "lock_path=$dry_run_lock_path"

  command=(
    "$quant_cmd"
    "workflow"
    "dry-run-refresh"
    "--strategy" "$strategy"
    "--provider" "$provider"
    "--symbol" "$symbol"
    "--start" "$start"
    "--quantity" "$quantity"
    "--broker-name" "$dry_run_broker_name"
    "--iterations" "$iterations"
    "--interval-seconds" "$interval_seconds"
    "--min-rows" "$min_rows"
    "--raw-dir" "$raw_dir"
    "--normalized-dir" "$normalized_dir"
    "--validation-dir" "$validation_dir"
    "--metadata-dir" "$metadata_dir"
    "--workflow-output-dir" "$dry_run_workflow_output_dir"
    "--dry-run-output-dir" "$dry_run_output_dir"
    "--run-output-dir" "$dry_run_run_output_dir"
    "--paper-signal-dir" "$signal_output_dir"
    "--comparison-output-path" "$dry_run_comparison_output_path"
    "--paper-state-path" "$state_path"
    "--logs-dir" "$log_dir"
    "--lock-path" "$dry_run_lock_path"
    "--lock-stale-after-seconds" "$lock_stale_after_seconds"
  )

  if [[ -n "$end" ]]; then
    command+=("--end" "$end")
  fi

  if [[ -n "$dry_run_publish_status_path" ]]; then
    command+=("--publish-status-path" "$dry_run_publish_status_path")
  fi

  if [[ -n "$dry_run_health_run_records_dir" ]]; then
    command+=("--health-run-records-dir" "$dry_run_health_run_records_dir")
  fi

  "${command[@]}"

  echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$log_file" 2>&1

cat "$log_file"
