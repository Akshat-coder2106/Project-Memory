"""
OpenRouter (OpenAI-compatible) API client with graceful fallback.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict

from openai import OpenAI

# ================================
# Project root for .env loading
# ================================
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ================================
# Defaults
# ================================
_DEFAULT_MODEL = "gpt-4o-mini"

# Quota saver: use only 1 LLM call per message
_quota_saving_mode = False


# ================================
# Helpers
# ================================
def _load_env():
    """Load .env from project root so it works regardless of cwd."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_PROJECT_ROOT / ".env")
        load_dotenv()
    except Exception:
        pass


def _log_error(msg: str, e: Optional[Exception] = None):
    print(f"[OpenRouter] {msg}", file=sys.stderr)
    if e is not None:
        print(f"[OpenRouter] Error: {e}", file=sys.stderr)


def _current_model() -> str:
    return (os.environ.get("OPENROUTER_MODEL") or _DEFAULT_MODEL).strip()


def _client():
    _load_env()
    try:
        client = OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
        )
        return client
    except Exception as e:
        _log_error("Could not create OpenAI-compatible client.", e)
        return None


# ================================
# Public API
# ================================
def is_available() -> bool:
    """Check if OpenRouter API is configured."""
    return _client() is not None


def is_quota_saving() -> bool:
    """True = use only 1 LLM call per message."""
    if _quota_saving_mode:
        return True
    v = (os.environ.get("OPENROUTER_SAVE_QUOTA") or "0").strip().lower()
    return v in ("1", "true", "yes")


def generate(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    """
    Generate a response via OpenRouter.
    Returns None on failure.
    """
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


def extract_facts(text: str) -> Optional[List[Dict]]:
    """
    Extract structured user facts.
    Returns None on failure so caller can fallback.
    """
    import json
    import re

    try:
        from config import CATEGORIES

        prompt = f"""
From this user message, extract important factual information about the user.

Output ONLY a JSON array of objects.
Each object must have:
- "content"
- "category" (one of {json.dumps(CATEGORIES)})

If nothing factual, return [].

User message:
{text}
"""

        result = generate(prompt)
        if not result:
            return None

        raw = result.strip()

        # Remove code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\\s*", "", raw)
            raw = re.sub(r"\\s*```$", "", raw)

        data = json.loads(raw)
        if isinstance(data, list):
            return data

    except Exception:
        pass

    return None


def summarize_memories(memory_texts: List[str]) -> Optional[str]:
    """
    Compress a list of memory strings into a concise summary.
    """
    if not memory_texts:
        return None

    try:
        combined = "\n".join(f"- {t}" for t in memory_texts)

        prompt = f"""
Summarize these user facts into 3–5 concise factual statements.
Preserve key details (names, preferences, places).

Output ONLY the summary.

Facts:
{combined}
"""
        return generate(prompt)

    except Exception:
        pass

    return None


# ================================
# Wrapper class (for compatibility)
# ================================
class OpenRouterClient:
    """
    Thin wrapper for compatibility with extractor code.
    """

    def generate_content(self, prompt: str):
        class Response:
            def __init__(self, text: Optional[str]):
                self.text = text

        out = generate(prompt)
        return Response(out) if out else None
