# 🤖 Job Application Automation — Claude Code Prompt V2 (Enhanced)

## COPY THIS ENTIRE PROMPT INTO CLAUDE CODE TO BUILD THE PROJECT

---

## 🎯 PROJECT IDEA

Build a **fully automated, intelligent job application bot** for a **Fresher (0–1 yr experience)**
targeting IT / Software roles in India. The bot must:

1. Login to LinkedIn, Naukri, Indeed, and Shine.com
2. Search for entry-level IT/Software jobs using smart keywords
3. **Score each job using AI** (relevance 1–10) — only apply if score ≥ 7
4. **Filter out fake entry-level jobs** that secretly require 2+ years experience
5. **Auto-apply** via Easy Apply with the right resume version per job type
6. **Detect Walk-In drives** and log them to a separate sheet
7. **Send personalized cold emails via Gmail** when no Easy Apply exists
8. **Auto follow-up cold mails** after 5 days if no reply
9. **Track application pipeline** with status updates (Applied → Interview → Offer etc.)
10. **Protect against bans** — human behaviour simulation, rate limiting, session reuse
11. **CAPTCHA alert via Telegram** when bot gets stuck
12. Save everything in a **color-coded Excel tracker** with 7 sheets
13. Run manually OR on daily schedule (8 AM & 6 PM)
14. **Telegram Bot** for full remote control from phone

---

## 📁 FILE STRUCTURE TO CREATE

```
job_automation/
│
├── main.py                          # Entry point — manual + scheduler
├── requirements.txt                 # All dependencies
├── README.md                        # Full setup guide
├── .env.example                     # Env variable template
│
├── config/
│   ├── __init__.py
│   ├── config.py                    # All settings, credentials, keywords
│   ├── resumes/
│   │   ├── resume_python.pdf        # Resume for Python/Django/Flask jobs
│   │   ├── resume_java.pdf          # Resume for Java/Spring jobs
│   │   └── resume_fullstack.pdf     # Resume for Full Stack / React jobs
│   ├── blacklist.txt                # Companies to never apply to (one per line)
│   └── whitelist.txt                # Priority dream companies (one per line)
│
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py              # Abstract base with human behaviour simulation
│   ├── linkedin_scraper.py
│   ├── naukri_scraper.py
│   ├── indeed_scraper.py
│   └── shine_scraper.py
│
├── ai/
│   ├── __init__.py
│   ├── job_scorer.py                # AI relevance scoring (1–10) using keyword + NLP
│   └── hr_name_extractor.py         # Extract HR name from JD for personalized mail
│
├── mailers/
│   ├── __init__.py
│   ├── cold_mailer.py               # Gmail SMTP — personalized cold mail sender
│   └── followup_mailer.py           # Auto follow-up after 5 days with no reply
│
├── tracker/
│   ├── __init__.py
│   ├── excel_tracker.py             # Excel read/write (openpyxl) — 7 sheets
│   ├── status_manager.py            # Update application status in Excel
│   ├── cooldown_manager.py          # Company cooldown (skip same company for 30 days)
│   └── job_applications.xlsx        # Auto-created on first run
│
├── telegram/
│   ├── __init__.py
│   └── bot.py                       # Fully working Telegram bot
│
├── utils/
│   ├── __init__.py
│   ├── walkin_detector.py           # Walk-in drive detection + detail extraction
│   ├── email_extractor.py           # HR email extraction (skip generic emails)
│   ├── fresher_filter.py            # Filter out fake entry-level jobs
│   ├── resume_selector.py           # Pick right resume based on JD keywords
│   ├── human_behaviour.py           # Random mouse, scroll, typing simulation
│   ├── session_manager.py           # Save/load browser cookies to avoid re-login
│   ├── rate_limiter.py              # Per-platform daily apply limits
│   └── logger.py                    # Colored console + rotating file logger
│
├── reports/
│   ├── __init__.py
│   └── weekly_report.py             # Auto weekly summary report generator
│
└── logs/
    └── .gitkeep
```

---

## 🔧 DETAILED INSTRUCTIONS FOR EACH FILE

