"""Run the pipeline in a background thread so the web request returns at once.

Only one run executes at a time; the UI polls is_running()/last_summary() to
show progress and the most recent result.
"""
import threading

from utils.logger import get_logger

logger = get_logger("webapp.runner")

_lock = threading.Lock()
_running = False
_thread: threading.Thread | None = None
_last_summary: dict | None = None


def is_running() -> bool:
    return _running


def last_summary() -> dict | None:
    return _last_summary


def start_run(source: str = "all") -> bool:
    """Kick off run_all(source) in a worker thread. Returns False if one is busy."""
    global _running, _thread
    with _lock:
        if _running:
            return False
        _running = True

    def _work():
        global _running, _last_summary
        try:
            from main import run_all  # imported lazily to avoid heavy import at boot
            _last_summary = run_all(source=source)
        except Exception as exc:  # never let the thread die silently
            logger.error("Background run failed: %s", exc, exc_info=True)
            _last_summary = {"errors": 1, "message": str(exc)}
        finally:
            _running = False

    _thread = threading.Thread(target=_work, name="job-run", daemon=True)
    _thread.start()
    return True
