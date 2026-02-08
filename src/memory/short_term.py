"""Short-term memory buffer - keeps last N messages for immediate context."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ShortTermBuffer:
    """
    Holds the most recent messages for context.
    Logic: append new → if over limit, remove oldest.
    """

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self.messages: list[Message] = []

    def add(self, role: str, content: str):
        """Add a message and trim if needed."""
        self.messages.append(Message(role=role, content=content))
        while len(self.messages) > self.max_size:
            self.messages.pop(0)

    def format_for_context(self) -> str:
        """Turn buffer into a string for the LLM prompt."""
        lines = []
        for m in self.messages:
            prefix = "User:" if m.role == "user" else "Assistant:"
            lines.append(f"{prefix} {m.content}")
        return "\n".join(lines) if lines else "(No previous messages)"

    def clear(self):
        """Clear all messages."""
        self.messages.clear()