---

### `config/config.py`

```python
# ── Profile ──────────────────────────────────────────────────
YOUR_NAME  = "Your Full Name"
YOUR_EMAIL = "your@gmail.com"
YOUR_PHONE = "+91-XXXXXXXXXX"

# ── Resumes ──────────────────────────────────────────────────
RESUMES = {
    "python":     "config/resumes/resume_python.pdf",
    "java":       "config/resumes/resume_java.pdf",
    "fullstack":  "config/resumes/resume_fullstack.pdf",
    "default":    "config/resumes/resume_python.pdf",
}

# Resume keyword mapping (which resume to pick based on JD words)
RESUME_KEYWORD_MAP = {
    "python":    ["python", "django", "flask", "fastapi", "pandas"],
    "java":      ["java", "spring", "springboot", "hibernate", "maven"],
    "fullstack": ["react", "node", "angular", "vue", "full stack", "fullstack"],
}

# ── Job Search ────────────────────────────────────────────────
JOB_KEYWORDS = [
    "Python Developer", "Software Engineer", "Backend Developer",
    "Django Developer", "Flask Developer", "Junior Software Engineer",
    "Entry Level Developer", "Graduate Trainee Software"
]
JOB_LOCATION      = "India"
EXPERIENCE_LEVEL  = "Entry Level"
WORK_MODE         = ["Remote", "On-site", "Hybrid"]
MIN_AI_SCORE      = 7           # Only apply if AI relevance score >= 7

# ── Platform Credentials ──────────────────────────────────────
LINKEDIN = {"email": "", "password": ""}
NAUKRI   = {"email": "", "password": ""}
INDEED   = {"email": "", "password": ""}
SHINE    = {"email": "", "password": ""}

# ── Gmail ─────────────────────────────────────────────────────
GMAIL = {
    "email":        "your@gmail.com",
    "app_password": "xxxx xxxx xxxx xxxx",   # Gmail App Password
    "sender_name":  YOUR_NAME
}

# ── Telegram ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = "your_bot_token_here"
TELEGRAM_CHAT_ID    = "your_chat_id_here"

# ── Excel ─────────────────────────────────────────────────────
EXCEL_FILE = "tracker/job_applications.xlsx"

# ── Scheduler ─────────────────────────────────────────────────
SCHEDULE_TIMES = ["08:00", "18:00"]

# ── Bot Behaviour ─────────────────────────────────────────────
HEADLESS             = False
MAX_APPLIES_PER_RUN  = 20
DAILY_LIMITS = {          # Max applies per platform per day (anti-ban)
    "LinkedIn": 80,
    "Naukri":   100,
    "Indeed":   50,
    "Shine":    50,
}
COMPANY_COOLDOWN_DAYS = 30    # Skip company if applied in last 30 days
FOLLOWUP_AFTER_DAYS   = 5     # Send follow-up cold mail after N days

# ── Cold Mail Templates ───────────────────────────────────────
COLD_MAIL_SUBJECT = "Application for {job_title} — {your_name}"
COLD_MAIL_BODY = """
Dear {hr_name},

I came across the {job_title} opening at {company} and I am very interested.

I am a fresher with hands-on experience in Python, Django, and backend development,
and I noticed your job description mentions {jd_keyword} — which aligns perfectly
with my skill set.

I have attached my resume for your review and would love to discuss how I can
contribute to {company}.

Looking forward to hearing from you.

Best regards,
{your_name}
{your_email} | {your_phone}
"""

FOLLOWUP_SUBJECT = "Follow-Up: {job_title} Application — {your_name}"
FOLLOWUP_BODY = """
Dear {hr_name},

I wanted to follow up on my application for the {job_title} role at {company},
which I sent on {original_date}.

I remain very enthusiastic about this opportunity and would love to connect.
Please let me know if you need any additional information.

Best regards,
{your_name}
"""
```

---

### `utils/fresher_filter.py`

Build `is_fake_entry_level(jd_text) -> bool`:

