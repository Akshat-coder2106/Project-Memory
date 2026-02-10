"""Best-effort live web search for current-data questions."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Optional

_LIVE_QUERY_RE = re.compile(
    r"\b("
    r"latest|current|today|right now|breaking|recent|news|update|"
    r"score|price|weather|forecast|who won|stock|crypto|election|"
    r"internet|online|web|live"
    r")\b",
    re.IGNORECASE,
)


def _env_truthy(name: str, default: str = "1") -> bool:
    raw = (os.environ.get(name) or default).strip().lower()
    return raw in ("1", "true", "yes", "on")


def should_search_web(query: str) -> bool:
    """Decide whether a query likely needs fresh online data."""
    if not _env_truthy("ENABLE_WEB_SEARCH", "1"):
        return False
    text = (query or "").strip()
    if not text:
        return False
    return bool(_LIVE_QUERY_RE.search(text))


def _search_with_ddgs(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS  # optional dependency

    results: list[dict] = []
    region = (os.environ.get("WEB_SEARCH_REGION") or "us-en").strip()
    safesearch = (os.environ.get("WEB_SEARCH_SAFESEARCH") or "moderate").strip()
    timelimit = (os.environ.get("WEB_SEARCH_TIMELIMIT") or "").strip() or None
    with DDGS() as ddgs:
        rows = ddgs.text(
            query,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            max_results=max_results,
        )
        for row in rows or []:
            title = str(row.get("title") or "").strip()
            url = str(row.get("href") or "").strip()
            snippet = str(row.get("body") or "").strip()
            if not (title or url or snippet):
                continue
            results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break
    return results


def _search_with_instant_answer(query: str, max_results: int) -> list[dict]:
    """Fallback that does not require extra packages."""
    url = (
        "https://api.duckduckgo.com/?"
        + urllib.parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }
        )
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Project-Memory/1.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        raw = json.loads(res.read().decode("utf-8"))

    out: list[dict] = []
    abstract = str(raw.get("AbstractText") or "").strip()
    abstract_url = str(raw.get("AbstractURL") or "").strip()
    heading = str(raw.get("Heading") or "").strip() or "Instant answer"
    if abstract:
        out.append({"title": heading, "url": abstract_url, "snippet": abstract})

    for topic in raw.get("RelatedTopics") or []:
        if "Topics" in topic:
            nested = topic.get("Topics") or []
        else:
            nested = [topic]
        for item in nested:
            text = str(item.get("Text") or "").strip()
            link = str(item.get("FirstURL") or "").strip()
            if text:
                out.append({"title": "Related", "url": link, "snippet": text})
                if len(out) >= max_results:
                    return out[:max_results]

    return out[:max_results]


def search_web(query: str, max_results: Optional[int] = None) -> list[dict]:
    """Return web snippets for the query; empty list on failure."""
    if not should_search_web(query):
        return []

    raw_max = (os.environ.get("WEB_SEARCH_MAX_RESULTS") or "").strip()
    limit = max_results if max_results is not None else int(raw_max or "5")
    limit = max(1, min(limit, 8))

    # Try full search first, fallback to instant answer API.
    try:
        return _search_with_ddgs(query, limit)
    except Exception:
        pass
    try:
        return _search_with_instant_answer(query, limit)
    except Exception:
        return []
