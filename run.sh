#!/usr/bin/env bash
# YT TUI Player — TUI Launcher
# Works on Linux and Termux (Android)

CDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$CDIR"

if [ -x ".venv/bin/python" ]; then
    exec .venv/bin/python main.py "$@"
elif [ -x ".venv/Scripts/python" ]; then
    # Windows fallback (untested)
    exec .venv/Scripts/python main.py "$@"
else
    echo "ERROR: Virtual environment not found." >&2
    echo "  Run ./setup.sh first, or create a venv:" >&2
    echo "    python3 -m venv .venv" >&2
    echo "    source .venv/bin/activate" >&2
    echo "    pip install -r requirements.txt" >&2
    exit 1
fi
