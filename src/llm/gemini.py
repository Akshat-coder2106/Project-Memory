"""Gemini API client with graceful fallback when unavailable."""

import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# Retry on 429: max attempts and cap wait time (seconds)
# Free tier is ~20 req/min; allow several waits so "retry in 59s" is honored
_MAX_429_RETRIES = 3
_MAX_429_WAIT = 90

# Client-side rate limit: stay under Gemini free tier (20 req/min)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX_CALLS = 15  # leave buffer under 20
_gemini_call_times: list[float] = []

# Models to try in order when one returns 429 (valid v1beta model IDs only)
_DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

# Lazy init: "new" = google.genai Client, "old" = GenerativeModel, False = failed
_client = None
_use_new_sdk = None
# Multi-key: GEMINI_API_KEY can be "key1,key2,key3". When one hits 429 we try the next.
_api_keys: list[str] = []
_client_key_index: Optional[int] = None  # which key the current _client uses
_exhausted_key_indices: set[int] = set()  # keys that returned 429 this session

# Session cache: prefer last working model, skip models that returned "limit: 0"
_last_working_model: Optional[str] = None
_models_with_no_quota: set[str] = set()

# Quota saver: use only 1 Gemini call per message (reply only). Set True on 429 or when GEMINI_SAVE_QUOTA=1
_quota_saving_mode = False

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


def _log_error(msg: str, e: Optional[Exception] = None):
    """Print error so user can see why Gemini failed."""
    print(f"[Gemini] {msg}", file=sys.stderr)
    if e is not None:
        print(f"[Gemini] Error: {e}", file=sys.stderr)


def _is_429(e: Exception) -> bool:
    """Check if exception is a 429 rate-limit / quota error."""
    s = str(e).lower()
    return "429" in s or "resource_exhausted" in s or "quota" in s


def _is_limit_zero(e: Exception) -> bool:
    """Check if error says quota limit is 0 (often = region not eligible for free tier)."""
    return "limit: 0" in str(e)


