"""ChatLog model — stores AI chat messages tied to snippets."""

import reflex as rx
from typing import Optional


class ChatLog(rx.Model, table=True):
    """A single chat message associated with a snippet."""

    snippet_id: int = 0
    role: str = "user"  # "user" or "assistant"
    content: str = ""
    timestamp: str = ""
