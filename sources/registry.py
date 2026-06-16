"""Maps source keys -> source classes, honouring the enabled flags in config."""
from config.config import SOURCES
from sources.gmail_source import GmailSource
from sources.indeed_source import IndeedSource
from sources.linkedin_source import LinkedInSource
from sources.naukri_source import NaukriSource
from sources.remoteok_source import RemoteOKSource
from sources.remotive_source import RemotiveSource
from sources.rss_source import RSSSource
from sources.walkin_search_source import WalkinSearchSource

_CLASSES = {
    "remotive": RemotiveSource,
    "remoteok": RemoteOKSource,
    "rss": RSSSource,
    "gmail": GmailSource,
    "linkedin": LinkedInSource,
    "naukri": NaukriSource,
    "indeed": IndeedSource,
    "walkin_search": WalkinSearchSource,
}


def get_sources(only: str = "all", mailer=None) -> list:
    """Instantiate enabled sources. `only` selects a single source key or 'all'."""
    keys = _CLASSES.keys() if only == "all" else [only]
    sources = []
    for key in keys:
        if key not in _CLASSES:
            continue
        if not SOURCES.get(key, {}).get("enabled", False):
            continue
        sources.append(_CLASSES[key](mailer=mailer))
    return sources


def available_keys() -> list[str]:
    return list(_CLASSES.keys())