- Scan JD text for these red-flag patterns (case-insensitive):
  - `"minimum \d+ years"`, `"\d\+ years experience"`, `"at least [2-9] year"`
  - `"2 years"`, `"3 years"`, `"4 years"`, `"5 years"` anywhere near "experience" or "required"
  - `"senior"`, `"lead"`, `"architect"` in job title (not description)
- Return `True` if any red-flag found → bot will skip this job
- Log a warning: `[Filter] Skipped fake entry-level: {company} — {title}`

---

### `ai/job_scorer.py`

Build `score_job(jd_text, job_title) -> int` (score 1–10):

Use **keyword-based weighted scoring** (no external API needed):

```python
SKILL_WEIGHTS = {
    # High value — exact match to fresher Python stack
    "python": 2, "django": 2, "flask": 2, "fastapi": 2,
    "sql": 1, "mysql": 1, "postgresql": 1, "git": 1,
    "rest api": 1, "api": 1, "backend": 1,
    # Bonus for fresher-friendly signals
    "fresher": 2, "graduate": 2, "trainee": 2, "entry level": 2,
    "0-1": 2, "0-2": 1, "no experience": 2,
    # Penalty words (reduce score)
    "senior": -3, "lead": -2, "manager": -3, "architect": -3,
    "5 years": -3, "4 years": -3, "3 years": -2,
}
```

- Combine jd_text + job_title, lowercase
- Sum weights for all matching keywords
- Normalize to 1–10 scale (clamp to min 1, max 10)
- Log: `[Scorer] {company} — {title}: Score {score}/10`
- Return score as int

---

### `ai/hr_name_extractor.py`

Build `extract_hr_name(jd_text) -> str`:

- Regex patterns to find HR name in JD:
  - `"contact[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)"` 
  - `"reach out to ([A-Z][a-z]+)"`
  - `"([A-Z][a-z]+) from HR"`
  - `"HR[:\s]+([A-Z][a-z]+)"`
- If name found → return first name only (e.g. "Priya")
- If not found → return `"Hiring Manager"` (safe default)

---

### `utils/resume_selector.py`

Build `select_resume(jd_text) -> str` (returns file path):

- Lowercase the JD text
- Loop through `RESUME_KEYWORD_MAP` in config
- Return path of resume whose keywords appear most in JD
- Default to `RESUMES["default"]` if no strong match
- Log which resume was selected and why

---

### `utils/human_behaviour.py`

Build functions to simulate human behaviour in Playwright:

```python
def random_sleep(min_sec=1.0, max_sec=2.5):
    """Random sleep between actions"""

def slow_type(page, selector, text, delay_ms_min=50, delay_ms_max=150):
    """Type text character by character with random delays"""
    # Use page.type(selector, text, delay=random_ms) per char

def random_scroll(page):
    """Scroll page randomly up/down before acting"""
    # page.evaluate("window.scrollBy(0, random_amount)")

def move_and_click(page, selector):
    """Move mouse to element with slight offset then click"""
    # Use element.hover() then element.click()
```

All scrapers must use these instead of direct `.click()` and `.fill()`.

---

### `utils/session_manager.py`

Build cookie-based session persistence:

```python
def save_session(platform: str, cookies: list):
    """Save browser cookies to logs/sessions/{platform}.json"""

def load_session(platform: str) -> list | None:
    """Load cookies if file exists and is less than 12 hours old"""

def is_session_valid(platform: str) -> bool:
    """Return True if saved session is < 12 hours old"""
```

In each scraper's `login()`:
- Check `is_session_valid(platform)` → if True, load cookies and skip login form
- If False → do normal login → save session after success

---

### `utils/rate_limiter.py`

Build per-platform daily apply counter:

```python
# Stored in logs/rate_limits.json as {"LinkedIn": {"date": "2026-06-04", "count": 45}}

def can_apply(platform: str) -> bool:
    """Return True if platform hasn't hit daily limit"""

def increment(platform: str):
    """Add 1 to today's count for platform"""

def get_count(platform: str) -> int:
    """Get today's apply count for platform"""

def reset_if_new_day(platform: str):
    """Reset count to 0 if stored date != today"""
```

