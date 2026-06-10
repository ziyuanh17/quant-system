#!/usr/bin/env bash
set -euo pipefail

runtime_root="${1:-$PWD}"
env_path="$runtime_root/.env"

echo "hostname=$(hostname)"
echo "architecture=$(uname -m)"
echo "macos_version=$(sw_vers -productVersion 2>/dev/null || echo unavailable)"
echo "runtime_root=$runtime_root"
echo "runtime_root_present=$([[ -d "$runtime_root" ]] && echo true || echo false)"
echo "git_present=$([[ -d "$runtime_root/.git" ]] && echo true || echo false)"
echo "quant_present=$([[ -x "$runtime_root/.venv/bin/quant" ]] && echo true || echo false)"
echo "env_present=$([[ -f "$env_path" ]] && echo true || echo false)"

# Report only whether required keys exist. Never print secret values.
for key in \
  QUANT_ALPACA_PAPER_API_KEY \
  QUANT_ALPACA_PAPER_SECRET_KEY \
  QUANT_BROKER \
  QUANT_MAX_ORDER_NOTIONAL \
  QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN
do
  if [[ -f "$env_path" ]] && grep -q "^${key}=" "$env_path"; then
    echo "$key=present"
  else
    echo "$key=missing"
  fi
done

