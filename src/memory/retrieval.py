"""Category-aware semantic retrieval from long-term memory."""

from typing import Optional

from memory.long_term import Memory, get_memories_by_category, get_all_memories
from memory.embeddings import encode, cosine_similarity, jepa_inspired_refine
from config import CATEGORIES, TOP_K_MEMORIES


# Keyword hints for category inference
CATEGORY_KEYWORDS = {
    "food": ["food", "eat", "meal", "restaurant", "cook", "recipe", "allergic", "like", "love", "hate", "vegan", "vegetarian", "diet"],
    "travel": ["travel", "trip", "flight", "hotel", "visit", "going to", "vacation", "city", "country", "destination"],
    "personal": ["name", "work", "job", "family", "pet", "dog", "cat", "home", "live", "from", "birthday", "age"],
}


def infer_category(query: str) -> Optional[str]:
    """Guess likely category from query keywords."""
    q = query.lower()
    best = None
    best_score = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > best_score:
            best_score = score
            best = cat
    return best


def retrieve(
    query: str,
    top_k: int = TOP_K_MEMORIES,
    category: Optional[str] = None,
    use_jepa_refine: bool = True,
    db_path=None,
) -> list[Memory]:
    """
    Category-aware retrieval:
    1. Infer category from query if not given
    2. Search in that category first
    3. Fallback to global search if few results
    """
    if category is None:
        category = infer_category(query)

    # Fetch candidates
    if category and category in CATEGORIES:
        candidates = get_memories_by_category(category, db_path)
    else:
        candidates = []

    # Fallback to all if category search returns little
    if len(candidates) < top_k:
        all_memories = get_all_memories(db_path)
        if len(all_memories) > len(candidates):
            seen_ids = {m.id for m in candidates}
            for m in all_memories:
                if m.id not in seen_ids:
                    candidates.append(m)
                    seen_ids.add(m.id)

    if not candidates:
        return []

    # Filter to memories with embeddings
    with_emb = [m for m in candidates if m.embedding is not None]
    if not with_emb:
        return candidates[:top_k]

    # Encode query
    query_emb = encode(query)

    # Optional: JEPA-inspired refinement
    if use_jepa_refine and len(with_emb) > 0:
        memory_embs = [m.embedding for m in with_emb]
        query_emb = jepa_inspired_refine(query_emb, memory_embs)

    # Compute similarities and rank
    scored = [
        (m, cosine_similarity(query_emb, m.embedding))
        for m in with_emb
    ]
    scored.sort(key=lambda x: -x[1])

    return [m for m, _ in scored[:top_k]]
