#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/app-data/run"

stop_pid_file() {
  local label="$1"
  local pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "$label is not managed by this launcher."
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $label on PID $pid..."
    kill "$pid" 2>/dev/null || true
  else
    echo "$label PID $pid is not running."
  fi
  rm -f "$pid_file"
}

stop_pid_file "backend" "$RUN_DIR/backend.pid"

echo "Done."
