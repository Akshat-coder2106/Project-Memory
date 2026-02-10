# Human-Like Long-Term Memory for Conversational AI

Chat app with hierarchical memory (short-term + long-term semantic), category-aware retrieval, and Gemini-powered extraction/compression.

## Quick start (one command)

```bash
cd "Project - Memory"
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.api
```

Open **http://localhost:5000** in your browser.
Create an account (username + password) on first use, then login to access that user's memories/chat history.

## Setup (first time)

1. Copy `.env.example` to `.env` and add your Gemini API key:
   ```
   GEMINI_API_KEY=your_key_here
   ```
   Get a key at https://aistudio.google.com/apikey

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run

```bash
python -m src.api
```

- **Chat UI:** http://localhost:5000  
- **API:** http://localhost:5000/api/chat, /api/messages, /api/memories, /api/health
- **Auth API:** /api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/me

## CLI (alternative)

For terminal chat instead of the web UI:

```bash
python -m src.main
```
