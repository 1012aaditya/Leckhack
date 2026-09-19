#!/usr/bin/env bash
# Start the Citation Auditor with one command.
#
#   ./run.sh              start on http://localhost:8000
#   PORT=9000 ./run.sh    start somewhere else
#   ./run.sh --demo-data  also load the bundled CAP-format sample first
#
# Creates a virtualenv and installs dependencies on first run, then reuses
# them. Safe to run repeatedly.

set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
VENV="${VENV:-.venv}"

step() { printf '\n\033[1;32m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$1"; }

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Install Python 3.11 or newer and try again." >&2
  exit 1
fi

PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
if [ "$PY_OK" != "1" ]; then
  echo "Python 3.10 or newer is required. Found: $(python3 --version)" >&2
  exit 1
fi

if [ ! -d "$VENV" ]; then
  step "Creating virtualenv in $VENV"
  python3 -m venv "$VENV"
fi

PYBIN="$VENV/bin/python"
[ -x "$PYBIN" ] || PYBIN="$VENV/Scripts/python"   # Windows layout

step "Installing dependencies"
"$PYBIN" -m pip install --quiet --upgrade pip
"$PYBIN" -m pip install --quiet -r requirements.txt

if [ "${1:-}" = "--demo-data" ]; then
  step "Loading the bundled CAP-format sample"
  "$PYBIN" scripts/load_cap.py fixtures/cap_sample.jsonl --synthetic --index
fi

# Fail early with a clear message rather than uvicorn's stack trace.
if command -v lsof >/dev/null 2>&1 && lsof -i ":$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  warn "Port $PORT is already in use. Try:  PORT=8001 ./run.sh"
  exit 1
fi

step "Starting the server"
printf '\n    \033[1mOpen  http://localhost:%s\033[0m\n    Press Ctrl+C to stop.\n\n' "$PORT"

exec "$PYBIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
