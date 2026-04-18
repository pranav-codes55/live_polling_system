#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="run"
if [[ "${1:-}" == "--setup-only" ]]; then
  MODE="setup"
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage: ./scripts/run_project.sh [--setup-only]"
  echo ""
  echo "Options:"
  echo "  --setup-only   Create venv and install deps only"
  echo ""
  echo "Environment overrides:"
  echo "  PYTHON_BIN     Python executable to use (default: python3)"
  echo "  HOST           UDP server host (default: 0.0.0.0)"
  echo "  PORT           UDP server port (default: 9999)"
  echo "  WEB_HOST       Dashboard host (default: 0.0.0.0)"
  echo "  WEB_PORT       Dashboard HTTP port (default: 8443)"
  exit 0
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9999}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-8443}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN not found in PATH."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

if [[ "$MODE" == "setup" ]]; then
  echo "Setup complete."
  echo "Run the server with: ./scripts/run_project.sh"
  exit 0
fi

echo "Starting UDP server on $HOST:$PORT and dashboard on http://$WEB_HOST:$WEB_PORT..."
exec python -m app.main server \
  --host "$HOST" \
  --port "$PORT" \
  --web-host "$WEB_HOST" \
  --web-port "$WEB_PORT"
