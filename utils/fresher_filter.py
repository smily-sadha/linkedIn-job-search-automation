"""Detect 'entry level' jobs that secretly require multiple years of experience."""
import re

from utils.logger import get_logger

logger = get_logger("fresher_filter")

# Patterns that strongly imply prior professional experience is required.
_EXP_PATTERNS = [
    r"minimum\s+(\d+)\s*\+?\s*years?",
    r"(\d+)\s*\+\s*years?\s+(?:of\s+)?experience",
    r"at\s+least\s+([2-9])\s*\+?\s*years?",
    r"([2-9])\s*-\s*\d+\s+years?\s+(?:of\s+)?experience",
]
# A plain "N years" near the word experience/required.
_YEARS_NEAR_EXP = re.compile(
    r"([2-9])\s*\+?\s*years?.{0,40}(experience|required)"
    r"|(experience|required).{0,40}([2-9])\s*\+?\s*years?",
    re.IGNORECASE,
)
_SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|lead|principal|architect|manager)\b", re.IGNORECASE)


def is_fake_entry_level(jd_text: str, job_title: str = "", company: str = "") -> bool:
    """Return True if this 'entry level' posting actually demands experience."""
    text = (jd_text or "").lower()

    # Senior-sounding titles are an immediate disqualifier.
    if _SENIOR_TITLE.search(job_title or ""):
        logger.warning("[Filter] Skipped (senior title): %s - %s", company, job_title)
        return True

    for pattern in _EXP_PATTERNS:
        m = re.search(pattern, text)
        if m:
            years_str = next((g for g in m.groups() if g and g.isdigit()), None)
            if years_str and int(years_str) >= 2:
                logger.warning("[Filter] Skipped (needs %s yrs): %s - %s",
                               years_str, company, job_title)
                return True

    if _YEARS_NEAR_EXP.search(text):
        logger.warning("[Filter] Skipped (experience required): %s - %s", company, job_title)
        return True

    return False
