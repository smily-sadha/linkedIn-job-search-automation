"""Extract a usable HR email from a job description, skipping generic inboxes."""
import re

from utils.logger import get_logger

logger = get_logger("email_extractor")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Inboxes that are usually unmonitored / autoresponders -> deprioritise.
_GENERIC_PREFIXES = (
    "no-reply", "noreply", "donotreply", "do-not-reply",
    "info", "support", "admin", "webmaster", "postmaster",
    "sales", "marketing", "newsletter",
)


def extract_email(jd_text: str) -> str | None:
    """Return the best HR email found, or None. Prefers personal/hr addresses."""
    candidates = _EMAIL_RE.findall(jd_text or "")
    if not candidates:
        return None

    # De-dupe, preserve order.
    seen, ordered = set(), []
    for c in candidates:
        cl = c.lower()
        if cl not in seen:
            seen.add(cl)
            ordered.append(cl)

    def is_generic(email: str) -> bool:
        local = email.split("@", 1)[0]
        return any(local.startswith(p) for p in _GENERIC_PREFIXES)

    preferred = [e for e in ordered if "hr" in e or "careers" in e or "recruit" in e]
    non_generic = [e for e in ordered if not is_generic(e)]

    chosen = (preferred or non_generic or ordered)[0]
    logger.info("[Email] Extracted recipient: %s", chosen)
    return chosen
