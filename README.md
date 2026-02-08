# Human-Like Long-Term Memory for Conversational AI

Hierarchical memory (short-term + long-term semantic) with category-aware retrieval, VL-JEPA-inspired embeddings, and Gemini-powered extraction/compression.

## Quick Start

```bash
cd "Project - Memory"
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Add GEMINI_API_KEY for AI responses (required for full features)
cp .env.example .env
# Edit .env and add your key from https://aistudio.google.com/apikey

python -m src.main
```

Type messages and `quit` to exit.

**CLI commands:** `/help`, `/memories`, `/stats`, `/export`, `/clear`

## What It Does

- **Short-term memory:** Keeps last 10 messages for immediate context
- **Long-term memory:** Extracts facts (allergies, preferences, travel, etc.) and stores in SQLite
- **Categories:** personal, food, travel, misc for fast partitioned retrieval
- **Embeddings:** sentence-transformers (all-MiniLM) in a VL-JEPA-inspired latent space
- **Retrieval:** Category-aware semantic search with JEPA-style query refinement
- **Compression:** When memory exceeds 50 items, older ones are summarized via Gemini
- **Fallbacks:** Works without Gemini using local extraction and deterministic responses
- **VL-JEPA:** Optional embedding backend (Mac/Apple Silicon) — set `USE_VLJEPA=1` and install `requirements-vljepa.txt`

## Project Structure

```
src/
├── main.py            # Chat loop
├── config.py          # Constants
├── memory/
│   ├── short_term.py  # Last N messages
│   ├── long_term.py   # SQLite storage
│   ├── extractor.py   # Fact extraction (local + Gemini)
│   ├── embeddings.py  # Sentence embeddings + JEPA refine
│   ├── retrieval.py   # Category-aware semantic search
│   └── compression.py # Summarize old memories
└── llm/
    └── gemini.py      # Gemini API + fallback
```
