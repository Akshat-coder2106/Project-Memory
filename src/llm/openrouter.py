"""OpenRouter API client for text generation and utility LLM tasks."""

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _load_env() -> None:
    """Load .env from project root and cwd (best effort)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(_PROJECT_ROOT / ".env")
        load_dotenv()
    except ImportError:
        pass


def _log_error(msg: str, e: Optional[Exception] = None) -> None:
    print(f"[OpenRouter] {msg}", file=sys.stderr)
    if e is not None:
        print(f"[OpenRouter] Error: {e}", file=sys.stderr)


def _openrouter_key() -> str:
    """Read OpenRouter API key from env."""
    return (os.environ.get("OPENROUTER_API_KEY") or "").strip()


def _openrouter_model() -> str:
    return (os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip()


def _temperature() -> float:
    raw = (os.environ.get("OPENROUTER_TEMPERATURE") or "").strip()
    if not raw:
        return 0.7
    try:
        value = float(raw)
    except ValueError:
        return 0.7
    return min(max(value, 0.0), 2.0)


def _max_tokens() -> Optional[int]:
    raw = (os.environ.get("OPENROUTER_MAX_TOKENS") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _ssl_context() -> Optional[ssl.SSLContext]:
    """Build SSL context for OpenRouter requests."""
    verify_ssl = _bool_env("OPENROUTER_VERIFY_SSL", True)
    if not verify_ssl:
        return ssl._create_unverified_context()

    cafile = (
        (os.environ.get("OPENROUTER_CA_BUNDLE") or "").strip()
        or (os.environ.get("SSL_CERT_FILE") or "").strip()
    )
    if cafile:
        return ssl.create_default_context(cafile=cafile)

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def is_available() -> bool:
    """True if OpenRouter key is configured."""
    _load_env()
    return bool(_openrouter_key())


def is_quota_saving() -> bool:
    """
    Optional low-call mode.
    Defaults to off.
    """
    v = (
        os.environ.get("AI_SAVE_QUOTA")
        or os.environ.get("OPENROUTER_SAVE_QUOTA")
        or "0"
    ).strip().lower()
    return v in ("1", "true", "yes")


def _parse_content(content) -> Optional[str]:
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
    return None


def generate(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    """Generate a response using OpenRouter (OpenAI-compatible API)."""
    _load_env()
    key = _openrouter_key()
    if not key:
        return None

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": _openrouter_model(),
        "messages": messages,
        "temperature": _temperature(),
    }
    max_tokens = _max_tokens()
    if max_tokens:
        payload["max_tokens"] = max_tokens

    req = urllib.request.Request(
        _OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "http://localhost:5000"),
            "X-Title": os.environ.get("OPENROUTER_APP_NAME", "Project-Memory"),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as res:
            raw = json.loads(res.read().decode("utf-8"))
            choices = raw.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            return _parse_content(message.get("content"))
    except ssl.SSLError as e:
        _log_error(
            "TLS verification failed. Install/refresh CA certs or set OPENROUTER_CA_BUNDLE."
            " As a temporary local workaround only, set OPENROUTER_VERIFY_SSL=0.",
            e,
        )
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        _log_error(f"HTTP {e.code}", Exception(body))
    except Exception as e:
        _log_error("Request failed.", e)
    return None


def extract_facts(text: str) -> Optional[list[dict]]:
    """Use OpenRouter to extract facts; returns None on failure so caller can fallback locally."""
    try:
        from config import CATEGORIES

        prompt = f"""From this user message, extract important factual information about the user.
Output ONLY a JSON array of objects, each with "content" and "category".
Categories must be one of: {json.dumps(CATEGORIES)}.
If nothing factual, return [].

User message: {text}"""
        result = generate(prompt)
        if not result:
            return None
        raw = result.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return None


def summarize_memories(memory_texts: list[str]) -> Optional[str]:
    """Summarize memories into concise facts."""
    if not memory_texts:
        return None
    try:
        combined = "\n".join(f"- {t}" for t in memory_texts)
        prompt = f"""Summarize these user facts into 3-5 concise factual statements. Preserve key details (names, preferences, allergies, places). Output only the summary, no preamble.

Facts:
{combined}"""
        return generate(prompt)
    except Exception:
        pass
    return None


class OpenRouterClient:
    """Simple wrapper exposing generate_content(prompt)."""

    def generate_content(self, prompt: str):
        class Response:
            def __init__(self, text):
                self.text = text

        out = generate(prompt)
        return Response(out) if out else None
