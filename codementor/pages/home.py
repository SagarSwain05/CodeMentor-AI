"""Home / Landing page — assembles navbar, hero, features, and footer."""

import reflex as rx
from codementor.components.navbar import navbar, notification_toast
from codementor.components.hero import hero
from codementor.components.footer import footer
from codementor.components.theme import COLORS


# ── Feature cards data ────────────────────────────────────────────────────────

FEATURES = [
    {
        "icon": "bug",
        "title": "Smart Bug Detection",
        "description": "Catches syntax errors, undefined variables, unused imports, and runtime issues using Python AST + Pylint — before you even run the code.",
        "color": "#f85149",
    },
    {
        "icon": "square_check",
        "title": "PEP 8 Style Analysis",
        "description": "Enforces Python's official style guide automatically. Get a Style Score out of 100 with line-by-line feedback on indentation, naming, and formatting.",
        "color": "#d29922",
    },
    {
        "icon": "shield_alert",
        "title": "Security Vulnerability Scan",
        "description": "Powered by Bandit. Detects OWASP-equivalent Python vulnerabilities — eval misuse, hardcoded secrets, unsafe subprocess calls, SQL injection patterns.",
        "color": "#ffa657",
    },
    {
        "icon": "bar_chart_2",
        "title": "Complexity Analysis",
        "description": "Radon computes Cyclomatic Complexity (A–F grade per function) and a Maintainability Index. Know exactly which functions are too complex to maintain.",
        "color": "#3fb950",
    },
    {
        "icon": "bot",
        "title": "AI Chat Assistant",
        "description": "Ask anything about your code in natural language. Powered by Ollama + qwen2.5-coder:7b running 100% locally. Explain, debug, optimize, or document.",
        "color": "#bc8cff",
    },
    {
        "icon": "git_branch",
        "title": "Control Flow Graph",
        "description": "Visualize how your code executes — branches, loops, conditionals, and function calls rendered as an interactive graph.",
        "color": "#58a6ff",
    },
    {
        "icon": "github",
        "title": "GitHub Repo Import",
        "description": "Import any GitHub repository, browse the file tree, and analyze individual files. RAG-powered chat answers questions about your entire codebase.",
        "color": "#8b949e",
    },
    {
        "icon": "terminal",
        "title": "Live Code Execution",
        "description": "Run Python code in a sandboxed environment and see output instantly in the integrated terminal.",
        "color": "#58a6ff",
    },
    {
        "icon": "clock",
        "title": "Analysis History",
        "description": "Every analysis is saved with a timestamp. Track your improvement over time and revisit past sessions.",
        "color": "#d29922",
    },
]

TECH_STACK = [
    ("Python 3.11+", "gray"),
    ("Reflex 0.8", "blue"),
    ("Ollama", "purple"),
    ("qwen2.5-coder:7b", "purple"),
    ("Python AST", "blue"),
    ("Pylint", "yellow"),
    ("Bandit", "orange"),
    ("Radon", "green"),
    ("ChromaDB", "blue"),
    ("BM25", "gray"),
    ("Graphviz", "green"),
    ("PyGitHub", "gray"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


# ── Feature card ──────────────────────────────────────────────────────────────

def feature_card(feature: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon(feature["icon"], size=20, color=feature["color"]),
                background=f"rgba({_hex_to_rgb(feature['color'])},0.10)",
                border=f"1px solid rgba({_hex_to_rgb(feature['color'])},0.25)",
                border_radius="8px",
                padding="10px",
                width="fit-content",
            ),
            rx.text(feature["title"],
                    font_size="14px", font_weight="600",
                    color=COLORS["text_primary"]),
            rx.text(feature["description"],
                    font_size="13px", color=COLORS["text_secondary"],
                    line_height="1.65"),
            spacing="3",
            align="start",
        ),
        background=COLORS["bg_secondary"],
        border=f"1px solid {COLORS['border']}",
        border_radius="10px",
        padding="20px",
        _hover={
            "border_color": feature["color"],
            "transform": "translateY(-3px)",
            "box_shadow": f"0 12px 32px rgba(0,0,0,0.35)",
        },
        transition="all 0.2s ease",
        cursor="default",
    )


# ── Features section ──────────────────────────────────────────────────────────

