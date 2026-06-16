"""
Scraping-API proxy helper — fetch a URL through a service that defeats hard
anti-bot (Akamai/Cloudflare) and uses residential IPs.

Used by sources that can't be fetched directly (e.g. Naukri behind Akamai Bot
Manager). Provider-agnostic: the default ScraperAPI request shape
(`?api_key=&url=&render=&country_code=`) also matches ZenRows/ScrapingBee when
you point SCRAPER_API_URL at them. Off unless SCRAPER_API_KEY is set.
"""
import requests

from config.config import SCRAPER_PROXY
from utils.logger import get_logger

logger = get_logger("scrape_proxy")


def is_enabled() -> bool:
    """True when a scraping-API key is configured."""
    return bool(SCRAPER_PROXY.get("api_key"))


def get(url: str, render: bool | None = None, timeout: int = 75):
    """Fetch `url` through the proxy. Returns the requests.Response, or None on
    error / when no key is set. `render` runs JS (defaults to the config value);
    rendered fetches are slower, hence the generous timeout."""
    key = SCRAPER_PROXY.get("api_key")
    if not key:
        return None
    use_render = SCRAPER_PROXY.get("render", True) if render is None else render
    params = {"api_key": key, "url": url}
    if use_render:
        params["render"] = "true"
    if SCRAPER_PROXY.get("country"):
        params["country_code"] = SCRAPER_PROXY["country"]
    try:
        return requests.get(SCRAPER_PROXY["api_url"], params=params, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("[scrape_proxy] fetch failed for %s: %s", url, exc)
        return None
