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
initial_cash="${QUANT_INITIAL_CASH:-100000}"
iterations="${QUANT_ITERATIONS:-1}"
interval_seconds="${QUANT_INTERVAL_SECONDS:-0}"
min_rows="${QUANT_MIN_ROWS:-1}"
state_path="${QUANT_STATE_PATH:-data/paper/state/default.json}"
signal_output_dir="${QUANT_SIGNAL_OUTPUT_DIR:-data/paper/signals}"
run_output_dir="${QUANT_RUN_OUTPUT_DIR:-data/scheduler/latest}"
raw_dir="${QUANT_RAW_DIR:-data/raw}"
normalized_dir="${QUANT_NORMALIZED_DIR:-data/normalized}"
validation_dir="${QUANT_VALIDATION_DIR:-data/validation}"
metadata_dir="${QUANT_METADATA_DIR:-data/metadata}"
workflow_output_dir="${QUANT_WORKFLOW_OUTPUT_DIR:-data/workflows/paper-signal-refresh}"
log_dir="${QUANT_LOG_DIR:-logs}"

mkdir -p "$log_dir"
log_file="$log_dir/paper-signal-refresh-$(date -u +%Y%m%dT%H%M%SZ).log"

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "log_file=$log_file"
  echo "symbol=$symbol"
  echo "provider=$provider"
  echo "start=$start"
  echo "state_path=$state_path"

  command=(
    "$quant_cmd"
    "workflow"
    "paper-signal-refresh"
    "--strategy" "$strategy"
    "--provider" "$provider"
    "--symbol" "$symbol"
    "--start" "$start"
    "--quantity" "$quantity"
    "--initial-cash" "$initial_cash"
    "--iterations" "$iterations"
    "--interval-seconds" "$interval_seconds"
    "--min-rows" "$min_rows"
    "--state-path" "$state_path"
    "--signal-output-dir" "$signal_output_dir"
    "--run-output-dir" "$run_output_dir"
    "--raw-dir" "$raw_dir"
    "--normalized-dir" "$normalized_dir"
    "--validation-dir" "$validation_dir"
    "--metadata-dir" "$metadata_dir"
    "--workflow-output-dir" "$workflow_output_dir"
  )

  if [[ -n "$end" ]]; then
    command+=("--end" "$end")
  fi

  "${command[@]}"

  echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$log_file" 2>&1

cat "$log_file"
