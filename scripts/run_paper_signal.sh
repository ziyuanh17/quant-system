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
data="${QUANT_DATA:-data/sample_prices.csv}"
quantity="${QUANT_QUANTITY:-1}"
initial_cash="${QUANT_INITIAL_CASH:-100000}"
iterations="${QUANT_ITERATIONS:-1}"
interval_seconds="${QUANT_INTERVAL_SECONDS:-0}"
min_rows="${QUANT_MIN_ROWS:-1}"
skip_validation="${QUANT_SKIP_VALIDATION:-false}"
state_path="${QUANT_STATE_PATH:-data/paper/state/default.json}"
signal_output_dir="${QUANT_SIGNAL_OUTPUT_DIR:-data/paper/signals}"
run_output_dir="${QUANT_RUN_OUTPUT_DIR:-data/scheduler/latest}"
log_dir="${QUANT_LOG_DIR:-logs}"

mkdir -p "$log_dir"
log_file="$log_dir/paper-signal-$(date -u +%Y%m%dT%H%M%SZ).log"

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "log_file=$log_file"
  echo "symbol=$symbol"
  echo "state_path=$state_path"

  command=(
    "$quant_cmd"
    "schedule"
    "paper-signal"
    "--strategy" "$strategy"
    "--data" "$data"
    "--symbol" "$symbol"
    "--quantity" "$quantity"
    "--initial-cash" "$initial_cash"
    "--iterations" "$iterations"
    "--interval-seconds" "$interval_seconds"
    "--min-rows" "$min_rows"
    "--state-path" "$state_path"
    "--signal-output-dir" "$signal_output_dir"
    "--run-output-dir" "$run_output_dir"
  )

  if [[ "$skip_validation" == "true" ]]; then
    command+=("--skip-validation")
  fi

  "${command[@]}"

  echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$log_file" 2>&1

cat "$log_file"
