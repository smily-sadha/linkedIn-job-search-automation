"""Shared Groq (OpenAI-compatible) chat client for the LLM features.

Plain HTTP via `requests` — no SDK. Returns the assistant's text, or None on
any failure or missing key, so every caller can fall back gracefully.
"""
import requests

from config.config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL
from utils.logger import get_logger

logger = get_logger("groq")


def is_enabled() -> bool:
    """True if a Groq key is configured."""
    return bool(GROQ_API_KEY)


def chat(system: str, user: str, *, max_tokens: int = 300,
         json_mode: bool = False, temperature: float = 0.3) -> "str | None":
    """Single-turn chat completion. Returns assistant text or None on failure."""
    if not GROQ_API_KEY:
        return None
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        r = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload, timeout=40,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("[Groq] chat failed: %s", exc)
        return None
