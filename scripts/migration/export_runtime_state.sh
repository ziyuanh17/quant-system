#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "usage: $0 RUNTIME_ROOT OUTPUT_DIR" >&2
  exit 2
fi

runtime_root="$1"
output_dir="$2"

if [[ ! -d "$runtime_root" ]]; then
  echo "runtime root does not exist: $runtime_root" >&2
  exit 1
fi

mkdir -p "$output_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive_path="$output_dir/quant-runtime-state-$timestamp.tar.gz"

# Export only operational history needed for continuity and diagnosis.
# Secrets, virtual environments, source code, and reproducible market-data
# caches are intentionally excluded.
candidate_paths=(
  "data/live"
  "data/workflows/alpaca-paper-refresh"
  "logs"
  "site/status.json"
)
existing_paths=()
for path in "${candidate_paths[@]}"; do
  if [[ -e "$runtime_root/$path" ]]; then
    existing_paths+=("$path")
  fi
done

if [[ "${#existing_paths[@]}" -eq 0 ]]; then
  echo "no runtime artifacts found under: $runtime_root" >&2
  exit 1
fi

tar -czf "$archive_path" -C "$runtime_root" "${existing_paths[@]}"
shasum -a 256 "$archive_path" > "$archive_path.sha256"

echo "$archive_path"

