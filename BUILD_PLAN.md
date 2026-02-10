# 4-Day Build Plan: Human-Like Long-Term Memory for Conversational AI

> **For complete beginners.** Each day builds on the previous. Focus: memory architecture + logic flow.

---

## 🎯 What You're Building (High-Level)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CONVERSATIONAL AI WITH MEMORY                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   User says: "I'm allergic to peanuts, love Thai food, going to Tokyo"  │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │  SHORT-TERM (current turn + last 5–10 messages)               │     │
│   │  → Immediate context for the response                         │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │  MEMORY EXTRACTOR (Gemini or local logic)                     │     │
│   │  → Picks important facts: "allergic: peanuts", "food: Thai",  │     │
│   │    "travel: Tokyo"                                            │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │  LONG-TERM SEMANTIC MEMORY                                    │     │
│   │  → Stored by category (personal, food, travel, misc)          │     │
│   │  → Each memory has an embedding (vector) for similarity search │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │  RETRIEVAL (when user asks something)                         │     │
│   │  → Category-aware search → find relevant memories → use them  │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📅 Day-by-Day Plan

### **DAY 1: Foundation + Short-Term Memory**

**Goal:** Get a minimal chat running with short-term context. No AI yet—just structure.

#### Tasks
1. **Setup project** (30 min)
   - Create folder structure
   - Set up Python virtual environment
   - Create `requirements.txt`

2. **Define data models** (1 hr)
   - `Message`: `role`, `content`, `timestamp`
   - `ShortTermBuffer`: list of last N messages (e.g. 10)

3. **Implement short-term memory** (1–2 hr)
   - Add message to buffer
   - Truncate when full (keep most recent)
   - Format buffer for context (e.g. "User: X\nAssistant: Y\n...")

4. **Simple CLI chat loop** (1 hr)
   - Input → add to buffer → print response (dummy: "Echo: ...") → repeat

**Deliverable:** A running chat that remembers the last 10 messages.

**Logic flow:**
```
User input → Append to ShortTermBuffer → Format context string → (placeholder) → Print response
```

---

### **DAY 2: Long-Term Memory + Categories**

**Goal:** Add persistent storage and category-based organization.

#### Tasks
1. **Define memory schema** (1 hr)
   - `Memory`: `id`, `content`, `category`, `created_at`, `embedding` (placeholder)
   - Categories: `personal`, `food`, `travel`, `misc`

2. **Storage layer** (1–2 hr)
   - Use SQLite (simple, no server)
   - Tables: `memories` (id, content, category, embedding_blob, created_at)
   - Functions: `add_memory()`, `get_memories_by_category()`, `get_all_memories()`

3. **Memory extractor (local version)** (2 hr)
   - Rules: e.g. if message contains "I like X", "I'm allergic to X", "I'm going to X" → extract fact
   - Use regex or simple keyword matching (no Gemini yet)
   - Assign category based on keywords

4. **Wire into chat** (1 hr)
   - After each user message → run extractor → save to DB
   - Log: "Stored: [food] likes Thai food"

**Deliverable:** Chat that stores facts in a database by category.

**Logic flow:**
```
User input → ShortTermBuffer → Extract facts (local rules) → Save to SQLite by category
```

---

### **DAY 3: Embeddings, VL-JEPA-Inspired Latent Space, Retrieval**

**Goal:** Semantic search and JEPA-inspired representation.

#### Tasks
1. **Sentence embeddings** (1 hr)
   - Install `sentence-transformers`
   - Use `all-MiniLM-L6-v2` (lightweight, 384-dim)
   - Encode each memory when storing
   - Store embedding as blob in SQLite

2. **VL-JEPA-inspired latent space** (2 hr)
   - **Concept:** VL-JEPA predicts embeddings in a latent space instead of tokens.
   - **Our version:** Treat the embedding space as the "latent space."
   - Add a small **predictor**: given user query embedding, predict a "refined" query embedding that better matches how memories were stored.
   - Simple implementation: `refined = query_emb + alpha * (mean_memory_emb - query_emb)` (optional centering)
   - Or: use a tiny MLP that takes query_emb → predicted_emb (trained on (query, relevant_memory) pairs if you have data; otherwise skip and use raw embeddings)

   - **Beginner-friendly option:** Skip predictor; use standard similarity. Document: "Embeddings live in a JEPA-style latent space (sentence-transformers)." You can add the predictor later.

3. **Category-aware retrieval** (2 hr)
   - Given user query → guess category from keywords (or use embedding similarity to category centroids)
   - Search only in that category first (fast)
   - Fallback: search all memories if category search returns little

4. **Similarity search** (1 hr)
   - Use cosine similarity: `dot(q, m) / (norm(q) * norm(m))`
   - Return top-k memories
   - For SQLite: load embeddings, compute in Python (or use `sqlite-vec` if you want to go fancier)

5. **Use retrieved memories in context** (1 hr)
   - Before calling Gemini: build context = short-term + "Relevant memories:\n" + top memories

**Deliverable:** Retrieval that finds relevant memories by category and similarity.

**Logic flow:**
```
User query → Embed query → (Optional: refine with predictor) → Category-aware search →
Top-K memories → Build context → Ready for LLM
```

---

