#!/bin/bash
# Run backend API + serve frontend

cd "$(dirname "$0")"

echo "Starting backend API on http://127.0.0.1:5000"
python -m src.api &
API_PID=$!

sleep 2
echo "Serving frontend on http://127.0.0.1:8080"
cd dashboard && python -m http.server 8080 &
SERVER_PID=$!

echo ""
echo "Open http://localhost:8080 in your browser"
echo "Press Ctrl+C to stop"
trap "kill $API_PID $SERVER_PID 2>/dev/null; exit" INT TERM
wait
