#!/usr/bin/env bash
# One job-hunt run, designed to be called by cron on the Raspberry Pi.
# Resolves the project directory relative to this script, activates the venv,
# runs main.py once, and appends all output to logs/scheduler.log.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p logs

echo "===== run at $(date '+%Y-%m-%d %H:%M:%S %Z') =====" >> logs/scheduler.log
"$PROJECT_DIR/venv/bin/python" main.py >> logs/scheduler.log 2>&1
echo "===== done at $(date '+%Y-%m-%d %H:%M:%S %Z') =====" >> logs/scheduler.log
