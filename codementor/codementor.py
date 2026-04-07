"""
AI Code Reviewer — Main application entry point.
Registers all pages and configures the Reflex app.
"""

import reflex as rx

# Import all models so Reflex creates their tables
from codementor.models import Snippet, ChatLog  # noqa: F401

from codementor.pages.home import home
from codementor.pages.analyze import analyze
from codementor.pages.history import history
from codementor.pages.about import about
from codementor.pages.settings import settings


# ─── App Configuration ────────────────────────────────────────────────────────

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="blue",
        gray_color="slate",
        radius="medium",
        scaling="95%",
    ),
    stylesheets=[
        "/styles/custom.css",
    ],
)


# ─── Register Pages ──────────────────────────────────────────────────────────

app.add_page(
    home,
    route="/",
    title="AI Code Reviewer — AI-Powered Code Reviewer",
    description="Analyze Python code for errors, style issues, and get AI optimization suggestions.",
)

app.add_page(
    analyze,
    route="/analyze",
    title="Analyze Code — AI Code Reviewer",
    description="Paste or upload Python code for instant AI-powered analysis.",
)

app.add_page(
    history,
    route="/history",
    title="History — AI Code Reviewer",
    description="View your saved code snippets and past analyses.",
)

app.add_page(
    about,
    route="/about",
    title="About — AI Code Reviewer",
    description="Learn about the AI Code Reviewer project, tech stack, and modules.",
)

app.add_page(
    settings,
    route="/settings",
    title="Settings — AI Code Reviewer",
    description="Configure your AI Code Reviewer API keys and preferences.",
)