In each scraper, call `can_apply(platform)` before every application.
If limit hit → log warning + stop scraper for that platform.

---

### `tracker/cooldown_manager.py`

Build company cooldown tracker:

```python
# Stored in logs/cooldowns.json as {"TCS": "2026-05-20", "Infosys": "2026-06-01"}

def is_on_cooldown(company: str) -> bool:
    """Return True if company was applied to within COMPANY_COOLDOWN_DAYS"""

def set_cooldown(company: str):
    """Record today's date as last applied date for company"""

def get_days_since(company: str) -> int:
    """Return days since last applied"""
```

In base_scraper, after extracting company name:
- Check `is_on_cooldown(company)` → if True, skip with log message
- After successful apply → call `set_cooldown(company)`

Also check `blacklist.txt` — never apply to blacklisted companies.
Check `whitelist.txt` — apply to these first before others.

---

### `tracker/status_manager.py`

Build pipeline status updater for the Applied Jobs sheet:

```python
VALID_STATUSES = [
    "Applied ✅",
    "Viewed 👁",
    "Shortlisted ⭐",
    "Interview Scheduled 📅",
    "Interview Done 🤝",
    "Offer Received 🎉",
    "Rejected ❌",
    "Ghosted 👻",
]

def update_status(job_url: str, new_status: str):
    """Find row by Job URL in Applied Jobs sheet and update Status column"""

def get_pipeline_summary() -> dict:
    """Return count of each status across all applied jobs"""
    # Returns: {"Applied ✅": 45, "Interview Scheduled 📅": 3, ...}
```

---

### `tracker/excel_tracker.py`

Create Excel with **7 sheets** using `openpyxl`:

**Sheet 1 — Dashboard (index 0)**
- Title: "🚀 Job Hunt Dashboard"
- Summary table with formulas:
  - Total Applied, Walk-Ins Found, Cold Mails Sent, Manual Pending
  - Interview Rate: `=Shortlisted/TotalApplied` as percentage
  - Best Platform: manual fill cell (yellow highlight)
- Last updated timestamp cell

