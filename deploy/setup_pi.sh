#!/usr/bin/env bash
# One-shot setup for the Raspberry Pi:
#   1. creates a Python virtual environment and installs dependencies
#   2. installs cron jobs: a run every 3 hours + a weekly report on Sunday 9am
#
# Run it once from the project folder on the Pi:
#   bash deploy/setup_pi.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
echo "Project directory: $PROJECT_DIR"

# --- 1. Python venv + dependencies ------------------------------------------
if ! command -v python3 >/dev/null; then
    echo "ERROR: python3 not found. Run: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "Creating virtual environment ..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
chmod +x deploy/run_once.sh

# --- 2. Sanity check ---------------------------------------------------------
if [ ! -f .env ]; then
    echo "WARNING: .env not found. Copy your .env (with secrets) to $PROJECT_DIR before the first run."
fi
echo "Verifying imports ..."
./venv/bin/python -c "import main" && echo "Imports OK."

# --- 3. Install cron jobs ----------------------------------------------------
RUN_LINE="0 */3 * * * $PROJECT_DIR/deploy/run_once.sh"
REPORT_LINE="0 9 * * 0 $PROJECT_DIR/venv/bin/python $PROJECT_DIR/main.py --report >> $PROJECT_DIR/logs/scheduler.log 2>&1"

# Remove any prior copies of our lines, then add the fresh ones.
( crontab -l 2>/dev/null | grep -v "run_once.sh" | grep -v "main.py --report" || true; \
  echo "$RUN_LINE"; echo "$REPORT_LINE" ) | crontab -

echo
echo "Cron installed (runs every 3 hours + weekly report Sunday 09:00):"
crontab -l | grep -E "run_once|--report"
echo
echo "Setup complete. The bot will now run automatically."
echo "Tip: set the Pi's timezone to IST ->  sudo timedatectl set-timezone Asia/Kolkata"