### **DAY 4: Gemini Integration, Compression, Fallbacks**

**Goal:** Full AI responses, memory compression, and robustness.

#### Tasks
1. **Gemini API integration** (1–2 hr)
   - Get API key from Google AI Studio
   - Use OpenAI-compatible SDK (OpenRouter)
   - Build prompt: system (instructions) + short-term context + retrieved memories + user message
   - Call Gemini → stream or get response

2. **Upgrade memory extractor with Gemini** (1 hr)
   - Prompt: "From this conversation, extract important factual information about the user. Output JSON: [{content, category}]"
   - Parse JSON → save to DB with embeddings
   - **Fallback:** If API fails → use Day 2 local extractor

3. **Memory compression** (2 hr)
   - When memory count > threshold (e.g. 50) → trigger compression
   - Call Gemini: "Summarize these memories into 3–5 concise facts: [list]"
   - Replace old memories with summary (one "compressed" memory)
   - **Fallback:** If API fails → keep oldest memories, add note "Compression skipped"

4. **API-failure tolerance** (1 hr)
   - Wrap all Gemini calls in try/except
   - On failure: use local/deterministic response
   - Log: "Gemini unavailable, using fallback"

5. **Polish & test** (1 hr)
   - Test with 50+ turns
   - Verify retrieval, compression, fallbacks

**Deliverable:** Production-ready system with Gemini, compression, and graceful fallbacks.

**Logic flow:**
```
User query → Retrieve memories → Build prompt → Try Gemini → Success? Use response : Use fallback
New memories → Count > 50? → Try compress via Gemini : Keep as is
```

---

## 📁 Suggested Project Structure

```
Project - Memory/
├── BUILD_PLAN.md          # This file
├── requirements.txt
├── .env                   # OPENROUTER_API_KEY (gitignore this!)
├── src/
│   ├── __init__.py
│   ├── main.py            # Entry point, chat loop
│   ├── config.py          # Constants, thresholds
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py  # ShortTermBuffer
│   │   ├── long_term.py   # SQLite, Memory model
│   │   ├── extractor.py   # Extract facts (local + Gemini)
│   │   ├── embeddings.py  # Sentence embeddings + JEPA-inspired logic
│   │   ├── retrieval.py   # Category-aware search
│   │   └── compression.py # Summarize old memories
│   └── llm/
│       ├── __init__.py
│       └── openrouter.py  # OpenRouter API + fallback
├── data/
│   └── memories.db        # SQLite DB (gitignore)
└── tests/
    └── (optional)
```

---

## 🧩 VL-JEPA Integration Options (Pick One for Day 3)

### Option A: Conceptual (Beginner)
- Use sentence-transformers embeddings.
- Treat them as your "latent space."
- Document: "JEPA-inspired: we operate in embedding space, not token space."
- **Effort:** 0 extra code.

### Option B: Simple Predictor (Intermediate)
- Add a small neural net: `query_embedding → predicted_embedding`.
- Train on pairs (user_question, relevant_memory_embedding) from your own logs.
- Use predicted embedding for retrieval.
- **Effort:** ~2–3 hr.

### Option C: Use JEPA Library (Advanced)
- `pip install jepa`
- Adapt their predictor for sentence embeddings.
- **Effort:** ~4+ hr, more reading.

**Recommendation:** Start with **Option A**. Add Option B in a future iteration if you have time.

---

## 📋 Prerequisites (Do Before Day 1)

1. **Python 3.10+**  
   - Check: `python3 --version`

2. **Git** (optional but useful)  
   - Check: `git --version`

3. **Google AI Studio account** (for Day 4)  
   - https://openrouter.ai/  
   - Create API key

4. **~2GB disk** for models (sentence-transformers downloads once)

---

## ✅ Daily Checklist

| Day | Done | Deliverable |
|-----|------|-------------|
| 1   | ☐    | Chat with short-term memory (last 10 msgs) |
| 2   | ☐    | Facts extracted and stored in SQLite by category |
| 3   | ☐    | Embeddings + category-aware retrieval working |
| 4   | ☐    | Gemini + compression + fallbacks working |

---

## 🆘 If You Get Stuck

- **Day 1:** Focus on "list of messages" and a simple loop. Ignore everything else.
- **Day 2:** SQLite is just `sqlite3` in Python. One table is enough.
- **Day 3:** Use `model.encode(["text"])` from sentence-transformers. Similarity = `np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))`.
- **Day 4:** Gemini SDK has a `generate_content()` method. Wrap it in try/except.

---

## 🔑 Key Logic Flows (Reference)

### Storing a memory
```
User message → Extractor (Gemini or local) → List of {content, category}
  → For each: encode to embedding → Save to DB
```

### Retrieving for a query
```
User query → Embed query → Infer category (or use all)
  → Load memories from category (or all)
  → Compute similarities → Sort → Top K → Return
```

### Generating response
```
User query
  → Retrieve top-K memories
  → Format: system + short-term + memories + query
  → Gemini API (or fallback)
  → Stream/return response
```

### Compressing
```
If memory_count > 50:
  → Get oldest 20–30 memories
  → Gemini: "Summarize into 3–5 facts"
  → Delete those, insert summary as 1 memory
```

---

Good luck! Start with Day 1 and move step by step.
