"""
Personalised cold-mail sender — deliberately conservative.

Safety rails (configurable in config.py / .env):
  * DRY_RUN .............. write the mail to data/drafts/ instead of sending.
  * REQUIRE_MAIL_CONFIRM . queue for manual approval; never auto-send.
  * MAX_COLD_MAILS_PER_DAY  hard daily cap so this can't become a spam cannon.

Approve queued mails with `python main.py --send-approved` or Telegram /approve.
"""
import json
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from config.config import (
    COLD_MAIL_BODY, COLD_MAIL_SUBJECT, DATA_DIR, DRY_RUN, FOLLOWUP_AFTER_DAYS,
    GMAIL, MAX_COLD_MAILS_PER_DAY, REQUIRE_MAIL_CONFIRM, RESUME_KEYWORD_MAP,
    YOUR_EMAIL, YOUR_NAME, YOUR_PHONE,
)
from tracker import excel_tracker as xl
from utils.logger import get_logger

logger = get_logger("cold_mailer")

_DRAFT_DIR = Path(DATA_DIR) / "drafts"
_QUEUE_FILE = Path(DATA_DIR) / "pending_mail.json"
_COUNT_FILE = Path(DATA_DIR) / "mail_count.json"


# ── small JSON helpers ───────────────────────────────────────────────────────
def _read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _sent_today() -> int:
    data = _read_json(_COUNT_FILE, {})
    if data.get("date") != date.today().isoformat():
        return 0
    return data.get("count", 0)


def _bump_sent_count() -> None:
    today = date.today().isoformat()
    data = _read_json(_COUNT_FILE, {})
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] += 1
    _write_json(_COUNT_FILE, data)


def _first_jd_keyword(jd_text: str) -> str:
    text = (jd_text or "").lower()
    for kws in RESUME_KEYWORD_MAP.values():
        for kw in kws:
            if kw in text:
                return kw
    return "your tech stack"


def _render(job: dict) -> tuple[str, str]:
    # Prefer a personalised LLM draft; fall back to the fixed template.
    try:
        from ai.mail_writer import write_cold_email
        llm = write_cold_email(job)
        if llm is not None:
            return llm
    except Exception as exc:
        logger.warning("[ColdMail] LLM draft failed (%s); using template", exc)

    subject = COLD_MAIL_SUBJECT.format(job_title=job.get("title", ""), your_name=YOUR_NAME)
    body = COLD_MAIL_BODY.format(
        hr_name=job.get("hr_name", "Hiring Manager"),
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        jd_keyword=_first_jd_keyword(job.get("description", "")),
        your_name=YOUR_NAME, your_email=YOUR_EMAIL, your_phone=YOUR_PHONE,
    )
    return subject, body


# ── public API ───────────────────────────────────────────────────────────────
def queue_cold_mail(job: dict) -> str:
    """
    Prepare a cold mail for `job`. Returns one of:
      "skipped" - daily cap hit (no mail prepared)
      "drafted" - written to disk only (DRY_RUN)
      "queued"  - awaiting manual approval (REQUIRE_MAIL_CONFIRM)
      "sent"    - actually delivered
    """
    if _sent_today() >= MAX_COLD_MAILS_PER_DAY:
        logger.warning("[ColdMail] Daily cap (%d) reached; skipping %s",
                       MAX_COLD_MAILS_PER_DAY, job.get("company"))
        return "skipped"

    subject, body = _render(job)
    record = {
        "company": job.get("company", ""), "title": job.get("title", ""),
        "hr_name": job.get("hr_name", "Hiring Manager"),
        "email": job.get("apply_email", ""), "subject": subject, "body": body,
        "resume": job.get("resume", ""), "url": job.get("url", ""),
        "followup_days": FOLLOWUP_AFTER_DAYS,
    }

    if DRY_RUN:
        _DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in record["company"] if c.isalnum())[:30] or "draft"
        draft_path = _DRAFT_DIR / f"{date.today().isoformat()}_{safe}.txt"
        draft_path.write_text(
            f"To: {record['email']}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        record["status"] = "Draft (dry-run)"
        xl.log_cold_mail(record)
        logger.info("[ColdMail] DRY_RUN draft written: %s", draft_path)
        return "drafted"

    if REQUIRE_MAIL_CONFIRM:
        queue = _read_json(_QUEUE_FILE, [])
        queue.append(record)
        _write_json(_QUEUE_FILE, queue)
        record["status"] = "Pending Approval"
        xl.log_cold_mail(record)
        logger.info("[ColdMail] Queued for approval: %s (%s)", record["company"], record["email"])
        return "queued"

    return "sent" if _send(record) else "skipped"


def _send(record: dict) -> bool:
    """Low-level SMTP send via Gmail. Returns True on success."""
    if not GMAIL.get("app_password"):
        logger.error("[ColdMail] No Gmail app password configured; cannot send.")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = f"{GMAIL['sender_name']} <{GMAIL['email']}>"
        msg["To"] = record["email"]
        msg["Subject"] = record["subject"]
        msg.set_content(record["body"])

        resume = Path(record.get("resume", ""))
        if resume.exists():
            msg.add_attachment(resume.read_bytes(), maintype="application",
                               subtype="pdf", filename=resume.name)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL["email"], GMAIL["app_password"])
            smtp.send_message(msg)
        _bump_sent_count()
        logger.info("[ColdMail] Sent to %s (%s)", record["company"], record["email"])
        return True
    except Exception as exc:
        logger.error("[ColdMail] Send failed for %s: %s", record.get("email"), exc)
        return False


def list_pending() -> list[dict]:
    return _read_json(_QUEUE_FILE, [])


def discard_pending(email: str, company: str = "") -> bool:
    """Drop the first queued draft matching `email` (and `company` if given)."""
    queue = _read_json(_QUEUE_FILE, [])
    for i, rec in enumerate(queue):
        if rec.get("email") == email and (not company or rec.get("company") == company):
            queue.pop(i)
            _write_json(_QUEUE_FILE, queue)
            logger.info("[ColdMail] Discarded pending draft to %s (%s)", email, company)
            return True
    return False


def send_approved(limit: int | None = None) -> dict:
    """Send queued mails (respecting the daily cap). Returns a small summary."""
    queue = _read_json(_QUEUE_FILE, [])
    sent, failed, remaining = 0, 0, []
    for record in queue:
        if (limit is not None and sent >= limit) or _sent_today() >= MAX_COLD_MAILS_PER_DAY:
            remaining.append(record)
            continue
        if _send(record):
            sent += 1
        else:
            failed += 1
            remaining.append(record)
    _write_json(_QUEUE_FILE, remaining)
    logger.info("[ColdMail] Approved send: %d sent, %d failed, %d left", sent, failed, len(remaining))
    return {"sent": sent, "failed": failed, "remaining": len(remaining)}
