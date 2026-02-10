# Human-Like Long-Term Memory for Conversational AI

Chat app with hierarchical memory (short-term + long-term semantic), category-aware retrieval, and AI-powered extraction/compression (OpenRouter recommended).

## Quick start (one command)

```bash
cd "Project - Memory"
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./.venv/bin/python -m src.api
```

Open **http://localhost:5000** in your browser.
Create an account (username + password) on first use, then login to access that user's memories/chat history.

## Setup (first time)

1. Copy `.env.example` to `.env` and add your OpenRouter key:
   ```bash
   OPENROUTER_API_KEY=sk-or-your_key_here
   OPENROUTER_MODEL=openai/gpt-4o-mini
   ```
   Get a key at https://openrouter.ai/keys

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run

```bash
./.venv/bin/python -m src.api
```

- **Chat UI:** http://localhost:5000  
- **API:** http://localhost:5000/api/chat, /api/messages, /api/memories, /api/health
- **Auth API:** /api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/me

## CLI (alternative)

For terminal chat instead of the web UI:

```bash
python -m src.main
```
