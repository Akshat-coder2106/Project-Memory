"""
Main entry point - conversational AI with hierarchical memory.

Run from project root:
python -m src.main
"""

import sys
from pathlib import Path

# Load .env early so OPENROUTER_API_KEY is available
sys.path.insert(0, str(Path(__file__).parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from memory.short_term import ShortTermBuffer
from memory.long_term import (
    init_db,
    add_memory,
    get_memory_count,
    get_all_memories,
    delete_memories,
)
from memory.extractor import extract_local, extract_with_openrouter
from memory.embeddings import encode, get_backend
from memory.retrieval import retrieve
from memory.compression import maybe_compress
from llm.openrouter import generate, is_available, is_quota_saving
from config import MAX_SHORT_TERM_MESSAGES, TOP_K_MEMORIES, CATEGORIES


# ------------------ helpers ------------------

def _get_fallback_message() -> str:
    """Shown when OpenRouter is unavailable."""
    import os
    from pathlib import Path

    key = os.environ.get("OPENROUTER_API_KEY")
    env_path = Path(__file__).resolve().parent.parent / ".env"

    if not key:
        return (
            "I can't connect to the AI right now.\n"
            f"Create {env_path} with:\n"
            "OPENROUTER_API_KEY=your_key\n"
            "Then restart the app."
        )
    return "AI is temporarily unavailable. Please try again."


CLI_HELP = """
Commands:
  /memories [category]  List stored memories
  /stats                Show memory statistics
  /export [file]        Export memories to JSON
  /clear                Delete all memories
  /help                 Show this help
  quit / exit / q       Exit
"""

SYSTEM_INSTRUCTION = """You are a helpful conversational assistant with long-term memory.
Use relevant memories naturally. Be concise and accurate.
If memory conflicts with recent input, prefer the latest message."""


# ------------------ core logic ------------------

def build_context(short_term: ShortTermBuffer, memories_text: str) -> str:
    parts = []
    if memories_text:
        parts.append("Relevant memories:\n" + memories_text)
    parts.append("Recent conversation:\n" + short_term.format_for_context())
    return "\n\n".join(parts)


def get_response(user_message: str, short_term: ShortTermBuffer) -> str:
    mems = retrieve(user_message, top_k=TOP_K_MEMORIES)
    memories_text = "\n".join(f"- [{m.category}] {m.content}" for m in mems) if mems else ""
    context = build_context(short_term, memories_text)
    prompt = f"{context}\n\nAssistant:"

    response = generate(prompt, system_instruction=SYSTEM_INSTRUCTION)
    return response if response else _get_fallback_message()


def process_and_store_facts(user_message: str, use_openrouter: bool) -> list[dict]:
    from config import DUPLICATE_SIMILARITY_THRESHOLD
    from memory.long_term import has_similar_memory

    extracted = (
        extract_with_openrouter(user_message)
        if use_openrouter
        else extract_local(user_message)
    )

    stored = []
    for item in extracted:
        content = item["content"]
        category = item["category"]

        try:
            embedding = encode(content)
        except Exception:
            embedding = None

        if embedding and has_similar_memory(
            embedding, category, DUPLICATE_SIMILARITY_THRESHOLD
        ):
            continue

        add_memory(content=content, category=category, embedding=embedding)
        stored.append(item)

    return stored


def handle_cli_command(cmd: str) -> bool:
    cmd = cmd.strip().lower()

    if cmd == "/help":
        print(CLI_HELP)
        return True

    if cmd == "/stats":
        mems = get_all_memories()
        print(f"\nMemories: {len(mems)} total")
        for c in CATEGORIES:
            print(f"  {c}: {sum(1 for m in mems if m.category == c)}")
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
            for m in mems:
                print(f"[{m.category}] {m.content}")
            print()
        return True

    if cmd == "/clear":
        confirm = input("Delete all memories? (yes/no): ").lower()
        if confirm == "yes":
            delete_memories([m.id for m in get_all_memories() if m.id])
            print("All memories cleared.\n")
        return True

    return False


# ------------------ main ------------------

def main():
    init_db()
    buffer = ShortTermBuffer(max_size=MAX_SHORT_TERM_MESSAGES)
    has_openrouter = is_available()

    print("=== Memory-Enabled Conversational AI ===")
    print(f"(Embeddings backend: {get_backend()})")

    if has_openrouter:
        print(
            "(OpenRouter connected — quota saver ON)"
            if is_quota_saving()
            else "(OpenRouter connected)"
        )
    else:
        print("(OpenRouter unavailable — local fallback active)")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if user_input.startswith("/") and handle_cli_command(user_input):
            continue

        buffer.add("user", user_input)

        stored = process_and_store_facts(
            user_input,
            use_openrouter=has_openrouter and not is_quota_saving(),
        )

        for s in stored:
            print(f"[Stored] [{s['category']}] {s['content']}")

        if not is_quota_saving() and maybe_compress():
            print("[Compressed older memories]")

        response = get_response(user_input, buffer)
        buffer.add("assistant", response)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()
