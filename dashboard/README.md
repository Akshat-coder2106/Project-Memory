# Memory System Dashboard

Research-grade dashboard for the human-like long-term memory system.  
**Tone:** minimal, futuristic, trustworthy. **Focus:** clarity, speed, safety.

## Run

Open `index.html` in a browser, or serve locally:

```bash
cd dashboard
python -m http.server 8080
# Open http://localhost:8080
```

## Layout

- **Left:** Chat panel — compact bubbles, memory tags (personal/food/travel/misc), badge when a message created/updated stored memories
- **Center:** Memory inspector — retrieved memories ranked by relevance; category chips, similarity score, timestamp, source snippet; edit, pin, delete, expand actions
- **Right:** Pipeline & health — Short-term → Semantic Retriever → Global Fallback → Compression; real-time status, API latency, fallback activations, memory size
- **Top:** Global search (semantic + keyword), category filters, safe-mode toggle
- **Bottom:** Compress, Export, Suggest memory (review queue)

## Sample Data

See `SAMPLE_DATA.md` for 10 sample memories across categories, mixed timestamps, and one compressed summary.

## Interactions

- Hover: relevance highlights
- Selection: provenance and confidence
- Graceful error UI when Gemini unavailable: local-fallback indicator + last-success timestamp

## Accessibility

- Keyboard navigation (Tab, Enter, ⌘K for search)
- Focus-visible outlines
- ARIA labels and roles
- `prefers-reduced-motion` and `prefers-contrast` supported
