#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="run"
if [[ "${1:-}" == "--setup-only" ]]; then
  MODE="setup"
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage: ./scripts/run_full_system.sh [--setup-only]"
  echo ""
  echo "Starts UDP server, Flask dashboard, and WebSocket proxy"
  echo ""
  echo "Environment overrides:"
  echo "  PYTHON_BIN     Python executable to use (default: python3)"
  echo "  NODE_BIN       Node.js executable to use (default: node)"
  echo "  HOST           UDP server host (default: 0.0.0.0)"
  echo "  PORT           UDP server port (default: 9999)"
  echo "  WEB_HOST       Dashboard host (default: 0.0.0.0)"
  echo "  WEB_PORT       Dashboard HTTP port (default: 8443)"
  echo "  WS_PORT        WebSocket proxy port (default: 9001)"
  exit 0
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_BIN="${NODE_BIN:-node}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9999}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-8443}"
WS_PORT="${WS_PORT:-9001}"

PROXY_UDP_HOST="$HOST"
if [[ "$PROXY_UDP_HOST" == "0.0.0.0" ]]; then
  PROXY_UDP_HOST="127.0.0.1"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN not found in PATH."
  exit 1
fi

if ! command -v "$NODE_BIN" >/dev/null 2>&1; then
  echo "Error: $NODE_BIN not found in PATH."
  exit 1
fi

# Setup Python environment
if [[ ! -d ".venv" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

# Setup Node.js dependencies
if [[ ! -d "node_modules" ]]; then
  echo "Installing Node.js dependencies..."
  npm install
fi

if [[ "$MODE" == "setup" ]]; then
  echo "Setup complete."
  echo "Run the full system with: ./scripts/run_full_system.sh"
  exit 0
fi

# Cleanup function
cleanup() {
  echo ""
  echo "Shutting down all services..."
  kill %1 %2 %3 2>/dev/null || true
  wait %1 %2 %3 2>/dev/null || true
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting Live Polling System with Node.js proxy..."
echo ""
echo "UDP Server:       $HOST:$PORT"
echo "Dashboard:        http://$WEB_HOST:$WEB_PORT"
echo "WebSocket Proxy:  ws://0.0.0.0:$WS_PORT"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# Start Python UDP server and Flask dashboard
"$PYTHON_BIN" -m app.main server \
  --host "$HOST" \
  --port "$PORT" \
  --web-host "$WEB_HOST" \
  --web-port "$WEB_PORT" &
PYTHON_PID=$!

# Give Python server time to start
sleep 2

# Start Node.js WebSocket proxy
UDP_HOST="$PROXY_UDP_HOST" UDP_PORT="$PORT" WS_PORT="$WS_PORT" "$NODE_BIN" websocket-proxy.js &
NODE_PID=$!

echo "Python server PID: $PYTHON_PID"
echo "WebSocket proxy PID: $NODE_PID"
echo ""
echo "Dashboard ready at: http://localhost:$WEB_PORT"
echo ""

# Wait for both processes
wait $PYTHON_PID $NODE_PID
