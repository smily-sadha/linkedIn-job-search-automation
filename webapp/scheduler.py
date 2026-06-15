"""In-process auto-fetch scheduler for the dashboard.

A daemon thread triggers a pipeline run every 3 hours (08 times/day) so freshly
posted jobs show up without you clicking "Run now". Only runs while the web
server is up — for always-on fetching use `python main.py --schedule`.

Environment overrides (set in .env):
    AUTO_FETCH            1/0  - enable auto-fetch (default 1)
    AUTO_FETCH_TIMES      comma-separated HH:MM run times
                          (default 06:00,09:00,12:00,15:00,18:00,21:00,00:00,03:00)
    GMAIL_LOOKBACK_HOURS  inbox history to scan per run (default 4; with a run
                          every 3h, 4h catches every new alert with a little
                          slack, and dedup makes the overlap harmless)
"""
import os
import threading
import time

import schedule

from utils.logger import get_logger
from webapp import runner

logger = get_logger("webapp.scheduler")

# Every 3 hours: 6AM, 9AM, 12PM, 3PM, 6PM, 9PM, 12AM, 3AM.
_DEFAULT_TIMES = "06:00,09:00,12:00,15:00,18:00,21:00,00:00,03:00"

_started = False


def _enabled() -> bool:
    return os.getenv("AUTO_FETCH", "1").strip().lower() in ("1", "true", "yes", "on")


def _times() -> list[str]:
    raw = os.getenv("AUTO_FETCH_TIMES", _DEFAULT_TIMES).strip()
    return [t.strip() for t in raw.split(",") if t.strip()] or _DEFAULT_TIMES.split(",")


def start() -> None:
    """Start the auto-fetch loop once. Safe to call more than once."""
    global _started
    if _started:
        return
    _started = True

    # Lookback is adaptive (set per-run in main.run_all to "time since last
    # run"), so we no longer force a fixed GMAIL_LOOKBACK_HOURS here.

    if not _enabled():
        logger.info("Auto-fetch disabled (AUTO_FETCH=0).")
        return

    times = _times()
    for t in times:
        schedule.every().day.at(t).do(lambda: runner.start_run("all"))
    logger.info("Auto-fetch scheduled at %s (lookback %sh).",
                times, os.environ.get("GMAIL_LOOKBACK_HOURS"))

    def _loop():
        while True:
            try:
                schedule.run_pending()
            except Exception as exc:  # never let the loop die
                logger.error("auto-fetch loop error: %s", exc)
            time.sleep(30)

    threading.Thread(target=_loop, name="auto-fetch", daemon=True).start()
