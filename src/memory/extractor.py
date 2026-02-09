"""Memory extractor - extracts factual info from user messages (local + Agent Router fallback)."""

import re
import json
from typing import Optional

from config import CATEGORIES


# Keyword patterns for local extraction (regex-based)
LOCAL_PATTERNS = [
    # Food
    (r"(?:i (?:like|love|enjoy|prefer|don't like|hate)) (.+?)(?:\.|$|!)", "food"),
    (r"(?:i'm )?(?:allergic to|allergic to) (.+?)(?:\.|$|,|!)", "personal"),
    (r"(?:my favorite (?:food|cuisine|dish) (?:is )?)(.+?)(?:\.|$|!)", "food"),
    (r"(?:i (?:am |'m )?)(vegan|vegetarian|pescatarian)", "food"),
    # Travel
    (r"(?:i(?:'m| am) (?:going to|traveling to|visiting)) (.+?)(?:\.|$|,|!)", "travel"),
    (r"(?:i (?:live in|live at|am from)) (.+?)(?:\.|$|,|!)", "personal"),
    (r"(?:my (?:hometown|city) (?:is )?)(.+?)(?:\.|$|!)", "personal"),
    (r"(?:i (?:visited|went to|traveled to)) (.+?)(?:\.|$|,|!)", "travel"),
    # Personal
    (r"(?:i (?:work as|am a|am an)) (.+?)(?:\.|$|,|!)", "personal"),
    (r"(?:my name is) (.+?)(?:\.|$|,|!)", "personal"),
    (r"(?:i have a (?:dog|cat|pet)) (.+?)(?:\.|$|,|!)", "personal"),
    (r"(?:i (?:like|love|enjoy) (?:to )?)(.+?)(?:\.|$|!|\?)", "misc"),
]


def extract_local(text: str) -> list[dict]:
    """
    Extract facts using simple regex rules. Returns list of {content, category}.
    """
    text_lower = text.lower().strip()
    extracted = []

    for pattern, category in LOCAL_PATTERNS:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        for m in matches:
            content = m.group(1).strip()
            if len(content) > 2 and content not in [e["content"] for e in extracted]:
                extracted.append({"content": content, "category": category})

    # Fallback: if nothing matched but message seems factual, store as misc
    if not extracted and _looks_factual(text_lower):
        # Take first sentence or whole message if short
        parts = re.split(r"[.!?]", text)
        first = (parts[0] if parts else text).strip()
        if 5 < len(first) < 200:
            extracted.append({"content": first, "category": "misc"})

    return extracted


def _looks_factual(text: str) -> bool:
    """Heuristic: does this look like a factual statement vs question/greeting?"""
    factual_starts = ("i ", "my ", "i'm ", "i am ", "we ", "we're ")
    question_starts = ("what", "how", "why", "when", "where", "who", "which", "?")
    text = text.strip().lower()
    if any(text.startswith(q) for q in question_starts):
        return False
    if any(text.startswith(f) for f in factual_starts):
        return True
    return " is " in text or " are " in text or " have " in text


def extract_with_agent_router(text: str) -> list[dict]:
    """
    Use Agent Router to extract facts. Returns list of {content, category}.
    Falls back to local extraction on failure.
    """
    try:
        from llm.agent_router import generate
        prompt = f"""From this user message, extract important factual information about the user.
Output ONLY a JSON array of objects, each with "content" and "category".
Categories must be one of: {json.dumps(CATEGORIES)}.
If nothing factual, return [].
Example: [{{"content": "likes Thai food", "category": "food"}}, {{"content": "allergic to peanuts", "category": "personal"}}]

User message: {text}"""

        response_text = generate(prompt)
        if not response_text:
            return extract_local(text)

        raw = response_text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if not isinstance(data, list):
            return extract_local(text)
        result = []
        for item in data:
            if isinstance(item, dict) and "content" in item:
                cat = item.get("category", "misc")
                if cat not in CATEGORIES:
                    cat = "misc"
                result.append({"content": str(item["content"]), "category": cat})
        return result if result else extract_local(text)
    except Exception:
        return extract_local(text)
