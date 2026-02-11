#!/bin/bash
# Run backend API + serve frontend

cd "$(dirname "$0")"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

echo "Starting backend API on http://127.0.0.1:5000"
"$PYTHON_BIN" -m src.api &
API_PID=$!

sleep 2
echo "Serving frontend on http://127.0.0.1:8080"
cd dashboard && "$PYTHON_BIN" -m http.server 8080 &
SERVER_PID=$!

echo ""
echo "Open http://localhost:8080 in your browser"
echo "Press Ctrl+C to stop"
trap "kill $API_PID $SERVER_PID 2>/dev/null; exit" INT TERM
wait
