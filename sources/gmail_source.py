"""
Gmail job-alert source — the ToS-safe way to get LinkedIn (and Naukri/Indeed)
jobs into the pipeline.

How it works: you set up Job Alerts on LinkedIn/Naukri/Indeed (email, daily).
Those sites email matching jobs to YOUR Gmail. This source logs into your own
inbox over IMAP, parses the alert emails, and feeds the jobs through the same
filter -> score -> route pipeline. You never automate the LinkedIn website, so
there is no scraping and no ban risk — you're only reading your own mail.

Setup: GMAIL_EMAIL + GMAIL_APP_PASSWORD in .env (same App Password as SMTP),
and IMAP enabled in Gmail settings (Settings -> Forwarding and POP/IMAP).
"""
import email
import imaplib
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from config.config import GMAIL, SOURCES
from sources.base_source import BaseSource

_IMAP_HOST = "imap.gmail.com"
_LINKEDIN_VIEW = re.compile(r"/jobs/view/(\d+)")
_GENERIC_JOB_LINK = re.compile(r"(job|/viewjob|/jobs/|jobid|job_id)", re.IGNORECASE)
_NAUKRI_LINK = re.compile(r"/jd/job-listings-|/job-listings-|job-listings-", re.IGNORECASE)


def _decode(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _html_body(msg) -> str:
    """Return the best HTML (or text) body from an email message."""
    if msg.is_multipart():
        html, text = "", ""
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get("Content-Disposition", "").startswith("attachment"):
                continue
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                continue
            if ctype == "text/html":
                html += decoded
            elif ctype == "text/plain":
                text += decoded
        return html or text
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return ""


class GmailSource(BaseSource):
    name = "gmail"
    pre_qualified = True  # jobs come from alerts YOU configured -> already relevant

    def __init__(self, mailer=None):
        super().__init__(mailer=mailer)
        self._served = False  # parse the inbox once, not per keyword

    # base.run() calls this per keyword; we parse the inbox once and dedupe.
    def fetch_jobs(self, keyword: str) -> list[dict]:
        if self._served:
            return []
        self._served = True
        return self._parse_inbox()

    # ── IMAP plumbing ────────────────────────────────────────────────────────
    def _parse_inbox(self) -> list[dict]:
        cfg = SOURCES.get("gmail", {})
        if not GMAIL.get("email") or not GMAIL.get("app_password"):
            self.logger.warning("[gmail] No Gmail email/app password set; skipping.")
            return []

        # Steady-state uses the configured window; a one-time catch-up can widen
        # it via GMAIL_LOOKBACK_HOURS (e.g. `set GMAIL_LOOKBACK_HOURS=240`).
        lookback_hours = int(os.getenv("GMAIL_LOOKBACK_HOURS", cfg.get("lookback_hours", 4)))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        # IMAP SINCE is day-granular, so we coarse-filter by date here and then
        # fine-filter each email by its actual timestamp to the last N hours.
        since = cutoff.strftime("%d-%b-%Y")
        senders = cfg.get("senders", [])
        max_emails = cfg.get("max_emails", 60)

        jobs, skipped_old = [], 0
        try:
            imap = imaplib.IMAP4_SSL(_IMAP_HOST)
            imap.login(GMAIL["email"], GMAIL["app_password"])
            imap.select("INBOX", readonly=True)  # readonly: we never modify your mail

            uids = []
            for sender in senders:
                typ, data = imap.search(None, f'(FROM "{sender}" SINCE "{since}")')
                if typ == "OK" and data and data[0]:
                    uids.extend(data[0].split())
            uids = list(dict.fromkeys(uids))[-max_emails:]  # newest N, deduped
            self.logger.info("[gmail] %d candidate emails since %s; keeping last %dh",
                             len(uids), since, lookback_hours)

            for uid in uids:
                typ, msg_data = imap.fetch(uid, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                if not self._within_window(msg.get("Date", ""), cutoff):
                    skipped_old += 1
                    continue
                sender = _decode(msg.get("From", "")).lower()
                jobs.extend(self._parse_email(_html_body(msg), sender))

            imap.logout()
            if skipped_old:
                self.logger.info("[gmail] skipped %d email(s) older than %dh",
                                 skipped_old, lookback_hours)
        except imaplib.IMAP4.error as exc:
            self.logger.error("[gmail] IMAP login/search failed: %s "
                              "(check App Password + IMAP enabled)", exc)
        except Exception as exc:
            self.logger.error("[gmail] inbox parse failed: %s", exc, exc_info=True)

        self.logger.info("[gmail] parsed %d jobs from alert emails", len(jobs))
        return jobs

    @staticmethod
    def _within_window(date_header: str, cutoff: datetime) -> bool:
        """True if the email's Date is at/after the cutoff. Keep it if unparseable."""
        if not date_header:
            return True
        try:
            sent = parsedate_to_datetime(date_header)
            if sent.tzinfo is None:
                sent = sent.replace(tzinfo=timezone.utc)
            return sent >= cutoff
        except (TypeError, ValueError):
            return True

    # Anchor text that is never a real job (headers/footers of alert emails).
    _NON_JOB = (
        "manage alerts", "see all jobs", "view all", "unsubscribe",
        "actively recruiting", "view job", "your job alert", "see more jobs",
        "update your preferences", "easy apply",
    )

    # ── HTML parsing ──────────────────────────────────────────────────────────
    def _parse_email(self, html: str, sender: str) -> list[dict]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        platform = ("LinkedIn" if "linkedin" in sender else
                    "Naukri" if "naukri" in sender else
                    "Indeed" if "indeed" in sender else "Email")
        linkedin = platform == "LinkedIn"
        naukri = platform == "Naukri"
        # Persist the real platform as the job's source so the UI can group by
        # platform (LinkedIn / Naukri / Indeed), not lump all alert mail as
        # "gmail". Rate-limiting still keys on self.name internally, unaffected.
        source_key = {"LinkedIn": "linkedin", "Naukri": "naukri",
                      "Indeed": "indeed"}.get(platform, "email")

        # LinkedIn renders several <a> per job (logo / title-only / rich block).
        # Group by job and keep the richest text so company+location survive.
        best: dict[str, dict] = {}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            is_li = bool(_LINKEDIN_VIEW.search(href))
            is_naukri = naukri and self._looks_like_naukri_job_link(href, a.get_text(" ", strip=True))
            # For LinkedIn, only real job-view links count (drops header/footer).
            if linkedin:
                if not is_li:
                    continue
            elif not (is_li or is_naukri or _GENERIC_JOB_LINK.search(href)):
                continue
            if any(w in href.lower() for w in ("unsubscribe", "settings", "/help", "email_open")):
                continue

            text = a.get_text("\n", strip=True)
            url = self._clean_url(href, is_li)
            key = _LINKEDIN_VIEW.search(href).group(1) if is_li else url
            cur = best.get(key)
            if cur is None or len(text) > len(cur["text"]):
                best[key] = {"url": url, "text": text}

        jobs = []
        for entry in best.values():
            title, company, location = self._parse_job_text(entry["text"])
            if naukri and not _NAUKRI_LINK.search(entry["url"]):
                continue
            if not title or title.lower() in self._NON_JOB:
                continue
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": entry["url"],
                "description": f"{title} {company} {location}".strip(),
                "source": source_key,
                "platform": platform,
            })
        return jobs

    @staticmethod
    def _looks_like_naukri_job_link(href: str, text: str) -> bool:
        """Keep only direct Naukri job-listing links, not footers/marketing."""
        haystack = f"{href} {text}".lower()
        if any(w in haystack for w in GmailSource._NON_JOB):
            return False
        if any(w in haystack for w in (
            "terms", "privacy", "security advice", "feedback", "ambitionbox",
            "recommendedjobs", "update profile", "get app", "report a problem",
        )):
            return False
        return bool(_NAUKRI_LINK.search(href))

    @staticmethod
    def _parse_job_text(text: str) -> tuple[str, str, str]:
        """Split 'Title \\n Company · Location (mode) \\n ...' into its parts."""
        lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
        if not lines:
            return "", "", ""
        title = lines[0]
        company, location = "", ""
        for ln in lines[1:]:
            if "·" in ln:  # LinkedIn separates company and location with a middot
                parts = [p.strip() for p in ln.split("·")]
                company = parts[0]
                location = parts[1] if len(parts) > 1 else ""
                break
            if not company and ln.lower() not in GmailSource._NON_JOB:
                company = ln  # fallback when there's no middot line
        return title, company, location

    @staticmethod
    def _clean_url(href: str, is_linkedin: bool) -> str:
        if is_linkedin:
            jid = _LINKEDIN_VIEW.search(href).group(1)
            return f"https://www.linkedin.com/jobs/view/{jid}/"
        return href.split("?")[0]

