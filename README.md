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
Threads are device-scoped by default, so the same account can keep separate chat lists on different devices.

## Setup (first time)

1. Copy `.env.example` to `.env` and add your OpenRouter key:
   ```bash
   OPENROUTER_API_KEY=sk-or-your_key_here
   OPENROUTER_MODEL=openai/gpt-4o-mini
   ENABLE_WEB_SEARCH=1
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

## Deploy on Render

This repo now includes `/render.yaml` for one-click deployment.

1. Push this project to GitHub.
2. In Render, create a new **Blueprint** and select the repo.
3. Render reads `render.yaml` and creates the web service automatically.
4. Set required secret:
   - `OPENROUTER_API_KEY`
5. Deploy.

If you create the service manually instead of Blueprint:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn src.api:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- **Environment Variables:** `OPENROUTER_API_KEY`, `FLASK_SECRET_KEY`, optional `OPENROUTER_MODEL`
- **Optional live web data:** `ENABLE_WEB_SEARCH=1` (default on), `WEB_SEARCH_MAX_RESULTS=5`
- **Optional reliability setting on low-memory instances:** `EMBEDDING_BACKEND=lite`

### Data Persistence Note

By default the SQLite DB is local file storage and can reset after restart/redeploy on ephemeral instances.
On Render, attach a persistent disk and set:

```bash
MEMORY_DB_PATH=/var/data/memories.db
```

Without a persistent disk, user accounts and chat history can be lost after redeploys/restarts.

## CLI (alternative)

For terminal chat instead of the web UI:

```bash
python -m src.main
```
