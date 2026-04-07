"""About page — project info, tech stack, documentation."""

import reflex as rx
from codementor.components.navbar import navbar, notification_toast
from codementor.components.theme import COLORS


TECH_ITEMS = [
    ("Reflex", "Python-based full-stack web framework", "#58a6ff", "layers"),
    ("Python AST", "Built-in abstract syntax tree parser", "#3fb950", "git-branch"),
    ("pyflakes", "Static error and bug detection", "#f85149", "circle_x"),
    ("pycodestyle", "PEP8 compliance checker", "#d29922", "square_check"),
    ("Gemini 1.5 Flash", "Google's fast multimodal LLM for AI analysis", "#bc8cff", "bot"),
    ("networkx + matplotlib", "Control flow graph generation and rendering", "#ffa657", "git_fork"),
    ("PostgreSQL / Neon.tech", "Serverless PostgreSQL database", "#58a6ff", "database"),
    ("SQLModel", "Type-safe ORM built on SQLAlchemy + Pydantic", "#3fb950", "table"),
]

MODULES = [
    {
        "number": "01",
        "title": "Code Parsing & Preprocessing",
        "description": "Accept Python code via paste or upload. Parse using Python's ast module to extract functions, classes, imports, and calculate cyclomatic complexity.",
        "color": "#58a6ff",
    },
    {
        "number": "02",
        "title": "Error & Bug Detection",
        "description": "Identify syntax errors, undefined variables, unused imports, and logical issues. All powered by pyflakes with structured, line-specific output.",
        "color": "#f85149",
    },
    {
        "number": "03",
        "title": "Coding Style Analysis",
        "description": "Check adherence to PEP8 standards using pycodestyle. Get a 0-100 compliance score and line-by-line style violation reports.",
        "color": "#d29922",
    },
    {
        "number": "04",
        "title": "AI Optimization Suggestions",
        "description": "Gemini 1.5 Flash analyzes your code for efficiency, readability, and best practices. Returns complexity analysis, before/after snippets, and actionable tips.",
        "color": "#bc8cff",
    },
    {
        "number": "05",
        "title": "Control Flow Visualization",
        "description": "Builds a Control Flow Graph from the AST using networkx. Rendered as a high-quality PNG showing branches, loops, function calls, and merge points.",
        "color": "#3fb950",
    },
]


def tech_item(item: tuple) -> rx.Component:
    name, desc, color, icon = item
    return rx.hstack(
        rx.box(
            rx.icon(icon, size=18, color=color),
            background=f"rgba(88,166,255,0.1)",
            border_radius="8px",
            padding="8px",
            width="36px",
            height="36px",
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(name, font_size="14px", font_weight="600",
                    color=COLORS["text_primary"]),
            rx.text(desc, font_size="12px", color=COLORS["text_secondary"]),
            spacing="0",
            align="start",
        ),
        spacing="3",
        align="center",
        padding="12px 0",
        border_bottom=f"1px solid {COLORS['border']}",
        width="100%",
    )


def module_card(module: dict) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.text(module["number"],
                    font_size="24px",
                    font_weight="800",
                    color=module["color"],
                    font_family="monospace"),
            flex_shrink="0",
            width="48px",
        ),
        rx.vstack(
            rx.text(module["title"],
                    font_size="15px", font_weight="600",
                    color=COLORS["text_primary"]),
            rx.text(module["description"],
                    font_size="13px", color=COLORS["text_secondary"],
                    line_height="1.6"),
            spacing="1",
            align="start",
        ),
        spacing="4",
        align="start",
        padding="16px",
        background=COLORS["bg_secondary"],
        border=f"1px solid {COLORS['border']}",
        border_left=f"3px solid {module['color']}",
        border_radius="4px 8px 8px 4px",
        _hover={"border_left_color": module["color"],
                "box_shadow": "0 4px 16px rgba(0,0,0,0.2)"},
        transition="all 0.2s",
    )


def about() -> rx.Component:
    return rx.box(
        navbar(),
        notification_toast(),
        rx.box(
            rx.vstack(
                # Header
                rx.vstack(
                    rx.badge("Open Source Project", color_scheme="green", variant="soft"),
                    rx.heading("About AI Code Reviewer",
                               size="8", color=COLORS["text_primary"],
                               font_weight="800"),
                    rx.text(
                        "An AI-powered code review platform designed to help students "
                        "and developers write better, cleaner, and more efficient Python code.",
                        font_size="16px",
                        color=COLORS["text_secondary"],
                        line_height="1.7",
                        max_width="640px",
                        text_align="center",
                    ),
                    spacing="4",
                    align="center",
                    margin_bottom="48px",
                ),

                rx.separator(color=COLORS["border"], width="100%"),

                # Two-column layout
                rx.hstack(
                    # Left: Modules
                    rx.vstack(
                        rx.text("MODULES", font_size="11px", font_weight="600",
                                color=COLORS["text_muted"], letter_spacing="1px"),
                        *[module_card(m) for m in MODULES],
                        spacing="3",
                        align="start",
                        flex="1",
                    ),

                    rx.separator(orientation="vertical", color=COLORS["border"],
                                 height="auto"),

                    # Right: Tech stack + project info
                    rx.vstack(
                        rx.text("TECH STACK", font_size="11px", font_weight="600",
                                color=COLORS["text_muted"], letter_spacing="1px"),
                        *[tech_item(t) for t in TECH_ITEMS],

                        rx.separator(color=COLORS["border"], width="100%",
                                     margin_y="16px"),

                        rx.text("PROJECT INFO", font_size="11px", font_weight="600",
                                color=COLORS["text_muted"], letter_spacing="1px"),

                        rx.hstack(
                            rx.icon("target", size=14, color=COLORS["text_muted"]),
                            rx.text("Goal: Reduce manual code review effort for "
                                    "instructors while helping students improve faster.",
                                    font_size="13px", color=COLORS["text_secondary"],
                                    line_height="1.5"),
                            spacing="2",
                            align="start",
                        ),
                        rx.hstack(
                            rx.icon("users", size=14, color=COLORS["text_muted"]),
                            rx.text("Target users: CS students, bootcamp learners, "
                                    "programming instructors.",
                                    font_size="13px", color=COLORS["text_secondary"]),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.icon("code", size=14, color=COLORS["text_muted"]),
                            rx.text("Languages supported: Python (more coming soon)",
                                    font_size="13px", color=COLORS["text_secondary"]),
                            spacing="2",
                            align="center",
                        ),

                        rx.separator(color=COLORS["border"], width="100%",
                                     margin_y="16px"),

                        rx.link(
                            rx.button(
                                rx.icon("play", size=14),
                                "Try the Analyzer",
                                color_scheme="blue",
                                variant="solid",
                                size="2",
                            ),
                            href="/analyze",
                        ),

                        width="380px",
                        min_width="380px",
                        spacing="2",
                        align="start",
                    ),

                    spacing="8",
                    align="start",
                    width="100%",
                    padding_top="32px",
                ),

                spacing="0",
                width="100%",
                padding="32px 48px",
                max_width="1200px",
                margin="0 auto",
            ),
            margin_top="56px",
            min_height="calc(100vh - 56px)",
            overflow_y="auto",
        ),
        background=COLORS["bg_primary"],
        min_height="100vh",
    )
