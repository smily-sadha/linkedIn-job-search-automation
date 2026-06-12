"""Pull an HR / contact first name out of a job description for personalisation."""
import re

from utils.logger import get_logger

logger = get_logger("hr_name_extractor")

_PATTERNS = [
    r"contact[:\s]+([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?",
    r"reach out to ([A-Z][a-z]+)",
    r"([A-Z][a-z]+)\s+from HR",
    r"HR[:\s]+([A-Z][a-z]+)",
    r"contact person[:\s]+([A-Z][a-z]+)",
]


def extract_hr_name(jd_text: str) -> str:
    """Return a first name if confidently found, else a safe default."""
    text = jd_text or ""
    for pattern in _PATTERNS:
        m = re.search(pattern, text)
        if m:
            name = m.group(1).strip()
            logger.info("[HR] Found contact name: %s", name)
            return name
    return "Hiring Manager"
