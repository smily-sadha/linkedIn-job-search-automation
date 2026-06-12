"""Generic RSS source — point it at any career-page / aggregator RSS feed.

Configure feeds in config.SOURCES["rss"]["feeds"]. RSS is published explicitly
for machine consumption, so this is fully ToS-friendly.
"""
import html
import re

import feedparser

from config.config import SOURCES
from sources.base_source import BaseSource

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", s or "")).strip()


class RSSSource(BaseSource):
    name = "rss"

    def fetch_jobs(self, keyword: str) -> list[dict]:
        feeds = SOURCES.get("rss", {}).get("feeds", [])
        kw = keyword.lower()
        out = []
        for feed_url in feeds:
            try:
                parsed = feedparser.parse(feed_url)
            except Exception as exc:
                self.logger.error("[rss] failed to parse %s: %s", feed_url, exc)
                continue
            for e in parsed.entries:
                title = e.get("title", "")
                summary = _strip_html(e.get("summary", ""))
                if kw not in f"{title} {summary}".lower():
                    continue
                out.append({
                    "title": title,
                    "company": e.get("author", "") or parsed.feed.get("title", "RSS"),
                    "location": "",
                    "url": e.get("link", ""),
                    "description": summary,
                    "source": self.name,
                })
        self.logger.info("[rss] '%s' -> %d jobs across %d feeds", keyword, len(out), len(feeds))
        return out
