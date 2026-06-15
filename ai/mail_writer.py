"""LLM-personalised cold-email writer.

Produces a (subject, body) tailored to the specific role and the candidate's
real skills — a genuine, concise note, not buzzword soup. Returns None when the
LLM is off or the call fails, so the cold mailer falls back to its template.
"""
import json

from ai.groq_client import chat, is_enabled
from config.config import EXPERIENCE_LEVEL, YOUR_EMAIL, YOUR_NAME, YOUR_PHONE
from utils.logger import get_logger

logger = get_logger("mail_writer")

_SYSTEM = (
    "Write a concise, genuine cold job-application email for an ENTRY-LEVEL "
    "candidate. 110-150 words, first person, specific to the role, no buzzword "
    "stuffing, and NEVER invent experience or numbers. End the body with the "
    "candidate's name, email and phone on separate lines. Reply with STRICT "
    'JSON: {"subject": "...", "body": "..."}.'
)


def write_cold_email(job: dict) -> "tuple[str, str] | None":
    """Return (subject, body) for `job`, or None to fall back to the template."""
    if not is_enabled():
        return None
    from utils.resume_parser import get_profile
    skills = ", ".join(get_profile().get("skills", [])[:25])
    user = (
        f"Candidate: {YOUR_NAME} ({EXPERIENCE_LEVEL}). "
        f"Email: {YOUR_EMAIL}. Phone: {YOUR_PHONE}. Skills: {skills}.\n"
        f"Role: {job.get('title', '')} at {job.get('company', '')}.\n"
        f"Addressed to: {job.get('hr_name', 'Hiring Manager')}.\n"
        f"Job details: {(job.get('description') or '')[:1500]}"
    )
    raw = chat(_SYSTEM, user, max_tokens=420, json_mode=True, temperature=0.5)
    if not raw:
        return None
    try:
        data = json.loads(raw, strict=False)  # tolerate raw newlines in strings
        subject = str(data.get("subject", "")).strip()
        body = str(data.get("body", "")).strip()
        if subject and body:
            logger.info("[MailWriter] drafted personalised mail for %s", job.get("company"))
            return subject, body
    except Exception as exc:
        logger.warning("[MailWriter] bad JSON: %s", exc)
    return None
