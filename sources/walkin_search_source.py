"""
Walk-in drive hunter — searches Google for walk-in interview drives.

Unlike the other sources (which only catch walk-ins mentioned *inside* a job
description), this one actively goes looking: it runs walk-in queries through
Google's official Custom Search JSON API, then pulls the date / time / venue out
of each result (snippet first, then the landing page for a fuller address) and
records them straight into the Walk-In Drives sheet.

Uses the official API (free 100 queries/day) — ToS-safe and reliable, no
scraping of google.com. Stays OFF until GOOGLE_API_KEY + GOOGLE_CSE_ID are set
in .env, runs only a few queries per run to stay inside the free quota, and
fails soft so a search hiccup never breaks a run.
"""
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config.config import GOOGLE_API_KEY, GOOGLE_CSE_ID, SOURCES
from sources.base_source import BaseSource, get_search_keywords
from tracker import excel_tracker as xl
from utils.walkin_detector import extract_walkin_details, is_walkin

_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Walk-in query templates. {role} {loc} {year} are filled per run; kept few so a
# run uses only a handful of the free 100 daily Custom Search calls.
_QUERY_TEMPLATES = [
    '"walk-in drive" {role} jobs {loc}',
    '"walk in interview" {role} {loc} {year}',
    'walk-in drive hiring {loc} this week',
    '"walk-in" interview {role} {loc}',
]


class WalkinSearchSource(BaseSource):
    name = "walkin_search"

    def __init__(self, mailer=None):
        super().__init__(mailer=mailer)
        self._served = False  # run the searches once per run, not per keyword

    def fetch_jobs(self, keyword: str) -> list[dict]:
        if self._served:
            return []
        self._served = True
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            self.logger.warning("[walkin_search] GOOGLE_API_KEY/GOOGLE_CSE_ID not "
                                "set; skipping. (Free key at programmablesearchengine.google.com)")
            return []

        cfg = SOURCES.get("walkin_search", {})
        location = cfg.get("location", "India")
        queries = self._build_queries(location, cfg.get("max_queries", 4))
        seen, out = set(), []
        for q in queries:
            for item in self._search(q, cfg):
                url = item.get("link", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                job = self._to_walkin(item, location, cfg)
                if job:
                    out.append(job)
        self.logger.info("[walkin_search] %d quer%s -> %d walk-in candidate(s)",
                         len(queries), "y" if len(queries) == 1 else "ies", len(out))
        return out

    # Walk-ins bypass scoring/cold-mail entirely — log them straight to the
    # Walk-In Drives sheet (deduped against everything already recorded).
    def process_job(self, job: dict) -> None:
        try:
            url = job.get("url", "")
            if url and xl.is_duplicate(url):
                self.summary["skipped"] += 1
                return
            xl.log_walkin(job)
            self.summary["walkins"] += 1
            self.logger.info("[Walk-in] %s | %s %s | %s",
                             job.get("company") or job.get("title"),
                             job.get("walkin_date") or "date?",
                             job.get("walkin_time") or "", job.get("venue") or "venue?")
        except Exception as exc:
            self.summary["errors"] += 1
            self.logger.error("[walkin_search] log failed: %s", exc, exc_info=True)

    # ── Query building ────────────────────────────────────────────────────────
    def _build_queries(self, location: str, max_queries: int) -> list[str]:
        roles = get_search_keywords() or ["jobs"]
        year = datetime.now().year
        queries: list[str] = []
        for i, tmpl in enumerate(_QUERY_TEMPLATES):
            role = roles[i % len(roles)]
            q = tmpl.format(role=role, loc=location, year=year)
            if q not in queries:
                queries.append(q)
            if len(queries) >= max_queries:
                break
        return queries

    # ── Custom Search API ──────────────────────────────────────────────────────
    def _search(self, query: str, cfg: dict) -> list[dict]:
        params = {
            "key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query,
            "num": min(10, int(cfg.get("results_per_query", 10))),
        }
        if cfg.get("date_restrict"):
            params["dateRestrict"] = cfg["date_restrict"]
        try:
            resp = requests.get(_CSE_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            self.logger.error("[walkin_search] search '%s' failed: %s", query, exc)
            return []
        if resp.status_code == 429:
            self.logger.warning("[walkin_search] daily quota hit (429) — stopping.")
            return []
        if resp.status_code != 200:
            self.logger.warning("[walkin_search] '%s' -> HTTP %d: %s", query,
                                resp.status_code, resp.text[:120])
            return []
        return resp.json().get("items", []) or []

    # ── Result -> walk-in row ──────────────────────────────────────────────────
    def _to_walkin(self, item: dict, location: str, cfg: dict) -> "dict | None":
        title = (item.get("title") or "").strip()
        url = item.get("link", "")
        if not title or not url:
            return None
        text = f"{title}. {item.get('snippet', '')}".strip()
        details = extract_walkin_details(text)

        # If the snippet didn't yield a date or venue, fetch the page for more.
        if cfg.get("fetch_pages") and not (details["walkin_date"] and details["venue"]):
            page = self._fetch_page_text(url)
            if page:
                full = f"{text} {page}"
                merged = extract_walkin_details(full)
                details = {k: details[k] or merged[k] for k in details}
                text = full

        # Only keep results that actually look like a walk-in (real signal or a date).
        if not is_walkin(text) and not details["walkin_date"]:
            return None

        return {
            "title": title,
            "company": self._guess_company(title),
            "location": details["venue"] or location,
            "url": url,
            "description": text[:1000],
            "source": self.name,
            "platform": "Walk-in (Google)",
            "walkin_date": details["walkin_date"],
            "walkin_time": details["walkin_time"],
            "venue": details["venue"],
        }

    def _fetch_page_text(self, url: str) -> str:
        try:
            resp = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.extract()
            return soup.get_text(" ", strip=True)[:5000]
        except Exception:
            return ""  # best-effort; a blocked page just means thinner details

    @staticmethod
    def _guess_company(title: str) -> str:
        """Pull a company name out of a result title when it's phrased plainly.

        Matches 'at/@/by/for <Name>' and keeps only the Capitalised run, so it
        stops at the next lowercase word ('TCS' from '… at TCS for Python …').
        """
        import re
        m = re.search(r"(?:at|@|by|for)\s+([A-Z][A-Za-z0-9&.]+(?:\s+[A-Z][A-Za-z0-9&.]+){0,3})",
                      title)
        return m.group(1).strip(" -|·") if m else ""
