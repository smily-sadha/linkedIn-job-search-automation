"""
Naukri jobs source — DIRECT.

Naukri sits behind Akamai Bot Manager, which blocks plain HTTP, TLS-impersonated
HTTP, and even headless browsers (406 "recaptcha required" / 403 Access Denied).
So this source has two paths:

  • Proxy path (reliable): when SCRAPER_API_KEY is set, the rendered search page
    is fetched through a scraping-API proxy that solves Akamai + uses residential
    IPs, and we parse the job cards out of the returned HTML.
  • Direct path (best-effort): otherwise it tries Naukri's internal jobapi with
    curl_cffi browser impersonation — works only when Akamai isn't challenging
    your IP (rare). Fails soft.

Either way it never breaks a run. Set SCRAPER_API_KEY in .env to switch the
proxy path on (ScraperAPI/ZenRows/ScrapingBee free trials ≈ 1000 calls/month).
"""
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

from config.config import SOURCES
from sources.base_source import BaseSource
from utils import scrape_proxy

_API = "https://www.naukri.com/jobapi/v3/search"
_BASE = "https://www.naukri.com"
_PER_PAGE = 20

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "appid": "109",
    "systemid": "Naukri",
    "Referer": "https://www.naukri.com/",
}


class NaukriSource(BaseSource):
    name = "naukri"
    # Keyword search you defined; the API gives a short JD blurb, so score for
    # sorting but don't hard-skip — same stance as the other alert-style sources.
    pre_qualified = True

    def fetch_jobs(self, keyword: str) -> list[dict]:
        cfg = SOURCES.get("naukri", {})
        if scrape_proxy.is_enabled():
            return self._fetch_via_proxy(keyword, cfg)
        return self._fetch_direct(keyword, cfg)

    # ── Proxy path (reliable, beats Akamai) ─────────────────────────────────────
    def _fetch_via_proxy(self, keyword: str, cfg: dict) -> list[dict]:
        seo = keyword.lower().replace(" ", "-") + "-jobs"
        url = f"{_BASE}/{seo}"
        resp = scrape_proxy.get(url, render=True)
        if resp is None or resp.status_code != 200:
            self.logger.warning("[naukri] proxy fetch '%s' -> HTTP %s; skipping.",
                                keyword, getattr(resp, "status_code", "error"))
            return []
        jobs = self._parse_html(resp.text)
        self.logger.info("[naukri] (proxy) '%s' -> %d jobs", keyword, len(jobs))
        return jobs

    def _parse_html(self, html: str) -> list[dict]:
        """Parse rendered Naukri SRP job cards. Selectors have fallbacks since
        Naukri tweaks its markup; anything unparseable is skipped."""
        soup = BeautifulSoup(html or "", "html.parser")
        out: list[dict] = []
        cards = soup.select("div.srp-jobtuple-wrapper") or soup.select("article.jobTuple")
        for card in cards:
            a = card.select_one("a.title") or card.select_one("a.jobTupleHeader, a[href*='/job-listings-']")
            if not a or not a.get("href"):
                continue
            title = a.get_text(strip=True)
            url = a["href"].split("?")[0]
            company = self._sel(card, "a.comp-name", "a.subTitle", ".comp-name", ".companyInfo")
            location = self._sel(card, "span.locWdth", ".loc-wrap .loc", ".locationsContainer", ".location")
            posted = self._sel(card, "span.job-post-day", ".job-post-day", ".jobTupleFooter .fleft")
            if not title:
                continue
            out.append({
                "title": title,
                "company": company,
                "location": location or "—",
                "url": url,
                "description": f"{title} {company} {location}".strip(),
                "source": self.name,
                "platform": "Naukri",
                "posted_at": "",        # relative text only; freshness uses 'posted'
                "posted": posted,       # e.g. "3 Days Ago" — parsed by the UI
            })
        return out

    @staticmethod
    def _sel(card, *selectors: str) -> str:
        for sel in selectors:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return ""

    # ── Direct path (best-effort, usually blocked by Akamai) ────────────────────
    def _fetch_direct(self, keyword: str, cfg: dict) -> list[dict]:
        pages = max(1, int(cfg.get("pages", 2)))
        # curl_cffi with browser TLS impersonation; warm up by loading the search
        # page first so the API call carries real cookies. (May still hit
        # Naukri's Akamai recaptcha; set SCRAPER_API_KEY to use the proxy path.)
        session = creq.Session(impersonate="chrome", headers=_HEADERS)
        seo = keyword.lower().replace(" ", "-") + "-jobs"
        try:
            session.get(f"{_BASE}/{seo}", timeout=25)  # warm-up for cookies
        except Exception:
            pass

        out: list[dict] = []
        for page in range(1, pages + 1):
            params = {
                "noOfResults": _PER_PAGE,
                "urlType": "search_by_keyword",
                "searchType": "adv",
                "keyword": keyword,
                "pageNo": page,
                "k": keyword,
                "seoKey": seo,
            }
            try:
                resp = session.get(_API, params=params, timeout=25)
            except Exception as exc:
                self.logger.error("[naukri] '%s' page %d request failed: %s",
                                   keyword, page, exc)
                break
            if resp.status_code in (401, 403, 429, 406):
                # 406 = "recaptcha required": Naukri flagged the IP as a bot
                # (common on datacenter/VPN IPs; usually fine from a home IP).
                self.logger.warning("[naukri] blocked/limited (HTTP %d) on '%s' "
                                    "— Naukri wants a captcha for this IP; backing "
                                    "off.", resp.status_code, keyword)
                break
            if resp.status_code != 200:
                self.logger.warning("[naukri] '%s' page %d -> HTTP %d; stopping.",
                                    keyword, page, resp.status_code)
                break
            try:
                details = resp.json().get("jobDetails", []) or []
            except ValueError:
                self.logger.warning("[naukri] '%s' page %d: non-JSON response "
                                    "(likely an anti-bot page); stopping.", keyword, page)
                break
            cards = [self._to_job(j) for j in details]
            out.extend(c for c in cards if c)
            if len(details) < _PER_PAGE:
                break  # last page

        self.logger.info("[naukri] '%s' -> %d jobs", keyword, len(out))
        return out

    def _to_job(self, j: dict) -> "dict | None":
        title = (j.get("title") or "").strip()
        url = j.get("jdURL") or ""
        if not title or not url:
            return None
        if url.startswith("/"):
            url = _BASE + url
        company = (j.get("companyName") or "").strip()
        location = self._placeholder(j, "location")
        posted_iso, posted_disp = self._posted(j)
        jd = (j.get("jobDescription") or
              f"{title} {company} {location} {self._placeholder(j, 'experience')}").strip()
        return {
            "title": title,
            "company": company,
            "location": location or "—",
            "url": url.split("?")[0],
            "description": jd,
            "source": self.name,
            "platform": "Naukri",
            "posted_at": posted_iso,   # ISO (for the freshness filter)
            "posted": posted_disp,     # YYYY-MM-DD or relative text (for display)
        }

    @staticmethod
    def _placeholder(j: dict, kind: str) -> str:
        for p in j.get("placeholders", []) or []:
            if p.get("type") == kind:
                return (p.get("label") or "").strip()
        return ""

    @staticmethod
    def _posted(j: dict) -> tuple[str, str]:
        """Return (iso_for_filter, display) from createdDate (epoch ms) or the
        footer label like '3 Days Ago'."""
        created = j.get("createdDate") or j.get("createdDateInMs")
        if created:
            try:
                dt = datetime.fromtimestamp(int(created) / 1000, tz=timezone.utc)
                day = dt.strftime("%Y-%m-%d")
                # end-of-day anchor keeps day-granular dates off the midnight edge
                return f"{day}T23:59:59", day
            except (TypeError, ValueError, OSError):
                pass
        footer = (j.get("footerPlaceholderLabel") or "").strip()
        return "", footer  # display-only; freshness falls back to Date Found
