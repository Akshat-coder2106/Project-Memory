"""Configuration and constants for the memory system."""

# Short-term memory
MAX_SHORT_TERM_MESSAGES = 10

# Categories for long-term memory
CATEGORIES = ["personal", "food", "travel", "misc"]

# Retrieval
TOP_K_MEMORIES = 5

# Compression
MEMORY_COMPRESSION_THRESHOLD = 50

# Deduplication: skip storing if similarity to existing memory > this
DUPLICATE_SIMILARITY_THRESHOLD = 0.92

# Database
DB_PATH = "data/memories.db"
