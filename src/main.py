"""
Main entry point - conversational AI with hierarchical memory.

Run from project root: python -m src.main
"""

import sys
from pathlib import Path

# Load .env early so GEMINI_API_KEY is available
sys.path.insert(0, str(Path(__file__).parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from memory.short_term import ShortTermBuffer
from memory.long_term import init_db, add_memory, get_memory_count, get_all_memories, delete_memories
from memory.extractor import extract_local, extract_with_gemini
from memory.embeddings import encode, get_backend
from memory.retrieval import retrieve
from memory.compression import maybe_compress
from llm.gemini import is_available
from config import (
    MAX_SHORT_TERM_MESSAGES,
    TOP_K_MEMORIES,
    CATEGORIES,
)

def _get_fallback_message() -> str:
    """Return helpful message when Gemini is unavailable."""
    import os
    from pathlib import Path
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not key:
        return (
            "I can't connect to the AI right now. To enable AI responses:\n"
            f"  1. Create {env_path} with: GEMINI_API_KEY=your_key\n"
            "  2. Get a free key at https://aistudio.google.com/apikey\n"
            "  3. Restart the app."
        )
    return "The AI service is temporarily unavailable. I've noted your message—please try again in a moment."


CLI_HELP = """
Commands:
  /memories [category]  List stored memories (optional: personal, food, travel, misc)
  /stats                Show memory statistics
  /export [file]        Export memories to JSON (default: data/memories_export.json)
  /clear                Delete all memories (confirmation required)
  /help                 Show this help
  quit, exit, q         Exit chat
"""

SYSTEM_INSTRUCTION = """You are a helpful conversational assistant with long-term memory of the user.
Use the provided "Relevant memories" to personalize your responses. Be concise and natural.
If memories conflict with what the user just said, prioritize the most recent conversation."""


def build_context(short_term: ShortTermBuffer, memories_text: str) -> str:
    """Build the context string for the LLM."""
    parts = []
    if memories_text:
        parts.append("Relevant memories about the user:\n" + memories_text)
    parts.append("\nRecent conversation:\n" + short_term.format_for_context())
    return "\n".join(parts)


def get_response_local(user_message: str, short_term: ShortTermBuffer) -> str:
    """Response without calling Gemini: acknowledge message and show relevant memories."""
    mems = retrieve(user_message, top_k=TOP_K_MEMORIES)
    parts = ["I've noted that."]
    if mems:
        parts.append("Relevant memories: " + "; ".join(f"[{m.category}] {m.content}" for m in mems[:3]))
    return " ".join(parts)


def get_response(user_message: str, short_term: ShortTermBuffer) -> str:
    """Generate response using Gemini or fallback. (Unused when Gemini is only used for compression.)"""
    mems = retrieve(user_message, top_k=TOP_K_MEMORIES)
    memories_text = "\n".join(f"- [{m.category}] {m.content}" for m in mems) if mems else ""
    context = build_context(short_term, memories_text)
    prompt = f"{context}\n\nAssistant:"
    response = generate(prompt, system_instruction=SYSTEM_INSTRUCTION)
    if response:
        return response
    return _get_fallback_message()


def process_and_store_facts(user_message: str, use_gemini: bool = True) -> list[dict]:
    """Extract facts and store them with embeddings. Skip near-duplicates."""
    from config import DUPLICATE_SIMILARITY_THRESHOLD
    from memory.long_term import has_similar_memory

    extracted = extract_with_gemini(user_message) if use_gemini else extract_local(user_message)
    stored = []
    for item in extracted:
        content = item["content"]
        category = item["category"]
        embedding = encode(content)
        if has_similar_memory(embedding, category, DUPLICATE_SIMILARITY_THRESHOLD):
            continue
        add_memory(content=content, category=category, embedding=embedding)
        stored.append(item)
    return stored


def handle_cli_command(cmd: str) -> bool:
    """Handle /commands. Returns True if handled (no further processing)."""
    cmd = cmd.strip().lower()
    if cmd == "/help":
        print(CLI_HELP)
        return True
    if cmd == "/stats":
        count = get_memory_count()
        mems = get_all_memories()
        by_cat = {}
        for m in mems:
            by_cat[m.category] = by_cat.get(m.category, 0) + 1
        print(f"\nMemories: {count} total")
        for c in CATEGORIES:
            print(f"  {c}: {by_cat.get(c, 0)}")
        print()
        return True
    if cmd.startswith("/memories"):
        parts = cmd.split(maxsplit=1)
        cat = parts[1] if len(parts) > 1 else None
        mems = get_all_memories()
        if cat and cat in CATEGORIES:
            mems = [m for m in mems if m.category == cat]
        if not mems:
            print("\nNo memories stored.\n")
        else:
            print(f"\n{len(mems)} memories:\n")
            for m in mems:
                print(f"  [{m.category}] {m.content}")
            print()
        return True
    if cmd == "/clear":
        confirm = input("Delete all memories? (yes/no): ").strip().lower()
        if confirm == "yes":
            mems = get_all_memories()
            delete_memories([m.id for m in mems if m.id])
            print("All memories cleared.\n")
        else:
            print("Cancelled.\n")
        return True
    if cmd.startswith("/export"):
        import json
        from pathlib import Path
        parts = cmd.split(maxsplit=1)
        out_path = Path(parts[1]) if len(parts) > 1 else Path("data/memories_export.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mems = get_all_memories()
        data = [{"content": m.content, "category": m.category, "created_at": m.created_at.isoformat() if m.created_at else None} for m in mems]
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(mems)} memories to {out_path}\n")
        return True
    return False


def main():
    init_db()
    buffer = ShortTermBuffer(max_size=MAX_SHORT_TERM_MESSAGES)
    has_gemini = is_available()

    print("=== Memory-Enabled Conversational AI ===")
    print("Type /help for commands, 'quit' to exit.\n")
    print(f"(Embeddings: {get_backend()})")
    if has_gemini:
        print("(Gemini used only when memory is full — for compression. Set GEMINI_API_KEY in .env)")
    else:
        print("(Gemini not configured — compression will be skipped when memory is full. Set GEMINI_API_KEY in .env)")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if user_input.startswith("/"):
            if handle_cli_command(user_input):
                continue

        buffer.add("user", user_input)

        # Extract and store facts (local only — no Gemini per message)
        stored = process_and_store_facts(user_input, use_gemini=False)
        if stored:
            for s in stored:
                print(f"  [Stored] [{s['category']}] {s['content']}")

        # Gemini only when memory is filled: compress old memories (uses GEMINI_API_KEY)
        if maybe_compress():
            print("  [Compressed older memories]")

        # Response without calling Gemini (per-message replies are local)
        response = get_response_local(user_input, buffer)
        buffer.add("assistant", response)

        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()
