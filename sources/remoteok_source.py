"""RemoteOK public job API. https://remoteok.com/api (documented & open)."""
import html
import re

import requests

from sources.base_source import BaseSource

_API = "https://remoteok.com/api"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", s or "")).strip()


class RemoteOKSource(BaseSource):
    name = "remoteok"

    def fetch_jobs(self, keyword: str) -> list[dict]:
        # RemoteOK asks for a descriptive User-Agent.
        resp = requests.get(_API, headers={"User-Agent": "job-hunt-assistant/1.0"}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        kw = keyword.lower()
        out = []
        for j in data:
            if not isinstance(j, dict) or "position" not in j:
                continue  # first element is a legal/metadata notice
            haystack = f"{j.get('position', '')} {j.get('description', '')} {' '.join(j.get('tags', []))}".lower()
            if kw not in haystack:
                continue
            out.append({
                "title": j.get("position", ""),
                "company": j.get("company", ""),
                "location": j.get("location") or "Remote",
                "url": j.get("url", ""),
                "description": _strip_html(j.get("description", "")),
                "source": self.name,
                "posted_at": j.get("date") or "",          # full ISO8601 (for 24h filter)
                "posted": (j.get("date") or "")[:10],        # YYYY-MM-DD (for display)
            })
        self.logger.info("[remoteok] '%s' -> %d jobs", keyword, len(out))
        return out
