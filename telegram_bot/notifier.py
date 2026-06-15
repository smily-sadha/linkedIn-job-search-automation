"""Lightweight, synchronous Telegram push helpers (used by main.py).

Uses the plain HTTP API via requests so it works without an event loop.
Silently no-ops if Telegram isn't configured.
"""
import requests

from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import get_logger

logger = get_logger("notifier")


def _send_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured; message not sent.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
        r.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


def send_run_summary(summary: dict) -> bool:
    from datetime import datetime
    mins, secs = divmod(int(summary.get("duration_seconds", 0)), 60)
    text = (
        f"Run Complete - {datetime.now():%d %b %Y %H:%M}\n"
        f"Jobs found:    {summary.get('found', 0)}\n"
        f"Walk-ins:      {summary.get('walkins', 0)}\n"
        f"Cold mails:    {summary.get('cold_mails', 0)}\n"
        f"Manual queue:  {summary.get('queued_manual', 0)}\n"
        f"Skipped:       {summary.get('skipped', 0)}\n"
        f"Errors:        {summary.get('errors', 0)}\n"
        f"Duration:      {mins}m {secs}s"
    )
    return _send_message(text)


def send_alert(text: str) -> bool:
    return _send_message(f"ALERT\n{text}")


def send_job_alerts(alerts: list, top: int = 8) -> bool:
    """Push a digest of fresh high-match jobs found this run (with apply links)."""
    if not alerts:
        return False
    ranked = sorted(alerts, key=lambda a: a.get("score", 0), reverse=True)
    lines = [f"🔥 {len(alerts)} fresh high-match job(s) — apply early!"]
    for a in ranked[:top]:
        lines.append(
            f"\n• {a.get('title', 'Role')} @ {a.get('company', '?')} "
            f"(match {a.get('score', 0)}/10)\n{a.get('url', '')}"
        )
    if len(ranked) > top:
        lines.append(f"\n…and {len(ranked) - top} more in the dashboard.")
    return _send_message("\n".join(lines))


def send_report(text: str) -> bool:
    return _send_message(text)
