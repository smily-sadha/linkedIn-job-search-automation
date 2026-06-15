"""Real open/closed verification for job postings.

The dashboard previously showed an *estimated* application window (date found +
30 days), which had nothing to do with whether the posting is actually live.
This checks the real URL instead:

  * LinkedIn  -> the public guest job-posting endpoint (no login), which shows a
                "No longer accepting applications" banner on closed roles.
  * Others    -> a plain GET; 404/410 = gone, 200 without a closed marker = open.

Results are cached in data/job_status.json with a timestamp so we don't re-hit
the network on every page load. Anything uncertain returns 'unknown' — we never
fake a status.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests

from config.config import DATA_DIR
from utils.logger import get_logger

logger = get_logger("job_status")

_CACHE = Path(DATA_DIR) / "job_status.json"
_UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
_CLOSED_MARKERS = (
    "no longer accepting applications", "no longer accepting application",
    "no longer available", "this job is no longer", "not accepting applications",
)
_LINKEDIN_ID = re.compile(r"/jobs/view/(\d+)")
_AGO = re.compile(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", re.I)
_AGE_HOURS = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}


# ── cache ────────────────────────────────────────────────────────────────────
def _load() -> dict:
    if _CACHE.exists():
        try:
            return json.loads(_CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(data: dict) -> None:
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_status(url: str) -> dict:
    """Return the cached {status, checked, detail} for a URL, or unknown."""
    return _load().get(url, {"status": "unknown", "checked": None})


def record_status(url: str, status: str, detail: str = "auto") -> None:
    """Write a single URL's status into the cache (warms the verify view)."""
    if not url:
        return
    cache = _load()
    cache[url] = {"status": status,
                  "checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
                  "detail": detail}
    _save(cache)


def linkedin_check(url: str) -> "tuple[float | None, str]":
    """One fetch of a LinkedIn posting → (age_hours, status).

    age_hours is hours since it was posted (parsed from "posted X ago"), or
    None if unknown. status is 'open' | 'closed' | 'unknown'.
    """
    m = _LINKEDIN_ID.search(url or "")
    if not m:
        return None, "unknown"
    try:
        r = requests.get(
            f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}",
            headers=_UA, timeout=20)
        if r.status_code in (404, 410):
            return None, "closed"
        if r.status_code != 200:
            return None, "unknown"
        status = "closed" if any(k in r.text.lower() for k in _CLOSED_MARKERS) else "open"
        am = _AGO.search(r.text)
        age = int(am.group(1)) * _AGE_HOURS[am.group(2).lower()] if am else None
        return age, status
    except Exception as exc:
        logger.warning("[Status] linkedin_check failed for %s: %s", url, exc)
        return None, "unknown"


# ── network checks ─────────────────────────────────────────────────────────--
def _check_linkedin(job_id: str) -> tuple[str, str]:
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    r = requests.get(url, headers=_UA, timeout=20)
    if r.status_code in (404, 410):
        return "closed", f"HTTP {r.status_code}"
    if r.status_code != 200:
        return "unknown", f"HTTP {r.status_code}"
    text = r.text.lower()
    if any(m in text for m in _CLOSED_MARKERS):
        return "closed", "no longer accepting applications"
    return "open", "accepting applications"


def _check_generic(url: str) -> tuple[str, str]:
    r = requests.get(url, headers=_UA, timeout=20, allow_redirects=True)
    if r.status_code in (404, 410):
        return "closed", f"HTTP {r.status_code}"
    if r.status_code != 200:
        return "unknown", f"HTTP {r.status_code}"
    if any(m in r.text.lower() for m in _CLOSED_MARKERS):
        return "closed", "closed marker on page"
    return "open", "reachable"


def check_url(url: str) -> tuple[str, str]:
    """Return (status, detail). status is 'open' | 'closed' | 'unknown'."""
    if not url:
        return "unknown", "no url"
    try:
        m = _LINKEDIN_ID.search(url)
        if "linkedin.com" in url and m:
            return _check_linkedin(m.group(1))
        return _check_generic(url)
    except Exception as exc:
        logger.warning("[Status] check failed for %s: %s", url, exc)
        return "unknown", "check failed"


def verify_urls(urls: list[str], max_workers: int = 8) -> dict:
    """Check many URLs concurrently, update the cache, return {url: result}."""
    urls = [u for u in dict.fromkeys(urls) if u]  # dedupe, keep order
    if not urls:
        return {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _one(u):
        status, detail = check_url(u)
        return u, {"status": status, "checked": now, "detail": detail}

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for u, res in pool.map(_one, urls):
            results[u] = res

    cache = _load()
    cache.update(results)
    _save(cache)
    logger.info("[Status] verified %d url(s)", len(results))
    return results
