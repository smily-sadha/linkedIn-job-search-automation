"""Pick the most relevant resume PDF based on job-description keywords."""
from config.config import RESUME_KEYWORD_MAP, RESUMES
from utils.logger import get_logger

logger = get_logger("resume_selector")


def select_resume(jd_text: str) -> str:
    """Return the path of the resume whose keywords appear most in the JD."""
    text = (jd_text or "").lower()
    scores = {}
    for variant, keywords in RESUME_KEYWORD_MAP.items():
        scores[variant] = sum(text.count(kw) for kw in keywords)

    best = max(scores, key=scores.get) if scores else None
    if best and scores[best] > 0:
        logger.info("[Resume] Selected '%s' (%d keyword hits)", best, scores[best])
        return RESUMES.get(best, RESUMES["default"])

    logger.info("[Resume] No strong match; using default")
    return RESUMES["default"]
