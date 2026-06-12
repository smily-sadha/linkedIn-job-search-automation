"""Per-source daily counters, persisted to logs/rate_limits.json."""
import json
from datetime import date
from pathlib import Path

from config.config import DAILY_LIMITS, LOG_DIR
from utils.logger import get_logger

logger = get_logger("rate_limiter")
_FILE = Path(LOG_DIR) / "rate_limits.json"


def _load() -> dict:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("rate_limits.json unreadable; starting fresh")
    return {}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def reset_if_new_day(source: str) -> None:
    data = _load()
    today = date.today().isoformat()
    if data.get(source, {}).get("date") != today:
        data[source] = {"date": today, "count": 0}
        _save(data)


def get_count(source: str) -> int:
    reset_if_new_day(source)
    return _load().get(source, {}).get("count", 0)


def can_apply(source: str) -> bool:
    limit = DAILY_LIMITS.get(source, 50)
    return get_count(source) < limit


def increment(source: str) -> None:
    reset_if_new_day(source)
    data = _load()
    data[source]["count"] = data[source].get("count", 0) + 1
    _save(data)
