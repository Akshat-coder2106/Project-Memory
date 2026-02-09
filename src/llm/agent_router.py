"""Agent Router (OpenAI-compatible) API client with graceful fallback."""

import os
import sys
from pathlib import Path
from typing import Optional

# Project root for .env loading
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Defaults
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_BASE_URL = "https://agentrouter.org/api/v1"

# Quota saver: use only 1 LLM call per message (reply only). Set True on errors or when AGENT_ROUTER_SAVE_QUOTA=1
_quota_saving_mode = False


def _load_env():
    """Load .env from project root so it works regardless of cwd."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_PROJECT_ROOT / ".env")
        load_dotenv()  # Also try cwd
    except ImportError:
        pass


def _log_error(msg: str, e: Optional[Exception] = None):
    print(f"[Agent Router] {msg}", file=sys.stderr)
    if e is not None:
        print(f"[Agent Router] Error: {e}", file=sys.stderr)


def _api_key() -> Optional[str]:
    _load_env()
    key = (os.environ.get("AGENT_ROUTER_API_KEY") or "").strip()
    return key or None


def _current_model() -> str:
    return (os.environ.get("AGENT_ROUTER_MODEL") or _DEFAULT_MODEL).strip()


def _client():
    key = _api_key()
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key, base_url=_DEFAULT_BASE_URL)
    except Exception as e:
        _log_error("Could not create OpenAI-compatible client.", e)
        return None


def is_available() -> bool:
    """Check if Agent Router API is configured."""
    return _client() is not None


def is_quota_saving() -> bool:
    """True = use only 1 LLM call per message. Saves quota."""
    if _quota_saving_mode:
        return True
    v = (os.environ.get("AGENT_ROUTER_SAVE_QUOTA") or "0").strip().lower()
    return v in ("1", "true", "yes")


def generate(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    """Generate response via Agent Router. Returns None on failure."""
    client = _client()
    if not client:
        return None
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model=_current_model(),
            messages=messages,
            temperature=0.7,
        )
        if response and response.choices:
            content = response.choices[0].message.content
            return content.strip() if content else None
    except Exception as e:
        global _quota_saving_mode
        _quota_saving_mode = True
        _log_error("Generate failed.", e)
    return None


def extract_facts(text: str) -> Optional[list[dict]]:
    """Use Agent Router to extract facts - returns None on failure, caller should fallback."""
    import json
    import re
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
            raw = re.sub(r"^```(?:json)?\\s*", "", raw)
            raw = re.sub(r"\\s*```$", "", raw)
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return None


def summarize_memories(memory_texts: list[str]) -> Optional[str]:
    """Compress a list of memory strings into a concise summary. Returns None on failure."""
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


class AgentRouterClient:
    """Thin wrapper for use in extractor (pass to extract_with_agent_router)."""

    def generate_content(self, prompt: str):
        class Response:
            def __init__(self, text):
                self.text = text
        out = generate(prompt)
        return Response(out) if out else None
