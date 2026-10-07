"""
AI Code Reviewer — Main application entry point.
Registers all pages and configures the Reflex app.
"""

import reflex as rx

# Import all models so Reflex creates their tables
from codementor.models import Snippet, ChatLog  # noqa: F401
from codementor.services.db_service import ensure_tables
from codementor.services.syntax_service import prefetch_grammars

# Make sure history tables exist even on a brand-new database
ensure_tables()
# Warm the tree-sitter grammar cache in the background (no-op if unavailable)
prefetch_grammars()

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
    title="CodeMentor AI — AI-Powered Code Reviewer",
    description="Review code in 40+ languages: errors, style, security, complexity, control flow and AI optimization.",
)

app.add_page(
    analyze,
    route="/analyze",
    title="Analyze Code — CodeMentor AI",
    description="Paste, upload or import code in any language for instant AI-powered analysis.",
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