def _current_model() -> str:
    """Model name from env or default."""
    return (os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()


def _retry_after_seconds(e: Exception) -> float:
    """Parse 'Please retry in X.XXs' from error message. Returns 0 if not found."""
    m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", str(e), re.I)
    if m:
        return min(float(m.group(1)), _MAX_429_WAIT)
    return 45.0  # default wait


def _wait_for_quota():
    """Block until we're under the per-minute quota so we don't hit 429."""
    global _gemini_call_times
    now = time.monotonic()
    # drop timestamps outside the window
    while _gemini_call_times and _gemini_call_times[0] < now - _RATE_LIMIT_WINDOW:
        _gemini_call_times.pop(0)
    if len(_gemini_call_times) >= _RATE_LIMIT_MAX_CALLS:
        wait = _RATE_LIMIT_WINDOW - (now - _gemini_call_times[0])
        if wait > 0.5:
            print(f"[Gemini] Throttling: waiting {wait:.0f}s to stay under quota...", file=sys.stderr)
            time.sleep(wait)
        now = time.monotonic()
        while _gemini_call_times and _gemini_call_times[0] < now - _RATE_LIMIT_WINDOW:
            _gemini_call_times.pop(0)


def _record_gemini_call():
    """Record that we're making a Gemini API call (for rate limiting)."""
    _gemini_call_times.append(time.monotonic())


def is_available() -> bool:
    """Check if Gemini API is configured and working."""
    return _get_client() is not None


def is_quota_saving() -> bool:
    """True = use only 1 Gemini call per message (reply only). Saves quota (free tier is 20/day)."""
    if _quota_saving_mode:
        return True
    v = (os.environ.get("GEMINI_SAVE_QUOTA") or "1").strip().lower()
    return v in ("1", "true", "yes")


def _parse_api_keys() -> list[str]:
    """Parse GEMINI_API_KEY (or GOOGLE_API_KEY) — supports comma-separated keys for quota rotation."""
    global _api_keys
    if _api_keys:
        return _api_keys
    _load_env()
    raw = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not raw:
        return []
    _api_keys = [k.strip() for k in raw.split(",") if k.strip()]
    return _api_keys


def _create_client_for_key(api_key: str):
    """Create a Gemini client for the given API key. Returns (client, use_new_sdk) or (False, False)."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        return client, True
    except ImportError:
        pass
    except Exception as e:
        _log_error("New SDK (google.genai) failed, will try old SDK.", e)
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(_current_model()), False
    except Exception as e:
        _log_error("Could not create Gemini client.", e)
        return False, False


def _get_client():
    """Lazy-load Gemini client. Uses first non-exhausted key; supports multiple keys (key1,key2) in .env."""
    global _client, _use_new_sdk, _client_key_index, _exhausted_key_indices
    if _client is not None:
        return _client
    keys = _parse_api_keys()
    if not keys:
        return None
    for i, api_key in enumerate(keys):
        if i in _exhausted_key_indices:
            continue
        _client, _use_new_sdk = _create_client_for_key(api_key)
        if _client is not False:
            _client_key_index = i
            return _client
    return None


def _switch_to_next_key() -> bool:
    """Mark current key as exhausted and clear client so next _get_client() uses next key. Returns True if more keys exist."""
    global _client, _client_key_index, _exhausted_key_indices
    if _client_key_index is not None:
        _exhausted_key_indices.add(_client_key_index)
    _client = None
    _client_key_index = None
    keys = _parse_api_keys()
    remaining = [i for i in range(len(keys)) if i not in _exhausted_key_indices]
    return len(remaining) > 0


def _response_to_text_new(response) -> Optional[str]:
    """Extract text from new SDK response."""
    if response is None:
        return None
    if hasattr(response, "text") and response.text:
        return response.text.strip()
    if hasattr(response, "candidates") and response.candidates:
        c = response.candidates[0]
        if hasattr(c, "content") and c.content and hasattr(c.content, "parts") and c.content.parts:
            part = c.content.parts[0]
            if hasattr(part, "text") and part.text:
                return part.text.strip()
    return None


def _generate_once(client, full: str, model: Optional[str] = None) -> Optional[str]:
    """Single attempt to generate. Raises on API errors."""
    if _use_new_sdk:
        from google.genai import types
        m = model or _current_model()
        response = client.models.generate_content(
            model=m,
            contents=full,
            config=types.GenerateContentConfig(temperature=0.7),
        )
        return _response_to_text_new(response)
    response = client.generate_content(full)
    if response and getattr(response, "text", None):
        return response.text.strip()
    return None


def _models_to_try() -> list[str]:
    """List of model names to try. Prefer last working model; skip models with no quota."""
    global _last_working_model, _models_with_no_quota
    current = _current_model()
    candidates = [current]
    for m in _DEFAULT_MODELS:
        if m != current:
            candidates.append(m)
    # Put last working model first so we don't hit 2.0 (no quota) every message
    if _last_working_model and _last_working_model in candidates:
        candidates = [_last_working_model] + [c for c in candidates if c != _last_working_model]
    # Skip models we already know have no quota (avoids repeated "No quota" logs)
    return [m for m in candidates if m not in _models_with_no_quota]


def generate(
    prompt: str,
    system_instruction: Optional[str] = None,
) -> Optional[str]:
    """
    Generate response from Gemini. Returns None on failure.
    Retries on 429 (quota/rate limit) with backoff; tries alternate models when limit is 0.
    Remembers which model worked so the next message skips models with no quota.
    """
    global _last_working_model, _models_with_no_quota
    client = _get_client()
    if not client:
        return None
    full = system_instruction + "\n\n" + prompt if system_instruction else prompt
    last_error = None
    models = _models_to_try() if _use_new_sdk else [_current_model()]
    for model in models:
        for attempt in range(_MAX_429_RETRIES + 1):
            _wait_for_quota()
            _record_gemini_call()
            try:
                out = _generate_once(client, full, model=model if _use_new_sdk else None)
                if out is not None:
                    _last_working_model = model if _use_new_sdk else _current_model()
                    return out
            except Exception as e:
                last_error = e
                if not _is_429(e):
                    break
                if _is_limit_zero(e) and _use_new_sdk and attempt == 0:
                    if model not in _models_with_no_quota:
                        _models_with_no_quota.add(model)
                        print(f"[Gemini] No quota for {model}; using next model for this session.", file=sys.stderr)
                    break
                if attempt < _MAX_429_RETRIES:
                    wait = _retry_after_seconds(e)
                    print(f"[Gemini] Rate limit — waiting {wait:.0f}s...", file=sys.stderr)
                    time.sleep(wait)
                else:
                    break
        if last_error and not (_is_429(last_error) and _is_limit_zero(last_error)):
            break
    # On 429, try next API key if multiple keys are configured (e.g. GEMINI_API_KEY=key1,key2)
    if last_error and _is_429(last_error) and _switch_to_next_key():
        print("[Gemini] Quota exceeded on this key — trying next key from .env...", file=sys.stderr)
        client = _get_client()
        if client:
            _wait_for_quota()
            _record_gemini_call()
            try:
                model = (_last_working_model or _current_model()) if _use_new_sdk else None
                out = _generate_once(client, full, model=model)
                if out is not None:
                    return out
            except Exception:
                pass
    _log_error("Generate failed.", last_error)
    if last_error and _is_429(last_error):
        global _quota_saving_mode
        _quota_saving_mode = True
        if _is_limit_zero(last_error):
            print(
                "[Gemini] Quota shows 'limit: 0' — free tier may not be available in your region.\n"
                "  • Check usage: https://aistudio.google.com/usage\n"
                "  • Try another model: add GEMINI_MODEL=gemini-2.5-flash or GEMINI_MODEL=gemini-2.5-flash-lite to .env and restart.",
                file=sys.stderr,
            )
        else:
            print(
                "[Gemini] Quota exceeded. Add another key in .env: GEMINI_API_KEY=key1,key2 (each key gets 20/day)",
                file=sys.stderr,
            )
            print("  Or get a new key: https://aistudio.google.com/apikey", file=sys.stderr)
        print("[Gemini] Using quota-saver mode for rest of session (1 call per message).", file=sys.stderr)
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
        pass
    return None


class GeminiClient:
    """Thin wrapper for use in extractor (pass to extract_with_gemini)."""

    def generate_content(self, prompt: str):
        class Response:
            def __init__(self, text):
                self.text = text
        out = generate(prompt)
        return Response(out) if out else None