**Sheet 2 — Applied Jobs**
- Columns: Company Name | Job Title | Location | Date Applied | Platform | AI Score | Resume Used | Job URL | Status | Notes
- Header: Dark blue (#1F4E79)
- Status column: dropdown validation with VALID_STATUSES list
- AI Score column: conditional color — green if ≥8, yellow if 6–7, red if <6
- Alternating row colors: #EBF5FB / #FFFFFF

**Sheet 3 — Walk-In Drives**
- Columns: Company Name | Job Title | Location | Walk-In Date | Walk-In Time | Venue | Platform | Job URL | Contact | Status
- Header: Dark green (#375623)
- Sort by Walk-In Date ascending

**Sheet 4 — Manual Apply Needed**
- Columns: Company Name | Job Title | Location | Date Found | Platform | Job URL | Reason | Status
- Header: Dark orange (#843C0C)
- Status: "Pending ⏳" default

**Sheet 5 — Cold Mails Sent**
- Columns: Company Name | Job Title | HR Name | Recipient Email | Date Sent | Follow-Up Date | Follow-Up Sent | Subject | Status
- Header: Dark purple (#4A235A)
- Follow-Up Date = Date Sent + 5 days (formula: `=D2+5`)
- Follow-Up Sent: "No" default (updated to "Yes ✉️" when follow-up is sent)

**Sheet 6 — Follow-Ups**
- Columns: Company Name | Job Title | Original Date | Follow-Up Date | Sent Date | Status
- Header: Teal (#1A5276)

**Sheet 7 — Skipped Jobs**
- Columns: Company Name | Job Title | Platform | Date | Reason (Fake Entry Level / Blacklisted / Low Score / Cooldown / Duplicate)
- Header: Grey (#424242)
- This sheet is for transparency — log every skipped job with reason

**Common rules:**
- Thin borders all cells, freeze pane A2, Arial size 10
- `init_excel()` only creates if not exists
- Duplicate URL check before insert
- `log_skipped(job, reason)` for Sheet 7

---

### `mailers/followup_mailer.py`

Build `send_followups()` — runs automatically each time `main.py` runs:

- Open Excel, read "Cold Mails Sent" sheet
- For each row where Follow-Up Sent = "No" AND today >= Follow-Up Date:
  - Send follow-up email using `FOLLOWUP_BODY` template
  - Update Follow-Up Sent column to "Yes ✉️" and Sent Date to today
  - Log to "Follow-Ups" sheet
- Max 2 follow-ups per company (track count)

---

### `scrapers/base_scraper.py`

Abstract base class:

```python
class BaseScraper(ABC):
    def __init__(self, platform: str):
        self.platform      = platform
        self.applied_count = 0
        self.logger        = get_logger(platform)

    def run(self) -> dict:
        """Launch browser, login (with session reuse), search, apply. Return summary dict."""

    @abstractmethod
    def login(self, page): ...

    @abstractmethod
    def search_jobs(self, page, keyword: str): ...

    @abstractmethod
    def process_job(self, page, url: str): ...

    def should_apply(self, job: dict, jd_text: str) -> tuple[bool, str]:
        """
        Returns (True/False, reason_if_skipped).
        Checks in this order:
        1. Is company blacklisted?           → skip
        2. Is company on cooldown?           → skip
        3. Is it a fake entry-level job?     → skip
        4. Is URL already in Excel?          → skip (duplicate)
        5. AI relevance score < MIN_AI_SCORE? → skip
        6. Platform rate limit hit?          → skip
        All passed → return True
        """

    def get_resume(self, jd_text: str) -> str:
        """Call select_resume(jd_text) and return path"""
```

Every `process_job` must:
1. Extract title, company, location, URL, full JD text
2. Call `self.should_apply(job, jd_text)` — if False, call `log_skipped()` and return
3. Check walk-in → `log_walkin()` and return
4. Get AI score → store in job dict
5. Select resume → store in job dict
6. Try Easy Apply → on success, `log_applied()` + `set_cooldown()`
7. On no Easy Apply → extract email → cold mail or `log_manual()`

---

### `scrapers/linkedin_scraper.py`

Extends `BaseScraper`:

- **Session reuse**: check `is_session_valid("linkedin")` → load cookies → verify logged in → skip login form if valid
- Login: `https://www.linkedin.com/login`
  - Use `slow_type()` for email and password fields
  - After login success → `save_session("linkedin", context.cookies())`
- Search URL: `https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}&f_E=1&f_AL=true&sortBy=DD`
- Job cards: `.job-card-container` — click each
- Extract: title `.job-details-jobs-unified-top-card__job-title`, company `.job-details-jobs-unified-top-card__company-name`, location `.job-details-jobs-unified-top-card__bullet`, description `.jobs-description__content`
- Call `self.should_apply()` before proceeding
- Easy Apply multi-step form:
  - Loop max 8 steps
  - Upload correct resume (from `get_resume()`) if `input[type="file"]` found
  - Fill phone if empty
  - Answer simple yes/no questions: for `select` elements with options, pick first option
  - Buttons: `aria-label="Continue to next step"` → `aria-label="Review your application"` → `aria-label="Submit application"`
  - After submit → close modal `aria-label="Dismiss"`
  - Call `log_applied(job)` with AI score and resume name
- **CAPTCHA detection**: if `iframe[src*="challenge"]` or `#captcha` appears → call `send_telegram_alert("⚠️ CAPTCHA on LinkedIn — please solve it")`

---

### `scrapers/naukri_scraper.py`

Extends `BaseScraper`:

- Session reuse same pattern as LinkedIn
- Login: `https://www.naukri.com/nlogin/login`
  - Use `slow_type()` for fields
  - Save session after login
- Search: `https://www.naukri.com/it-jobs?k={keyword}&l={location}&experience=0`
- Cards: `.jobTuple` → open in new tab
- Extract from job page: `.jd-header-title`, `.jd-header-comp-name`, `.location-container`, `#job_description`
- Apply button: `button[data-ga-track*="Apply"]` or `button:has-text("Apply")`
- If apply redirects to external site → treat as cold mail opportunity
- CAPTCHA: same detection and Telegram alert

---

### `scrapers/indeed_scraper.py`

Extends `BaseScraper`:

- Login: `https://secure.indeed.com/auth` — email step then password step
- Save session after login
- Search: `https://in.indeed.com/jobs?q={keyword}&l={location}&explvl=entry_level&sort=date`
- Cards: `.job_seen_beacon` → open `h2.jobTitle a`
- Extract: `[data-testid="jobsearch-JobInfoHeader-title"]`, `[data-testid="inlineHeader-companyName"]`, `[data-testid="job-location"]`, `#jobDescriptionText`
- Apply: `button:has-text("Apply now")` or `button:has-text("Easily apply")`
- CAPTCHA detection + Telegram alert

---

### `scrapers/shine_scraper.py`

Extends `BaseScraper`:

- Login: `https://www.shine.com/login/`
- Session reuse + save
- Search: `https://www.shine.com/job-search/{keyword}-jobs?experience=0-2`
- Cards: `.jsx-jobCard` → `a.job-title`
- Apply: `button:has-text("Apply")` or `a:has-text("Apply Now")`
- CAPTCHA detection + Telegram alert

---

### `telegram/bot.py`

Build a **fully working** Telegram bot using `python-telegram-bot==20.7`:

```python
# Commands:
# /start       → Welcome + list of commands
# /run         → Run all platforms now (calls run_all())
# /run linkedin → Run only LinkedIn
# /run naukri  → Run only Naukri
# /run indeed  → Run only Indeed
# /run shine   → Run only Shine
# /status      → Show pipeline summary from Excel
# /walkins     → List today's + upcoming walk-in drives
# /manual      → List pending manual apply jobs (max 10)
# /followups   → Show pending cold mail follow-ups
# /skipped     → Show last 10 skipped jobs with reasons
# /stop        → Gracefully stop the scheduler
# /help        → Show all commands
```

**`/status` response format:**
```
📊 Job Hunt Status — 04 Jun 2026

✅ Applied:          47
⭐ Shortlisted:       4
📅 Interviews:        2
🎉 Offers:            0
❌ Rejected:          8
👻 Ghosted:          12

📬 Cold Mails:       15
🏃 Walk-Ins:          6
⏳ Manual Pending:   11

📈 Response Rate:   8.5%
🏆 Best Platform:   LinkedIn (28 applies)
```

**After every `run_all()` completion, auto-send this message:**
```
🤖 Run Complete — 04 Jun 2026 08:03 AM

✅ Applied:    12
🏃 Walk-Ins:    2
📬 Cold Mails:  3
⏳ Manual:      4
❌ Errors:      1
⏱ Duration:  2m 34s
```

**CAPTCHA alert format:**
```
⚠️ CAPTCHA Detected!
Platform: LinkedIn
Please open your browser and solve the CAPTCHA.
Bot is paused and waiting...
```

After CAPTCHA alert, bot waits 60 seconds then retries automatically.

**Security**: Only respond to messages from `TELEGRAM_CHAT_ID` in config. Ignore all others.

---

### `reports/weekly_report.py`

Build `generate_weekly_report()` — runs every Sunday automatically:

- Read all sheets from Excel
- Generate a summary:
  - Total applies this week vs last week
  - Which platform had most success
  - Which job keyword got most responses
  - Walk-ins attended vs missed
  - Cold mail reply rate
- Save as `reports/weekly_YYYY-MM-DD.txt`
- Send report via Telegram as a formatted message

---

### `main.py`

```python
import argparse, schedule, time
from tracker.excel_tracker import init_excel
from mailers.followup_mailer import send_followups
from config.config import SCHEDULE_TIMES

def run_all(platform="all") -> dict:
    """
    Run scrapers for given platform(s).
    Before scraping: call init_excel(), send_followups()
    After scraping: return summary dict.
    """
    summary = {
        "applied": 0, "walkins": 0, "cold_mails": 0,
        "manual": 0, "skipped": 0, "errors": 0,
        "duration_seconds": 0
    }
    # ... run scrapers, accumulate into summary ...
    return summary

def run_scheduled():
    for t in SCHEDULE_TIMES:
        schedule.every().day.at(t).do(run_all)
    # Every Sunday 9 AM generate weekly report
    schedule.every().sunday.at("09:00").do(generate_weekly_report)
    while True:
        schedule.run_pending()
        time.sleep(30)

# argparse: --schedule, --platform, --followups-only, --status
```

---

### `requirements.txt`

```
playwright==1.44.0
openpyxl==3.1.2
schedule==1.2.1
python-dotenv==1.0.0
python-telegram-bot==20.7
```

---

### `README.md`

Include:
1. Full project idea explanation
2. File structure tree
3. Step-by-step setup (pip install, playwright install, config, Gmail App Password, Telegram bot setup)
4. How to create multiple resume versions
5. How to use blacklist.txt and whitelist.txt
6. All `python main.py` run commands with examples
7. Excel sheet descriptions table (all 7 sheets)
8. Telegram commands list
9. Full decision flow diagram:

```
Job Found on Platform
        ↓
Company Blacklisted?      ──YES──→ Log to Skipped (Blacklisted)
        ↓ NO
Company on Cooldown?      ──YES──→ Log to Skipped (Cooldown)
        ↓ NO
Fake Entry Level?         ──YES──→ Log to Skipped (Fake JD)
        ↓ NO
Already Applied? (URL)    ──YES──→ Log to Skipped (Duplicate)
        ↓ NO
AI Score < 7?             ──YES──→ Log to Skipped (Low Score)
        ↓ NO
Walk-In Drive?            ──YES──→ Log to Walk-In Drives sheet
        ↓ NO
Platform Limit Hit?       ──YES──→ Stop platform for today
        ↓ NO
Select Resume (Python/Java/Fullstack based on JD)
        ↓
Easy Apply Available?     ──YES──→ Auto Apply → Log to Applied Jobs
        ↓ NO                        Set company cooldown
Email Found in JD?        ──YES──→ Personalized Cold Mail → Log to Cold Mails
        ↓ NO
Log to Manual Apply Needed sheet
```

10. Troubleshooting section (CAPTCHA, Gmail auth, session issues)

---

## ⚙️ TECHNICAL REQUIREMENTS

- Python 3.10+
- Playwright `sync_api` (synchronous, NOT async)
- `random.uniform(1.0, 2.5)` sleep between ALL browser actions
- All scrapers must use `human_behaviour.py` functions — no raw `.click()` or `.fill()`
- All credentials in `config/config.py` — zero hardcoding
- Every component wrapped in try/except — one failure never crashes the whole run
- Scrapers are independent — LinkedIn failure does not stop Naukri
- `run_all()` MUST return the summary dict — Telegram bot depends on it
- JSON files in `logs/` for session cookies, rate limits, cooldowns
- Rotate log file daily — `logs/run_YYYYMMDD.log`

---

## ✅ DEFINITION OF DONE

- [ ] All files and folders created with correct structure
- [ ] `python main.py` runs without import errors
- [ ] Excel creates with 7 sheets on first run
- [ ] AI job scorer returns 1–10 score
- [ ] Fresher filter rejects fake entry-level JDs correctly
- [ ] Company cooldown prevents duplicate company applies
- [ ] Rate limiter stops scraper at daily platform limit
- [ ] Session reuse skips login form on second run (< 12 hrs)
- [ ] Resume selector picks correct PDF based on JD keywords
- [ ] Cold mail sends with personalized HR name
- [ ] Follow-up mailer runs automatically
- [ ] Telegram bot responds to all commands
- [ ] Telegram receives run summary after every execution
- [ ] CAPTCHA alert sent via Telegram when detected
- [ ] Skipped jobs logged to Sheet 7 with reason
- [ ] Weekly report generates every Sunday
- [ ] README covers full setup end to end