def features_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.badge(
                rx.hstack(
                    rx.icon("sparkles", size=12),
                    rx.text("Features"),
                    spacing="1",
                ),
                color_scheme="blue",
                variant="soft",
                padding="4px 12px",
            ),
            rx.heading(
                "Everything you need to write better code",
                size="7",
                color=COLORS["text_primary"],
                text_align="center",
                font_weight="700",
                letter_spacing="-0.5px",
            ),
            rx.text(
                "From basic syntax checking to AI-powered optimization, "
                "AI Code Reviewer gives you a complete code quality toolkit.",
                font_size="15px",
                color=COLORS["text_secondary"],
                text_align="center",
                max_width="540px",
                line_height="1.7",
            ),
            spacing="3",
            align="center",
            margin_bottom="40px",
        ),
        rx.grid(
            *[feature_card(f) for f in FEATURES],
            columns=rx.breakpoints({"0px": "1", "640px": "2", "1024px": "3"}),
            spacing="4",
            width="100%",
        ),
        padding_x=rx.breakpoints({"0px": "20px", "768px": "48px"}),
        padding_y="64px",
        max_width="1200px",
        margin="0 auto",
        width="100%",
    )


# ── How it works section ──────────────────────────────────────────────────────

def _step(number: str, title: str, desc: str, color: str) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.box(
                rx.text(number, font_size="14px", font_weight="800",
                        color="white"),
                background=f"linear-gradient(135deg, {color}, {color}aa)",
                border_radius="50%",
                width="36px",
                height="36px",
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink="0",
            ),
            rx.vstack(
                rx.text(title, font_size="14px", font_weight="600",
                        color=COLORS["text_primary"]),
                rx.text(desc, font_size="13px", color=COLORS["text_secondary"],
                        line_height="1.6"),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="start",
        ),
    )


def how_it_works_section() -> rx.Component:
    steps = [
        ("1", "Paste or write your Python code",
         "Use the built-in code editor or upload a .py file directly.", "#58a6ff"),
        ("2", "Click Analyze",
         "AST parsing, Pylint, Bandit, and Radon run simultaneously in under 2 seconds.", "#3fb950"),
        ("3", "Review your results",
         "Errors, style issues, security warnings, and complexity grades appear instantly.", "#d29922"),
        ("4", "Chat with the AI",
         "Ask questions in plain English. The AI explains issues and suggests optimized rewrites.", "#bc8cff"),
        ("5", "Fix and iterate",
         "Apply suggestions, re-analyze, watch your scores improve.", "#ffa657"),
    ]
    return rx.box(
        rx.box(
            rx.vstack(
                rx.badge("How It Works", color_scheme="green", variant="soft",
                         padding="4px 12px"),
                rx.heading(
                    "From paste to insight in seconds",
                    size="7",
                    color=COLORS["text_primary"],
                    font_weight="700",
                    letter_spacing="-0.5px",
                    text_align="center",
                ),
                spacing="3",
                align="center",
                margin_bottom="40px",
            ),
            rx.hstack(
                rx.vstack(
                    *[_step(*s) for s in steps],
                    spacing="5",
                    align="start",
                    max_width="520px",
                    width="100%",
                ),
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("zap", size=32, color="#58a6ff"),
                            rx.vstack(
                                rx.text("Zero Setup Required",
                                        font_size="16px", font_weight="700",
                                        color=COLORS["text_primary"]),
                                rx.text("No API keys. No cloud accounts. Just run and analyze.",
                                        font_size="13px",
                                        color=COLORS["text_secondary"]),
                                spacing="1",
                                align="start",
                            ),
                            spacing="4",
                            align="start",
                        ),
                        rx.separator(color=COLORS["border"]),
                        rx.hstack(
                            rx.icon("lock", size=32, color="#3fb950"),
                            rx.vstack(
                                rx.text("100% Private",
                                        font_size="16px", font_weight="700",
                                        color=COLORS["text_primary"]),
                                rx.text("Your code runs on your machine. Never sent to external servers.",
                                        font_size="13px",
                                        color=COLORS["text_secondary"]),
                                spacing="1",
                                align="start",
                            ),
                            spacing="4",
                            align="start",
                        ),
                        rx.separator(color=COLORS["border"]),
                        rx.hstack(
                            rx.icon("cpu", size=32, color="#bc8cff"),
                            rx.vstack(
                                rx.text("Local AI Inference",
                                        font_size="16px", font_weight="700",
                                        color=COLORS["text_primary"]),
                                rx.text("Ollama runs qwen2.5-coder:7b locally — no quotas, no rate limits.",
                                        font_size="13px",
                                        color=COLORS["text_secondary"]),
                                spacing="1",
                                align="start",
                            ),
                            spacing="4",
                            align="start",
                        ),
                        spacing="5",
                        align="start",
                        padding="32px",
                        background=COLORS["bg_secondary"],
                        border=f"1px solid {COLORS['border']}",
                        border_radius="12px",
                        max_width="440px",
                        width="100%",
                    ),
                ),
                justify="between",
                align="start",
                spacing="8",
                wrap="wrap",
            ),
            max_width="1200px",
            margin="0 auto",
            padding_x=rx.breakpoints({"0px": "20px", "768px": "48px"}),
            padding_y="64px",
        ),
        background=COLORS["bg_secondary"],
        border_top=f"1px solid {COLORS['border']}",
        border_bottom=f"1px solid {COLORS['border']}",
        width="100%",
    )


