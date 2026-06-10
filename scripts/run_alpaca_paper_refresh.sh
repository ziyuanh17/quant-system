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
min_rows="${QUANT_MIN_ROWS:-1}"
raw_dir="${QUANT_RAW_DIR:-data/raw}"
normalized_dir="${QUANT_NORMALIZED_DIR:-data/normalized}"
validation_dir="${QUANT_VALIDATION_DIR:-data/validation}"
metadata_dir="${QUANT_METADATA_DIR:-data/metadata}"
log_dir="${QUANT_LOG_DIR:-logs}"
lock_stale_after_seconds="${QUANT_LOCK_STALE_AFTER_SECONDS:-7200}"

alpaca_paper_workflow_output_dir="${QUANT_ALPACA_PAPER_WORKFLOW_OUTPUT_DIR:-data/workflows/alpaca-paper-refresh}"
alpaca_paper_lock_path="${QUANT_ALPACA_PAPER_LOCK_PATH:-data/locks/alpaca-paper-refresh.lock}"
alpaca_paper_order_output_dir="${QUANT_ALPACA_PAPER_ORDER_OUTPUT_DIR:-data/live/orders}"
alpaca_paper_fill_output_dir="${QUANT_ALPACA_PAPER_FILL_OUTPUT_DIR:-data/live/fills}"
alpaca_paper_snapshot_output_dir="${QUANT_ALPACA_PAPER_SNAPSHOT_OUTPUT_DIR:-data/live/account_snapshots}"
alpaca_paper_reconciliation_output_path="${QUANT_ALPACA_PAPER_RECONCILIATION_OUTPUT_PATH:-data/live/reconciliation/latest.json}"
alpaca_paper_cash_tolerance="${QUANT_ALPACA_PAPER_CASH_TOLERANCE:-0.01}"
alpaca_paper_order_poll_attempts="${QUANT_ALPACA_PAPER_ORDER_POLL_ATTEMPTS:-5}"
alpaca_paper_order_poll_interval_seconds="${QUANT_ALPACA_PAPER_ORDER_POLL_INTERVAL_SECONDS:-1}"
alpaca_paper_publish_status_after_run="${QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN:-false}"
alpaca_paper_publish_status_path="${QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH:-site/status.json}"
alpaca_paper_publish_status_fail_on_failed="${QUANT_ALPACA_PAPER_PUBLISH_STATUS_FAIL_ON_FAILED:-false}"
alpaca_paper_preflight_only="${QUANT_ALPACA_PAPER_PREFLIGHT_ONLY:-false}"

mkdir -p "$log_dir"
log_file="$log_dir/alpaca-paper-refresh-$(date -u +%Y%m%dT%H%M%SZ).log"
wrapper_exit_code=0

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "log_file=$log_file"
  echo "symbol=$symbol"
  echo "provider=$provider"
  echo "start=$start"
  echo "workflow_output_dir=$alpaca_paper_workflow_output_dir"
  echo "order_output_dir=$alpaca_paper_order_output_dir"
  echo "reconciliation_output_path=$alpaca_paper_reconciliation_output_path"
  echo "lock_path=$alpaca_paper_lock_path"
  echo "publish_status_after_run=$alpaca_paper_publish_status_after_run"
  echo "preflight_only=$alpaca_paper_preflight_only"

  # Preflight mode lets a server install or cron edit verify the resolved
  # wrapper configuration without refreshing data or submitting a paper order.
  if [[ "$alpaca_paper_preflight_only" == "true" ]]; then
    echo "preflight completed without broker submission"
  else
    command=(
      "$quant_cmd"
      "workflow"
      "alpaca-paper-refresh"
      "--from-env"
      "--strategy" "$strategy"
      "--provider" "$provider"
      "--symbol" "$symbol"
      "--start" "$start"
      "--quantity" "$quantity"
      "--min-rows" "$min_rows"
      "--raw-dir" "$raw_dir"
      "--normalized-dir" "$normalized_dir"
      "--validation-dir" "$validation_dir"
      "--metadata-dir" "$metadata_dir"
      "--workflow-output-dir" "$alpaca_paper_workflow_output_dir"
      "--order-output-dir" "$alpaca_paper_order_output_dir"
      "--fill-output-dir" "$alpaca_paper_fill_output_dir"
      "--snapshot-output-dir" "$alpaca_paper_snapshot_output_dir"
      "--reconciliation-output-path" "$alpaca_paper_reconciliation_output_path"
      "--cash-tolerance" "$alpaca_paper_cash_tolerance"
      "--order-poll-attempts" "$alpaca_paper_order_poll_attempts"
      "--order-poll-interval-seconds" "$alpaca_paper_order_poll_interval_seconds"
      "--lock-path" "$alpaca_paper_lock_path"
      "--lock-stale-after-seconds" "$lock_stale_after_seconds"
    )

    if [[ -n "$end" ]]; then
      command+=("--end" "$end")
    fi

    "${command[@]}" || wrapper_exit_code=$?

    if [[ "$alpaca_paper_publish_status_after_run" == "true" ]]; then
      publish_command=(
        "$quant_cmd"
        "ops"
        "publish-status"
        "--output-path" "$alpaca_paper_publish_status_path"
        "--logs-dir" "$log_dir"
        # This wrapper is the Alpaca paper lane. Skip older local
        # paper/dry-run checks so inactive artifacts do not mask a healthy
        # broker-connected paper run.
        "--no-check-paper-service"
        "--no-check-comparison"
        "--check-alpaca-paper"
        "--alpaca-paper-workflow-records-dir" "$alpaca_paper_workflow_output_dir"
        "--alpaca-paper-reconciliation-report-path" "$alpaca_paper_reconciliation_output_path"
      )

      if [[ "$alpaca_paper_publish_status_fail_on_failed" == "true" ]]; then
        publish_command+=("--fail-on-failed")
      fi

      publish_exit_code=0
      "${publish_command[@]}" || publish_exit_code=$?
      if [[ "$wrapper_exit_code" -eq 0 && "$publish_exit_code" -ne 0 ]]; then
        wrapper_exit_code="$publish_exit_code"
      fi
    fi
  fi

  echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$log_file" 2>&1

cat "$log_file"
exit "$wrapper_exit_code"
