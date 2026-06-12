"""Remotive public job API. https://remotive.com/api/remote-jobs (documented & open)."""
import html
import re

import requests

from sources.base_source import BaseSource

_API = "https://remotive.com/api/remote-jobs"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", s or "")).strip()


class RemotiveSource(BaseSource):
    name = "remotive"

    def fetch_jobs(self, keyword: str) -> list[dict]:
        resp = requests.get(_API, params={"search": keyword, "limit": 20}, timeout=20)
        resp.raise_for_status()
        out = []
        for j in resp.json().get("jobs", []):
            out.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "Remote"),
                "url": j.get("url", ""),
                "description": _strip_html(j.get("description", "")),
                "source": self.name,
            })
        self.logger.info("[remotive] '%s' -> %d jobs", keyword, len(out))
        return out
