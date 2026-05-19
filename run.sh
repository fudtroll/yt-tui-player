#!/usr/bin/env bash
# YT TUI Player — TUI Launcher
cd "$(dirname "$0")"
exec .venv/bin/python main.py "$@"
