#!/usr/bin/env bash
# start-api.sh — kill any process holding the API port, then start uvicorn.
# Works on Windows (Git Bash), macOS, and Linux.

set -e

PORT=${PORT:-8000}

echo "Starting API on port $PORT..."

# --- kill any existing process on this port ---
if command -v netstat >/dev/null 2>&1; then
    PIDS=$(netstat -ano 2>/dev/null \
        | awk "/LISTEN/" \
        | awk -v p=":$PORT " '$0 ~ p {print $NF}' \
        | sort -u)

    for PID in $PIDS; do
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            echo "  Killing PID $PID (was holding port $PORT)..."
            # Windows (Git Bash)
            cmd //c "taskkill /PID $PID /F" 2>/dev/null \
                || kill -9 "$PID" 2>/dev/null \
                || true
        fi
    done

    [ -n "$PIDS" ] && sleep 1
fi

# --- start uvicorn ---
exec uvicorn src.api.main:app --reload --port "$PORT"
