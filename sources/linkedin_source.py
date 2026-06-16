"""
LinkedIn jobs source — direct, via the PUBLIC guest job-search endpoint.

This hits the same unauthenticated endpoint LinkedIn's own logged-out job
search uses to render result cards:

    https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

No login, no cookies, no account — so there's no account to ban. The only
realistic failure is LinkedIn rate-limiting your IP (HTTP 429), which we detect
and back off from cleanly. The endpoint returns an HTML fragment of job cards;
we parse title / company / location / posting date / job URL out of each and
feed them through the same score -> filter -> route pipeline as every other
source.

Note: scraping LinkedIn is against its Terms of Service even via this public
endpoint. This source is OFF unless you enable it in config.SOURCES. The cards
carry no full description, so jobs are scored on title+company (like the Gmail
alert source) and the source is pre-qualified so a thin description doesn't
hard-drop relevant roles.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

from config.config import SOURCES
from sources.base_source import BaseSource

_GUEST_API = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
_PER_PAGE = 25  # the guest endpoint pages in fixed blocks of 25

# A plain browser-like UA; the guest endpoint refuses obvious bots / blank UAs.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


class LinkedInSource(BaseSource):
    name = "linkedin"
    # Jobs come from a keyword search YOU defined (same as your saved alerts),
    # and the public cards carry no full JD — so we score for sorting but don't
    # hard-skip on a title-only low score. Mirrors the Gmail alert source.
    pre_qualified = True

    def fetch_jobs(self, keyword: str) -> list[dict]:
        cfg = SOURCES.get("linkedin", {})
        location = cfg.get("location", "India")
        pages = max(1, int(cfg.get("pages", 2)))
        within_hours = int(cfg.get("posted_within_hours", 0) or 0)

        params = {
            "keywords": keyword,
            "location": location,
            "sortBy": "DD",  # date descending → freshest first
        }
        if within_hours > 0:
            params["f_TPR"] = f"r{within_hours * 3600}"  # time-posted range, in seconds

        session = requests.Session()
        session.headers.update(_HEADERS)
        out: list[dict] = []
        for page in range(pages):
            params["start"] = page * _PER_PAGE
            try:
                resp = session.get(_GUEST_API, params=params, timeout=20)
            except requests.RequestException as exc:
                self.logger.error("[linkedin] '%s' page %d request failed: %s",
                                   keyword, page, exc)
                break
            if resp.status_code == 429:
                self.logger.warning("[linkedin] rate-limited (429) on '%s' page %d "
                                    "— backing off for this keyword.", keyword, page)
                break
            if resp.status_code != 200:
                self.logger.warning("[linkedin] '%s' page %d -> HTTP %d; stopping.",
                                    keyword, page, resp.status_code)
                break
            cards = self._parse_cards(resp.text)
            out.extend(cards)
            if len(cards) < _PER_PAGE:
                break  # last page reached
            time.sleep(1.5)  # be gentle between page requests

        self.logger.info("[linkedin] '%s' -> %d jobs", keyword, len(out))
        return out

    # ── HTML parsing ──────────────────────────────────────────────────────────
    def _parse_cards(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html or "", "html.parser")
        jobs: list[dict] = []
        for card in soup.select("li"):
            link = card.find("a", class_="base-card__full-link") or \
                card.select_one("a[href*='/jobs/view/']")
            if not link or not link.get("href"):
                continue
            url = self._clean_url(link["href"])
            if not url:
                continue
            title = self._text(card, "h3.base-search-card__title")
            company = self._text(card, "h4.base-search-card__subtitle")
            location = self._text(card, ".job-search-card__location")
            posted = self._posted_date(card)
            if not title:
                continue
            # Guest cards give only a day-granular date. For the hour-based
            # freshness filter, anchor to END of that day so yesterday's jobs
            # aren't dropped at the midnight boundary (LinkedIn's f_TPR already
            # bounds the window server-side); keep the bare date for display.
            posted_at = f"{posted}T23:59:59" if posted else ""
            jobs.append({
                "title": title,
                "company": company,
                "location": location or "—",
                "url": url,
                "description": f"{title} {company} {location}".strip(),
                "source": self.name,
                "platform": "LinkedIn",
                "posted_at": posted_at,     # end-of-day ISO (for the freshness filter)
                "posted": posted,           # YYYY-MM-DD (for display)
            })
        return jobs

    @staticmethod
    def _text(card, selector: str) -> str:
        el = card.select_one(selector)
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _posted_date(card) -> str:
        """The card's posting date as YYYY-MM-DD, or '' if absent."""
        t = card.find("time")
        if t and t.get("datetime"):
            return t["datetime"][:10]
        return ""

    @staticmethod
    def _clean_url(href: str) -> str:
        """Canonical jobs/view URL keyed on the numeric posting id.

        Guest links look like '/jobs/view/<slug>-at-<company>-<id>'; we pull the
        trailing id and rebuild the same canonical form the Gmail source uses, so
        the same posting from both paths dedupes to one row.
        """
        if "/jobs/view/" not in href:
            return ""
        tail = href.split("/jobs/view/", 1)[1].split("?")[0]
        ids = re.findall(r"\d+", tail)
        if ids:
            return f"https://www.linkedin.com/jobs/view/{ids[-1]}/"
        return href.split("?")[0]
