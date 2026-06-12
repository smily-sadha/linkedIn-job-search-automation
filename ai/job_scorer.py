"""Relevance scoring (1-10) for a job description.

Two modes (config.USE_RESUME_PROFILE):
  * resume mode  - score against the skills parsed from YOUR resume PDF, so a
                   job that matches what you actually know scores high.
  * static mode  - fall back to the fixed SKILL_WEIGHTS table (no resume).

Both modes reward fresher signals and penalise senior/experience signals.
"""
import re

from config.config import USE_RESUME_PROFILE
from utils.logger import get_logger

logger = get_logger("job_scorer")

# Static fallback table (used only when USE_RESUME_PROFILE is False or no resume).
SKILL_WEIGHTS = {
    "python": 2, "django": 2, "flask": 2, "fastapi": 2,
    "sql": 1, "mysql": 1, "postgresql": 1, "git": 1,
    "rest api": 1, "api": 1, "backend": 1,
    "fresher": 2, "graduate": 2, "trainee": 2, "entry level": 2,
    "0-1": 2, "0-2": 1, "no experience": 2,
    "senior": -3, "lead": -2, "manager": -3, "architect": -3,
    "5 years": -3, "4 years": -3, "3 years": -2,
}

# Shared signal tables for resume mode.
_FRESHER_SIGNALS = {
    "fresher": 2, "graduate": 2, "trainee": 2, "entry level": 2,
    "0-1": 2, "0-2": 1, "no experience": 2, "intern": 1,
}
_PENALTIES = {
    "senior": -3, "lead": -2, "manager": -3, "architect": -3, "staff": -2,
    "principal": -3, "5 years": -3, "4 years": -3, "3 years": -2,
}

_MAX_SKILL_MATCHES = 5  # cap so a keyword-stuffed JD can't trivially max out


def _count(text: str, term: str) -> int:
    return len(re.findall(rf"(?<![a-z0-9.+#]){re.escape(term)}(?![a-z0-9])", text))


def _score_static(text: str) -> int:
    raw = sum(w * _count(text, kw) for kw, w in SKILL_WEIGHTS.items())
    return max(1, min(10, round((raw + 6) / 18 * 9) + 1))


def _score_with_resume(text: str) -> tuple[int, int]:
    from utils.resume_parser import get_profile
    profile = get_profile()
    skills = profile.get("skills", [])
    # Role phrases like "ai engineer" / "data analyst" matter for sparse JDs
    # (e.g. email alerts that only carry the title).
    roles = [r.lower() for r in profile.get("search_keywords", [])]

    matched = sum(1 for s in skills if _count(text, s) > 0)
    matched += sum(1 for r in roles if r and r in text)
    matched = min(matched, _MAX_SKILL_MATCHES)
    raw = matched * 2
    raw += sum(w * _count(text, kw) for kw, w in _FRESHER_SIGNALS.items())
    raw += sum(w * _count(text, kw) for kw, w in _PENALTIES.items())

    score = max(1, min(10, round((raw + 8) / 22 * 9) + 1))
    return score, matched


def score_job(jd_text: str, job_title: str = "", company: str = "") -> int:
    text = f"{job_title} {jd_text}".lower()
    if USE_RESUME_PROFILE:
        try:
            score, matched = _score_with_resume(text)
            logger.info("[Scorer] %s - %s: Score %d/10 (%d resume-skill matches)",
                        company, job_title, score, matched)
            return score
        except Exception as exc:  # never let scoring crash a run
            logger.warning("[Scorer] resume mode failed (%s); using static table", exc)

    score = _score_static(text)
    logger.info("[Scorer] %s - %s: Score %d/10 (static)", company, job_title, score)
    return score