# ── Tech stack section ────────────────────────────────────────────────────────

def tech_stack_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text("BUILT WITH", font_size="11px", font_weight="700",
                    color=COLORS["text_muted"], letter_spacing="2px"),
            rx.hstack(
                *[
                    rx.badge(name, color_scheme=color, variant="soft",
                             font_size="12px", padding="5px 12px",
                             border_radius="20px")
                    for name, color in TECH_STACK
                ],
                wrap="wrap",
                justify="center",
                spacing="2",
                max_width="860px",
            ),
            spacing="4",
            align="center",
        ),
        padding="48px 48px",
        width="100%",
        text_align="center",
    )


# ── CTA banner ────────────────────────────────────────────────────────────────

def cta_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading(
                "Ready to write better code?",
                size="7",
                color=COLORS["text_primary"],
                font_weight="700",
                text_align="center",
                letter_spacing="-0.5px",
            ),
            rx.text(
                "Start analyzing your Python code instantly — no sign-up, no API keys, no cost.",
                font_size="15px",
                color=COLORS["text_secondary"],
                text_align="center",
                line_height="1.7",
            ),
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.icon("play", size=16),
                        "Start Reviewing Now",
                        size="3",
                        color_scheme="blue",
                        variant="solid",
                        font_size="15px",
                        font_weight="600",
                        height="46px",
                        padding="0 32px",
                        border_radius="8px",
                        _hover={
                            "opacity": "0.9",
                            "transform": "translateY(-1px)",
                            "box_shadow": "0 8px 24px rgba(88,166,255,0.3)",
                        },
                        transition="all 0.2s ease",
                    ),
                    href="/analyze",
                ),
                rx.link(
                    rx.button(
                        rx.icon("book_open", size=16),
                        "About the Project",
                        size="3",
                        variant="outline",
                        color=COLORS["text_secondary"],
                        border_color=COLORS["border"],
                        font_size="15px",
                        height="46px",
                        padding="0 24px",
                        border_radius="8px",
                        _hover={
                            "border_color": COLORS["text_primary"],
                            "color": COLORS["text_primary"],
                        },
                        transition="all 0.2s ease",
                    ),
                    href="/about",
                ),
                spacing="3",
                justify="center",
                wrap="wrap",
            ),
            spacing="5",
            align="center",
            padding="64px 48px",
            max_width="640px",
            margin="0 auto",
        ),
        width="100%",
        background=COLORS["bg_primary"],
    )


# ── Page assembly ─────────────────────────────────────────────────────────────

def home() -> rx.Component:
    return rx.box(
        navbar(),
        notification_toast(),

        rx.box(
            hero(),
            features_section(),
            how_it_works_section(),
            tech_stack_section(),
            cta_section(),
            footer(),

            margin_top="56px",
            overflow_y="auto",
            height="calc(100vh - 56px)",
        ),

        background=COLORS["bg_primary"],
        min_height="100vh",
        class_name="page-scroll",
    )
