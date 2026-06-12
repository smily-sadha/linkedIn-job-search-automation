"""Detect walk-in drives in a job description and extract their details."""
import re

from utils.logger import get_logger

logger = get_logger("walkin_detector")

_WALKIN_RE = re.compile(r"\bwalk[\s-]?in\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"(\d{1,2}[\s/-](?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s/-]?\d{0,4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)(?:\s*[-to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))?)",
                      re.IGNORECASE)
_VENUE_RE = re.compile(r"(?:venue|address|location)[:\s]+([^\n.]{5,120})", re.IGNORECASE)


def is_walkin(jd_text: str) -> bool:
    return bool(_WALKIN_RE.search(jd_text or ""))


def extract_walkin_details(jd_text: str) -> dict:
    """Best-effort extraction of date / time / venue from a walk-in JD."""
    text = jd_text or ""
    date_m = _DATE_RE.search(text)
    time_m = _TIME_RE.search(text)
    venue_m = _VENUE_RE.search(text)
    return {
        "walkin_date": date_m.group(1).strip() if date_m else "",
        "walkin_time": time_m.group(1).strip() if time_m else "",
        "venue": venue_m.group(1).strip() if venue_m else "",
    }
