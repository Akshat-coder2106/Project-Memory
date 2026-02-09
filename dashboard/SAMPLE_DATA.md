# Sample Test Data for Designer

## 10 Memories (mixed categories, timestamps, 1 compressed)

| # | Content | Category | Similarity | Timestamp | Source Snippet |
|---|---------|----------|------------|-----------|----------------|
| 1 | My name is Umesh | personal | 0.94 | 2025-02-08T10:23:00Z | User: I'm Umesh, allergic to peanuts... |
| 2 | Allergic to peanuts | personal | 0.91 | 2025-02-08T10:23:00Z | User: I'm Umesh, allergic to peanuts... |
| 3 | Friend name is Akshat | personal | 0.88 | 2025-02-08T10:23:00Z | User: My friend Akshat and I love Thai food |
| 4 | Loves Thai food | food | 0.89 | 2025-02-08T10:23:00Z | User: ...and I love Thai food |
| 5 | Planning trip to Tokyo next month | travel | 0.92 | 2025-02-08T10:25:00Z | User: Planning a trip to Tokyo next month |
| 6 | Has a brother named Shailesh | personal | 0.85 | 2025-02-07T15:42:00Z | User: I have a brother named Shailesh |
| 7 | Works as a software engineer | personal | 0.82 | 2025-02-06T09:10:00Z | User: I work as a software engineer |
| 8 | Vegetarian diet | food | 0.87 | 2025-02-05T14:30:00Z | User: I'm vegetarian |
| 9 | Visited Paris last year | travel | 0.79 | 2025-02-04T11:00:00Z | User: I visited Paris last year |
| 10 | [Compressed summary] User is Umesh; allergic to peanuts; loves Thai food; vegetarian; friend Akshat; brother Shailesh; software engineer; plans Tokyo trip; visited Paris. | misc | 0.76 | 2025-02-03T08:00:00Z | Compression run |

## Category breakdown
- **personal**: 5
- **food**: 2
- **travel**: 2
- **misc**: 1 (compressed)

## Microcopy (short, human, reassuring)
- Search placeholder: "Semantic or keyword search…"
- Safe mode: "Safe mode"
- Panel headers: "Conversation", "Retrieved memories", "Pipeline & health"
- Action bar: "Compress", "Export", "Suggest memory"
- Error state: "Using local fallback" + "Last API: 2m ago"
- Success: "Gemini connected" + "Last success: just now"
