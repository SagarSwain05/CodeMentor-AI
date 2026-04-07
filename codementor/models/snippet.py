"""Snippet model — stores code submissions."""

import reflex as rx
from typing import Optional


class Snippet(rx.Model, table=True):
    """A saved code snippet with analysis metadata."""

    title: str = "untitled.py"
    code: str = ""
    language: str = "python"
    style_score: int = 0
    error_count: int = 0
    style_issue_count: int = 0
    created_at: str = ""

    class Config:
        arbitrary_types_allowed = True
