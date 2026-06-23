"""
Central configuration for the job-hunt assistant.

Secrets are read from the environment (.env file) so nothing sensitive lives
in source control. Everything else (keywords, weights, limits) lives here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder that contains this config package's parent.
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _bool(key: str, default: bool) -> bool:
    return _env(key, str(default)).lower() in ("1", "true", "yes", "on")


# ── Profile ────────────────────────────────────────────────────────────────
YOUR_NAME = _env("YOUR_NAME", "Your Full Name")
YOUR_EMAIL = _env("YOUR_EMAIL", "your@gmail.com")
YOUR_PHONE = _env("YOUR_PHONE", "+91-XXXXXXXXXX")

# ── Resumes ────────────────────────────────────────────────────────────────
# Just drop ONE resume PDF into config/resumes/ — whatever it's named. The bot
# auto-picks it, so swapping in a different resume immediately changes which
# jobs are searched/scored (skills are re-read from the new file). No code edit
# needed. If several PDFs are present, the most recently modified one wins.
_RESUMES_DIR = ROOT / "config" / "resumes"


def _detect_resume() -> str:
    pdfs = sorted(
        _RESUMES_DIR.glob("*.pdf"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if pdfs:
        return str(pdfs[0])
    # Fallback: keep a stable path so logs point somewhere sensible if empty.
    return str(_RESUMES_DIR / "resume.pdf")


_SINGLE_RESUME = _detect_resume()
RESUMES = {
    "python": _SINGLE_RESUME,
    "java": _SINGLE_RESUME,
    "fullstack": _SINGLE_RESUME,
    "default": _SINGLE_RESUME,
}

# Which resume to pick based on words found in the job description.
RESUME_KEYWORD_MAP = {
    "python": ["python", "django", "flask", "fastapi", "pandas"],
    "java": ["java", "spring", "springboot", "hibernate", "maven"],
    "fullstack": ["react", "node", "angular", "vue", "full stack", "fullstack"],
}

# ── Job search ─────────────────────────────────────────────────────────────
JOB_KEYWORDS = [
    "Python Developer", "Software Engineer", "Backend Developer",
    "Django Developer", "Flask Developer", "Junior Software Engineer",
    "Entry Level Developer", "Graduate Trainee Software",
]
JOB_LOCATION = "India"
EXPERIENCE_LEVEL = "Entry Level"
MIN_AI_SCORE = 7  # Only surface/apply jobs scoring >= this.
# Push an instant Telegram alert for fresh jobs scoring >= this (high match),
# so you can apply within the first hour. Needs TELEGRAM_* configured.
ALERT_MIN_SCORE = int(_env("ALERT_MIN_SCORE", "7") or "7")

# Freshness: only surface jobs actually posted within this many hours, for
# sources that expose a real posting date (Remotive / RemoteOK / RSS). Gmail
# freshness is governed by GMAIL_LOOKBACK_HOURS instead, since alert emails
# carry no posting date — a short lookback (≈ the 3h run interval) keeps those
# fresh. 0 disables the filter.
FRESH_MAX_HOURS = int(_env("FRESH_MAX_HOURS", "24") or "24")

# Adaptive Gmail lookback: each run reads alert emails going back to the LAST
# run (so a run after a 7h gap looks back ~7h, a 3-hourly run ~3h), capped just
# above the freshness window since older emails can only hold stale jobs. This
# makes every run — scheduled or manual — pick up exactly what's new since the
# previous one, with no gaps. Set False to use a fixed GMAIL_LOOKBACK_HOURS.
ADAPTIVE_LOOKBACK = _bool("ADAPTIVE_LOOKBACK", True)

# When True, the bot reads your resume PDF, extracts your real skills, and uses
# them to (a) build search keywords and (b) score jobs against YOUR profile
# instead of the static JOB_KEYWORDS / SKILL_WEIGHTS below.
USE_RESUME_PROFILE = True

# ── LLM match scoring (optional, via Groq — OpenAI-compatible API) ───────────
# When enabled, jobs are scored by an LLM that reasons about how well YOUR
# resume matches the role (a "Match" score, not a real hiring probability).
# Needs GROQ_API_KEY in .env (free tier at https://console.groq.com). Any
# failure falls back to the keyword scorer, so a missing key or wrong model
# never breaks a run. Groq is OpenAI-compatible, so this uses plain HTTP
# (requests) — no extra SDK.
USE_LLM_SCORING = _bool("USE_LLM_SCORING", False)
GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL = _env("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")

# ── Google Programmable Search (for the walk-in drive hunter) ────────────────
# Official Custom Search JSON API: free 100 queries/day, ToS-safe, reliable.
# Create both at https://programmablesearchengine.google.com (engine -> cx id)
# and https://console.cloud.google.com (enable "Custom Search API" -> key).
# Set GOOGLE_API_KEY + GOOGLE_CSE_ID in .env to switch the walkin_search source on.
GOOGLE_API_KEY = _env("GOOGLE_API_KEY")
GOOGLE_CSE_ID = _env("GOOGLE_CSE_ID")

# ── Scraping-API proxy (for sites behind hard anti-bot, e.g. Naukri/Akamai) ──
# Routes a fetch through a service that solves the anti-bot + uses residential
# IPs, then returns the rendered HTML. Works with ScraperAPI (default) and any
# compatible "?api_key=&url=&render=" proxy (ZenRows/ScrapingBee via SCRAPER_API_URL).
# Free trials give ~1000 calls/month. Set SCRAPER_API_KEY in .env to switch on.
SCRAPER_PROXY = {
    "api_url": _env("SCRAPER_API_URL", "https://api.scraperapi.com/"),
    "api_key": _env("SCRAPER_API_KEY"),
    "country": _env("SCRAPER_COUNTRY", "in"),   # residential IP country
    "render": _bool("SCRAPER_RENDER", True),     # run JS (needed to beat Akamai)
}

# ── Job sources (ToS-friendly: public APIs + RSS feeds only) ────────────────
# Each source is queried programmatically through documented endpoints.
# No browser automation, no anti-bot evasion, no logging in as you.
SOURCES = {
    # Remotive: public job API. https://remotive.com/api/remote-jobs
    "remotive": {"enabled": True},
    # RemoteOK: public job API. https://remoteok.com/api
    "remoteok": {"enabled": True},
    # Generic RSS feeds — add any career-page / aggregator RSS URL here.
    "rss": {
        "enabled": True,
        "feeds": [
            # "https://example.com/jobs.rss",
        ],
    },
    # Gmail: reads job-ALERT emails from your own inbox (LinkedIn / Naukri /
    # Indeed alerts you opted into). This is the ToS-safe way to get LinkedIn
    # jobs — you read your own email, you never automate the LinkedIn site.
    # Requires GMAIL_EMAIL + GMAIL_APP_PASSWORD in .env and IMAP enabled.
    "gmail": {
        "enabled": True,
        # Each run only looks at alert emails from the last N hours. Set this a
        # little above your run interval (runs are every 3h) so nothing slips
        # through a boundary, while old mail isn't re-scanned every run.
        # (Already-tracked jobs are deduped anyway, so overlap is harmless.)
        "lookback_hours": 4,
        "max_emails": 60,              # safety cap on messages parsed per run
        # Only TRUE job-alert senders (not notifications/newsletters/marketing).
        # These are matched as a substring of the From header.
        "senders": [
            "jobalerts-noreply@linkedin.com",   # LinkedIn saved-search alerts
            "jobs-noreply@linkedin.com",        # LinkedIn "X is hiring"
            "jobs-listings@linkedin.com",
            "alerts@naukri.com",                # Naukri job alerts (set them up)
            "jobalerts@naukri.com",
            "naukri.com",                       # Naukri sender variants / notifications
            "alert@indeed.com",                 # Indeed job alerts (set them up)
            "donotreply@match.indeed.com",
            "invitetoapply@indeed.com",
        ],
    },
    # LinkedIn — DIRECT scrape via the public, logged-out guest job-search
    # endpoint. No login/cookies, so there's no account to ban; the only risk is
    # LinkedIn rate-limiting your IP (handled gracefully). NOTE: scraping is
    # against LinkedIn's Terms of Service even via this public endpoint — this is
    # why it's a deliberate opt-in. The Gmail source above is the ToS-safe path.
    "linkedin": {
        "enabled": True,
        "location": JOB_LOCATION,
        "pages": 2,                          # 25 jobs/page from the guest endpoint
        "posted_within_hours": FRESH_MAX_HOURS,  # 0 = no time filter (maps to f_TPR)
    },
    # Naukri — DIRECT via its internal search JSON API. EXPERIMENTAL: undocumented
    # endpoint, against ToS, can change shape or rate-limit your IP. Fails soft.
    "naukri": {
        "enabled": True,
        "pages": 2,                          # 20 jobs/page
    },
    # Indeed — DIRECT by parsing the public results page. EXPERIMENTAL and the
    # most fragile: Indeed's anti-bot (Cloudflare/captcha) often returns 0 jobs,
    # especially from datacenter/VPN IPs. Fails soft; treat hits as a bonus.
    "indeed": {
        "enabled": True,
        "domain": "in.indeed.com",           # country site (in./www./uk. etc.)
        "location": JOB_LOCATION,
        "pages": 2,                          # 10 jobs/page
    },
    # Walk-in drive hunter — searches Google (official Custom Search API) for
    # walk-in interview drives across the whole web, then extracts date/time/
    # venue into the Walk-In Drives sheet. Auto-on only when the Google keys are
    # set; budget-aware (a few queries per run to stay under the free 100/day).
    "walkin_search": {
        "enabled": bool(GOOGLE_API_KEY and GOOGLE_CSE_ID),
        "location": JOB_LOCATION,
        "max_queries": 4,                    # CSE calls per run (×8 runs/day ≈ 32)
        "results_per_query": 10,             # CSE returns up to 10 per call
        "fetch_pages": True,                 # fetch landing pages for fuller address
        "date_restrict": "m1",               # only results from the last month
    },
}

# ── Gmail (cold mail) ──────────────────────────────────────────────────────
GMAIL = {
    "email": _env("GMAIL_EMAIL", YOUR_EMAIL),
    "app_password": _env("GMAIL_APP_PASSWORD"),
    "sender_name": YOUR_NAME,
}

# ── Telegram ───────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("TELEGRAM_CHAT_ID")

# ── Files ──────────────────────────────────────────────────────────────────
EXCEL_FILE = str(ROOT / "tracker" / "job_applications.xlsx")
LOG_DIR = str(ROOT / "logs")
DATA_DIR = str(ROOT / "data")
SESSION_DIR = str(ROOT / "logs" / "sessions")

# ── Scheduler ──────────────────────────────────────────────────────────────
# Runs every 3 hours, around the clock (8 runs/day).
SCHEDULE_TIMES = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
WEEKLY_REPORT_DAY = "sunday"
WEEKLY_REPORT_TIME = "09:00"

# ── Behaviour / safety rails ───────────────────────────────────────────────
# DRY_RUN: when True, cold mails are written to data/drafts/ instead of sent.
DRY_RUN = _bool("DRY_RUN", True)
# REQUIRE_MAIL_CONFIRM: when True, a mail is only sent after explicit approval
# (Telegram /approve or main.py --send-approved). Mass-blasting is intentionally
# not supported.
REQUIRE_MAIL_CONFIRM = _bool("REQUIRE_MAIL_CONFIRM", True)

MAX_JOBS_PER_RUN = 40
# Per-source daily caps keep this polite and within any rate guidance.
DAILY_LIMITS = {
    "remotive": 100,
    "remoteok": 100,
    "rss": 100,
}
# Cold-mail caps (deliberately conservative to avoid looking like spam).
MAX_COLD_MAILS_PER_DAY = 15
COMPANY_COOLDOWN_DAYS = 30   # Skip a company applied to in the last N days.
FOLLOWUP_AFTER_DAYS = 5      # Send a follow-up after N days with no reply.
MAX_FOLLOWUPS = 1            # At most this many follow-ups per company.

# ── Cold-mail templates ────────────────────────────────────────────────────
COLD_MAIL_SUBJECT = "Application for {job_title} - {your_name}"
COLD_MAIL_BODY = """Dear {hr_name},

I came across the {job_title} opening at {company} and I am very interested.

I am a fresher with hands-on experience in Python, Django, and backend
development, and I noticed your description mentions {jd_keyword}, which aligns
well with my skill set.

I have attached my resume for your review and would welcome the chance to
discuss how I can contribute to {company}.

Looking forward to hearing from you.

Best regards,
{your_name}
{your_email} | {your_phone}
"""

FOLLOWUP_SUBJECT = "Follow-up: {job_title} Application - {your_name}"
FOLLOWUP_BODY = """Dear {hr_name},

I wanted to follow up on my application for the {job_title} role at {company},
which I sent on {original_date}.

I remain very enthusiastic about this opportunity and would be glad to share any
additional information you need.

Best regards,
{your_name}
"""

