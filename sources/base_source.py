"""
Abstract base for ToS-friendly job sources.

A "source" fetches normalised job dicts from a *public API or RSS feed* — it
never logs in as you, never drives a real browser, and never tries to evade
bot-detection. The shared decision pipeline (filter -> score -> route) lives
here so every source behaves identically.

Normalised job dict shape:
    {
        "title", "company", "location", "url",
        "description", "source", "apply_email" (optional)
    }
"""
from abc import ABC, abstractmethod

from ai.hr_name_extractor import extract_hr_name
from ai.job_scorer import score_job
from config.config import JOB_KEYWORDS, MAX_JOBS_PER_RUN, MIN_AI_SCORE, USE_RESUME_PROFILE
from tracker import excel_tracker as xl
from tracker.cooldown_manager import (
    is_blacklisted, is_on_cooldown, is_whitelisted, set_cooldown,
)
from utils.email_extractor import extract_email
from utils.fresher_filter import is_fake_entry_level
from utils.logger import get_logger
from utils.rate_limiter import can_apply, get_count, increment
from utils.resume_selector import select_resume
from utils.walkin_detector import extract_walkin_details, is_walkin


def get_search_keywords() -> list[str]:
    """Keywords to search for: resume-derived when enabled, else config list."""
    if USE_RESUME_PROFILE:
        try:
            from utils.resume_parser import get_profile
            kws = get_profile().get("search_keywords", [])
            if kws:
                return kws
        except Exception:
            pass
    return JOB_KEYWORDS


class BaseSource(ABC):
    name = "base"
    # Sources where the jobs already match criteria YOU set (e.g. your own
    # LinkedIn/Naukri job-alert emails) are pre-qualified: we still score them
    # for sorting, but we don't hard-skip on a low score.
    pre_qualified = False

    def __init__(self, mailer=None):
        self.logger = get_logger(self.name)
        self.mailer = mailer  # injected cold_mailer module (optional)
        self.summary = {
            "queued_manual": 0, "walkins": 0, "cold_mails": 0,
            "skipped": 0, "errors": 0, "fetched": 0,
        }

    # ── Each concrete source implements just this ───────────────────────────
    @abstractmethod
    def fetch_jobs(self, keyword: str) -> list[dict]:
        """Return a list of normalised job dicts for one keyword."""

    # ── Shared decision pipeline ────────────────────────────────────────────
    def should_apply(self, job: dict) -> tuple[bool, str]:
        company = job.get("company", "")
        jd = job.get("description", "")
        title = job.get("title", "")

        if is_blacklisted(company):
            return False, "Blacklisted"
        if is_on_cooldown(company):
            return False, "Cooldown"
        if is_fake_entry_level(jd, title, company):
            return False, "Fake Entry Level"
        if xl.is_duplicate(job.get("url", "")):
            return False, "Duplicate"
        score = score_job(jd, title, company)
        job["score"] = score
        if score < MIN_AI_SCORE and not self.pre_qualified:
            return False, "Low Score"
        if not can_apply(self.name):
            return False, "Rate Limit"
        return True, ""

    def process_job(self, job: dict) -> None:
        try:
            job.setdefault("source", self.name)

            # Walk-in drives are logged separately regardless of apply path.
            if is_walkin(job.get("description", "")):
                job.update(extract_walkin_details(job["description"]))
                xl.log_walkin(job)
                self.summary["walkins"] += 1
                self.logger.info("[Walk-in] %s - %s", job.get("company"), job.get("title"))
                return

            ok, reason = self.should_apply(job)
            if not ok:
                xl.log_skipped(job, reason)
                self.summary["skipped"] += 1
                return

            job["resume"] = select_resume(job.get("description", ""))
            email = job.get("apply_email") or extract_email(job.get("description", ""))

            if email and self.mailer is not None:
                job["apply_email"] = email
                job["hr_name"] = extract_hr_name(job.get("description", ""))
                result = self.mailer.queue_cold_mail(job)
                if result == "skipped":
                    xl.log_manual(job, "Cold-mail cap reached - review & apply")
                    self.summary["queued_manual"] += 1
                else:
                    self.summary["cold_mails"] += 1
                    set_cooldown(job.get("company", ""))
                    increment(self.name)
            else:
                # No Easy Apply auto-submit in responsible mode: hand off to you.
                xl.log_manual(job, "Review & submit (resume: %s)" % job["resume"].split("/")[-1])
                self.summary["queued_manual"] += 1
                increment(self.name)
        except Exception as exc:  # one bad job never kills the run
            self.summary["errors"] += 1
            self.logger.error("process_job failed: %s", exc, exc_info=True)

    def run(self) -> dict:
        self.logger.info("=== Source '%s' starting (today's count: %d) ===",
                         self.name, get_count(self.name))
        seen_urls = set()
        processed = 0
        keywords = get_search_keywords()
        self.logger.info("[%s] search keywords: %s", self.name, keywords)
        for keyword in keywords:
            if processed >= MAX_JOBS_PER_RUN:
                break
            try:
                jobs = self.fetch_jobs(keyword)
            except Exception as exc:
                self.summary["errors"] += 1
                self.logger.error("fetch_jobs('%s') failed: %s", keyword, exc)
                continue
            self.summary["fetched"] += len(jobs)
            for job in jobs:
                if processed >= MAX_JOBS_PER_RUN:
                    break
                url = job.get("url", "")
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)
                self.process_job(job)
                processed += 1
        self.logger.info("=== Source '%s' done: %s ===", self.name, self.summary)
        return self.summary
