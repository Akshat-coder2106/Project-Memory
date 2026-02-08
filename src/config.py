"""Configuration and constants for the memory system."""

# Short-term memory
MAX_SHORT_TERM_MESSAGES = 10

# Categories for long-term memory
CATEGORIES = ["personal", "food", "travel", "misc"]

# Retrieval
TOP_K_MEMORIES = 5

# Compression
MEMORY_COMPRESSION_THRESHOLD = 50

# Deduplication: skip storing only if very similar (0.95 = avoid dropping distinct facts)
DUPLICATE_SIMILARITY_THRESHOLD = 0.95

# Database
DB_PATH = "data/memories.db"
