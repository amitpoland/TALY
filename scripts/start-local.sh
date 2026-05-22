#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/app-data/run"
LOG_DIR="$ROOT_DIR/app-data/logs"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
APP_PORT="${TALY_PORT:-8010}"
BACKEND_URL="http://127.0.0.1:${APP_PORT}/health"
APP_URL="http://127.0.0.1:${APP_PORT}/"

mkdir -p "$RUN_DIR" "$LOG_DIR"
cd "$ROOT_DIR"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Stopping existing local process on port $port..."
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local log_file="$3"
  local attempts=40
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is ready: $url"
      return 0
    fi
    sleep 0.5
  done
  echo "$name did not become ready. Last log lines:"
  tail -40 "$log_file" || true
  return 1
}

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  echo "Missing backend virtual environment: $ROOT_DIR/.venv"
  echo "Create/install the backend environment before starting TALY."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not available. Install Node.js/npm before starting TALY."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$ROOT_DIR/frontend" && npm install)
fi

echo "Building frontend..."
(cd "$ROOT_DIR/frontend" && npm run build)

echo "Seeding local foundation data..."
PYTHONPATH=backend "$ROOT_DIR/.venv/bin/python" -m app.commands.seed

if is_running "$BACKEND_PID_FILE"; then
  echo "Restarting managed backend on PID $(cat "$BACKEND_PID_FILE")..."
  kill "$(cat "$BACKEND_PID_FILE")" 2>/dev/null || true
  rm -f "$BACKEND_PID_FILE"
  sleep 1
fi

if port_in_use "$APP_PORT"; then
  stop_port "$APP_PORT"
fi

echo "Starting backend..."
nohup env PYTHONPATH=backend "$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$APP_PORT" >"$LOG_DIR/backend.log" 2>&1 &
echo $! > "$BACKEND_PID_FILE"

wait_for_url "$BACKEND_URL" "Backend" "$LOG_DIR/backend.log"

echo
echo "TALY is running:"
echo "  App:     $APP_URL"
echo "  Backend: http://127.0.0.1:${APP_PORT}"
echo
echo "Logs:"
echo "  $LOG_DIR/backend.log"
echo

if command -v open >/dev/null 2>&1; then
  open "$APP_URL"
fi
