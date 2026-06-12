"""Company cooldown + blacklist/whitelist gating, persisted to logs/cooldowns.json."""
import json
from datetime import date, datetime
from pathlib import Path

from config.config import COMPANY_COOLDOWN_DAYS, LOG_DIR, ROOT
from utils.logger import get_logger

logger = get_logger("cooldown_manager")
_FILE = Path(LOG_DIR) / "cooldowns.json"
_BLACKLIST = ROOT / "config" / "blacklist.txt"
_WHITELIST = ROOT / "config" / "whitelist.txt"


def _load() -> dict:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("cooldowns.json unreadable; starting fresh")
    return {}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def is_blacklisted(company: str) -> bool:
    return (company or "").strip().lower() in _read_list(_BLACKLIST)


def is_whitelisted(company: str) -> bool:
    return (company or "").strip().lower() in _read_list(_WHITELIST)


def get_days_since(company: str) -> int | None:
    last = _load().get((company or "").strip().lower())
    if not last:
        return None
    return (date.today() - datetime.fromisoformat(last).date()).days


def is_on_cooldown(company: str) -> bool:
    days = get_days_since(company)
    return days is not None and days < COMPANY_COOLDOWN_DAYS


def set_cooldown(company: str) -> None:
    data = _load()
    data[(company or "").strip().lower()] = date.today().isoformat()
    _save(data)
