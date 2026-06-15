"""Per-job application tailoring via the LLM.

Given a job + your resume profile, produce honest, ATS-aware assets: a tailored
resume summary, what to emphasise, the role's key ATS keywords (so you can make
sure they appear in your resume), and a ready-to-send cover letter.

Honest scope: it never invents experience you don't have — it reframes what you
already have toward the role. Returns None if the LLM is off or the call fails.
"""
import json

from ai.groq_client import chat, is_enabled
from config.config import EXPERIENCE_LEVEL, YOUR_NAME
from utils.logger import get_logger

logger = get_logger("tailor")

_SYSTEM = (
    "You are an expert tech career coach helping an ENTRY-LEVEL candidate apply "
    "to a role. Produce concise, honest, ATS-aware assets. NEVER invent "
    "experience, employers, or numbers the candidate did not provide — only "
    "reframe their real skills toward the role. Reply with STRICT JSON, keys: "
    '"summary" (a 2-3 line resume summary tailored to this role), '
    '"highlight" (1-2 lines on which of the candidate\'s skills/projects to '
    'emphasise), '
    '"keywords" (array of 5-10 ATS keywords/skills from the role the candidate '
    'should ensure appear in their resume), '
    '"cover_letter" (a 120-160 word first-person cover letter, ready to send).'
)


def tailor_application(job: dict) -> "dict | None":
    """Return {summary, highlight, keywords[], cover_letter} or None."""
    if not is_enabled():
        return None
    from utils.resume_parser import get_profile
    skills = ", ".join(get_profile().get("skills", [])[:30])
    title = job.get("Job Title") or job.get("title") or ""
    company = job.get("Company Name") or job.get("company") or ""
    jd = job.get("description") or job.get("Reason") or ""
    user = (
        f"CANDIDATE: {YOUR_NAME}, {EXPERIENCE_LEVEL}. Skills: {skills}.\n\n"
        f"ROLE: {title} at {company}.\n"
        f"Job details: {jd[:2500] or '(only the role title is known)'}"
    )
    raw = chat(_SYSTEM, user, max_tokens=650, json_mode=True, temperature=0.4)
    if not raw:
        return None
    try:
        data = json.loads(raw, strict=False)  # tolerate raw newlines in strings
    except Exception as exc:
        logger.warning("[Tailor] bad JSON for %s: %s", title, exc)
        return None
    kws = data.get("keywords") or []
    if isinstance(kws, str):
        kws = [k.strip() for k in kws.split(",") if k.strip()]
    return {
        "summary": str(data.get("summary", "")).strip(),
        "highlight": str(data.get("highlight", "")).strip(),
        "keywords": [str(k).strip() for k in kws if str(k).strip()][:10],
        "cover_letter": str(data.get("cover_letter", "")).strip(),
    }
