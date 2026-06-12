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

if [[ -z "${QUANT_CONSOLE_API_KEY:-}" ]]; then
  echo "QUANT_CONSOLE_API_KEY is required for the deployed console" >&2
  exit 1
fi

quant_cmd="${QUANT_CMD:-.venv/bin/quant}"
host="${QUANT_CONSOLE_HOST:-127.0.0.1}"
port="${QUANT_CONSOLE_PORT:-8000}"

exec "$quant_cmd" web serve --host "$host" --port "$port"
