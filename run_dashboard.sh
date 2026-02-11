#!/bin/bash
# Run the app via Flask. The frontend is served by src.api on the same origin.

set -euo pipefail
cd "$(dirname "$0")"

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="venv/bin/python"
elif [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use."
  echo "Stop the existing process or run with another port, for example:"
  echo "  PORT=5001 ./run_dashboard.sh"
  exit 1
fi

echo "Starting app on http://$HOST:$PORT"
echo "Open http://$HOST:$PORT in your browser"
echo "Using Python: $PYTHON_BIN"
exec "$PYTHON_BIN" -m src.api
