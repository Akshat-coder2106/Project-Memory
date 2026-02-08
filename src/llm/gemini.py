"""Gemini API client with graceful fallback when unavailable."""

import os
from pathlib import Path
from typing import Optional

# Lazy init
_client = None

# Project root for .env loading
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_env():
    """Load .env from project root so it works regardless of cwd."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_PROJECT_ROOT / ".env")
        load_dotenv()  # Also try cwd
    except ImportError:
        pass


def is_available() -> bool:
    """Check if Gemini API is configured and working."""
    return _get_client() is not None


def _get_client():
    """Lazy-load Gemini client."""
    global _client
    if _client is None:
        _load_env()
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key.strip())
            _client = genai.GenerativeModel("gemini-1.5-flash")
        except Exception:
            _client = False
    return _client if _client else None


def generate(
    prompt: str,
    system_instruction: Optional[str] = None,
) -> Optional[str]:
    """
    Generate response from Gemini. Returns None on failure.
    """
    client = _get_client()
    if not client:
        return None
    try:
        full = system_instruction + "\n\n" + prompt if system_instruction else prompt
        response = client.generate_content(full)
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass
    return None


def extract_facts(text: str) -> Optional[list[dict]]:
    """Use Gemini to extract facts - returns None on failure, caller should fallback."""
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
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
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
        return None


class GeminiClient:
    """Thin wrapper for use in extractor (pass to extract_with_gemini)."""

    def generate_content(self, prompt: str):
        class Response:
            def __init__(self, text):
                self.text = text
        out = generate(prompt)
        return Response(out) if out else None
