"""
Indeed jobs source — DIRECT, by parsing the public search-results page.

Indeed embeds its result cards as JSON inside the search page, in a script tag:

    window.mosaic.providerData["mosaic-provider-jobcards"] = {...}

We fetch the search page and pull jobs out of that blob. No login. Indeed runs
Cloudflare anti-bot that blocks plain HTTP clients, so we use curl_cffi with
browser TLS impersonation (impersonate="chrome") — that's enough to fetch the
page even from datacenter IPs. If Indeed ever serves a challenge instead, we
fail soft (log a warning, return []) and never break the run.
"""
import json
import re

from curl_cffi import requests as creq

from config.config import SOURCES
from sources.base_source import BaseSource

# The jobcards blob is assigned to this global in a <script> on the results page.
_MOSAIC_RE = re.compile(
    r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});',
    re.DOTALL,
)
_PER_PAGE = 10  # Indeed paginates results in blocks of 10 (start=0,10,20…)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class IndeedSource(BaseSource):
    name = "indeed"
    pre_qualified = True  # cards carry no full JD; score for sorting, don't hard-skip

    def fetch_jobs(self, keyword: str) -> list[dict]:
        cfg = SOURCES.get("indeed", {})
        domain = cfg.get("domain", "in.indeed.com")
        location = cfg.get("location", "India")
        pages = max(1, int(cfg.get("pages", 2)))
        # Browser TLS impersonation beats Indeed's Cloudflare check where plain
        # requests gets a 403.
        session = creq.Session(impersonate="chrome", headers=_HEADERS)

        out: list[dict] = []
        for page in range(pages):
            params = {"q": keyword, "l": location, "sort": "date",
                      "start": page * _PER_PAGE}
            try:
                resp = session.get(f"https://{domain}/jobs", params=params, timeout=25)
            except Exception as exc:
                self.logger.error("[indeed] '%s' page %d request failed: %s",
                                   keyword, page, exc)
                break
            if resp.status_code in (403, 429) or "/hcaptcha" in resp.url:
                self.logger.warning("[indeed] blocked/challenged (HTTP %d) on '%s' "
                                    "— Indeed is anti-bot; backing off.",
                                    resp.status_code, keyword)
                break
            if resp.status_code != 200:
                self.logger.warning("[indeed] '%s' page %d -> HTTP %d; stopping.",
                                    keyword, page, resp.status_code)
                break
            cards = self._parse(resp.text, domain)
            if not cards:
                # No blob usually means a challenge/empty page — stop paging.
                break
            out.extend(cards)
            if len(cards) < _PER_PAGE:
                break

        self.logger.info("[indeed] '%s' -> %d jobs", keyword, len(out))
        return out

    def _parse(self, html: str, domain: str) -> list[dict]:
        m = _MOSAIC_RE.search(html or "")
        if not m:
            return []
        try:
            blob = json.loads(m.group(1))
        except ValueError:
            return []
        results = (blob.get("metaData", {})
                       .get("mosaicProviderJobCardsModel", {})
                       .get("results", []) or [])
        jobs = []
        for r in results:
            title = (r.get("title") or r.get("displayTitle") or "").strip()
            jobkey = r.get("jobkey") or r.get("jobKey")
            if not title or not jobkey:
                continue
            posted = self._posted(r)
            company = (r.get("company") or "").strip()
            location = (r.get("formattedLocation")
                        or r.get("jobLocationCity") or "").strip()
            jobs.append({
                "title": title,
                "company": company,
                "location": location or "—",
                "url": f"https://{domain}/viewjob?jk={jobkey}",
                "description": f"{title} {company} {location}".strip(),
                "source": self.name,
                "platform": "Indeed",
                "posted_at": posted,   # ISO end-of-day, or '' (falls back to Date Found)
                "posted": posted[:10] if posted else
                          (r.get("formattedRelativeTime") or "").strip(),
            })
        return jobs

    @staticmethod
    def _posted(r: dict) -> str:
        """End-of-day ISO from pubDate (epoch ms), else '' (display uses the
        card's relative-time text instead)."""
        ms = r.get("pubDate") or r.get("createDate")
        if ms:
            try:
                from datetime import datetime, timezone
                day = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc) \
                    .strftime("%Y-%m-%d")
                return f"{day}T23:59:59"
            except (TypeError, ValueError, OSError):
                pass
        return ""
