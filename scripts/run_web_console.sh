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

auth_mode="${QUANT_CONSOLE_AUTH_MODE:-api_key}"
case "$auth_mode" in
  api_key)
    if [[ -z "${QUANT_CONSOLE_API_KEY:-}" ]]; then
      echo "QUANT_CONSOLE_API_KEY is required in api_key mode" >&2
      exit 1
    fi
    ;;
  tailscale)
    if [[ -z "${QUANT_CONSOLE_TAILSCALE_USERS:-}" ]]; then
      echo "QUANT_CONSOLE_TAILSCALE_USERS is required in tailscale mode" >&2
      exit 1
    fi
    ;;
  *)
    echo "Unsupported deployed console auth mode: $auth_mode" >&2
    exit 1
    ;;
esac

quant_cmd="${QUANT_CMD:-.venv/bin/quant}"
host="${QUANT_CONSOLE_HOST:-127.0.0.1}"
port="${QUANT_CONSOLE_PORT:-8000}"

exec "$quant_cmd" web serve --host "$host" --port "$port"
