"""Optional LLM match scoring via the Groq API.

Groq's API is OpenAI-compatible, so we call it with plain `requests` — no extra
SDK. It reads your resume profile + the job (title, company, description) and
returns a 1-10 *match* score: how well YOU fit the role.

Honest scope: this is a resume-to-job FIT score, NOT a probability of being
hired. No model can know the applicant pool, ATS rules, or recruiter behaviour.

Enable with USE_LLM_SCORING=1 and GROQ_API_KEY in .env (free tier at
https://console.groq.com). Every failure path returns None so the caller falls
back to the keyword scorer — a missing key, wrong model name, or network blip
never breaks a pipeline run.
"""
import json
import re

from ai.groq_client import chat, is_enabled
from config.config import EXPERIENCE_LEVEL
from utils.logger import get_logger

logger = get_logger("llm_scorer")

_SYSTEM = (
    "You are a precise technical recruiter screening a candidate for a role. "
    "Rate how well the CANDIDATE matches the JOB on a 1-10 scale "
    "(10 = ideal fit, 1 = no fit). Weigh skills overlap, seniority fit, and "
    "domain. Reply with STRICT JSON only, no prose: "
    '{"match": <integer 1-10>, "reason": "<max 12 words why>"}'
)


def _profile_brief() -> str:
    from utils.resume_parser import get_profile
    skills = ", ".join(get_profile().get("skills", [])[:30])
    return f"Experience level: {EXPERIENCE_LEVEL}. Skills: {skills}."


def _parse(content: str) -> tuple[int, str]:
    """Pull (score, reason) out of the model reply, defensively."""
    try:
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0) if m else content, strict=False)
        score = int(data.get("match"))
        reason = str(data.get("reason", "")).strip()
    except Exception:
        nums = re.findall(r"\b(10|[1-9])\b", content)
        score = int(nums[0]) if nums else 5
        reason = content.strip().replace("\n", " ")[:80]
    return max(1, min(10, score)), reason


def score_match(title: str, company: str, jd_text: str) -> "tuple[int, str] | None":
    """Return (match 1-10, reason) from Groq, or None to signal fallback."""
    if not is_enabled():
        return None
    content = chat(
        _SYSTEM,
        f"CANDIDATE:\n{_profile_brief()}\n\n"
        f"JOB:\nTitle: {title}\nCompany: {company}\n"
        f"Description: {(jd_text or '')[:3000]}",
        max_tokens=120, json_mode=True, temperature=0,
    )
    if content is None:
        return None
    score, reason = _parse(content)
    logger.info("[LLM] %s - %s: Match %d/10 (%s)", company, title, score, reason)
    return score, reason
