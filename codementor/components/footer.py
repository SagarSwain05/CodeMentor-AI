"""Footer component for AI Code Reviewer."""

import reflex as rx
from codementor.components.theme import COLORS


def _footer_link(label: str, href: str, external: bool = False) -> rx.Component:
    return rx.link(
        label,
        href=href,
        font_size="13px",
        color=COLORS["text_muted"],
        text_decoration="none",
        is_external=external,
        _hover={
            "color": COLORS["text_secondary"],
            "text_decoration": "underline",
        },
        transition="color 0.15s ease",
    )


def _footer_column(heading: str, links: list) -> rx.Component:
    return rx.vstack(
        rx.text(heading, font_size="12px", font_weight="700",
                color=COLORS["text_primary"], letter_spacing="0.5px",
                text_transform="uppercase"),
        rx.vstack(
            *[_footer_link(label, href, ext) for label, href, ext in links],
            spacing="2",
            align="start",
        ),
        spacing="3",
        align="start",
    )


def footer() -> rx.Component:
    return rx.box(
        # ── Top section ───────────────────────────────────────────────────
        rx.box(
            rx.hstack(
                # Brand column
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            rx.icon("file_code_2", size=15, color="white"),
                            background="linear-gradient(135deg, #58a6ff, #bc8cff)",
                            border_radius="7px",
                            width="30px",
                            height="30px",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            box_shadow="0 2px 6px rgba(88,166,255,0.3)",
                        ),
                        rx.vstack(
                            rx.text("AI Code Reviewer", font_size="14px",
                                    font_weight="700", color=COLORS["text_primary"],
                                    line_height="1"),
                            rx.text("Powered by Ollama", font_size="10px",
                                    color=COLORS["text_muted"], line_height="1"),
                            spacing="0",
                            align="start",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(
                        "An intelligent, AI-powered code review platform\n"
                        "for students, developers, and educators.",
                        font_size="13px",
                        color=COLORS["text_muted"],
                        line_height="1.7",
                        max_width="240px",
                        white_space="pre-line",
                    ),
                    # Social icons
                    rx.hstack(
                        rx.link(
                            rx.icon_button(
                                rx.icon("github", size=15),
                                variant="ghost",
                                size="1",
                                color=COLORS["text_muted"],
                                _hover={"color": COLORS["text_primary"],
                                        "background": COLORS["bg_tertiary"]},
                            ),
                            href="https://github.com/saanvi-sahoo",
                            is_external=True,
                        ),
                        spacing="1",
                    ),
                    spacing="4",
                    align="start",
                    flex_shrink="0",
                ),

                rx.spacer(),

                # Navigation links columns
                rx.hstack(
                    _footer_column("Navigate", [
                        ("Home",          "/",        False),
                        ("Review Code",   "/analyze", False),
                        ("History",       "/history", False),
                        ("About",         "/about",   False),
                        ("Settings",      "/settings",False),
                    ]),
                    _footer_column("Analysis", [
                        ("Bug Detection",   "/analyze", False),
                        ("Style (PEP 8)",   "/analyze", False),
                        ("Security Scan",   "/analyze", False),
                        ("Complexity",      "/analyze", False),
                        ("Control Flow",    "/analyze", False),
                    ]),
                    _footer_column("Resources", [
                        ("Reflex Docs",      "https://reflex.dev/docs", True),
                        ("Python AST",       "https://docs.python.org/3/library/ast.html", True),
                        ("Pylint",           "https://pylint.readthedocs.io", True),
                        ("Bandit",           "https://bandit.readthedocs.io", True),
                        ("Ollama",           "https://ollama.ai", True),
                    ]),
                    spacing="9",
                    align="start",
                    display=rx.breakpoints({"0px": "none", "768px": "flex"}),
                ),

                align="start",
                width="100%",
                max_width="1200px",
                margin="0 auto",
                padding_x="48px",
                padding_y="48px",
            ),
            border_top=f"1px solid {COLORS['border']}",
            background=COLORS["bg_secondary"],
            width="100%",
        ),

        # ── Bottom bar ────────────────────────────────────────────────────
        rx.box(
            rx.hstack(
                rx.hstack(
                    rx.text("©", color=COLORS["text_muted"], font_size="13px"),
                    rx.text("2026 AI Code Reviewer — Built with",
                            font_size="13px", color=COLORS["text_muted"]),
                    rx.link(
                        rx.hstack(
                            rx.icon("zap", size=12, color="#bc8cff"),
                            rx.text("Reflex", font_size="13px",
                                    color=COLORS["text_secondary"],
                                    font_weight="500"),
                            spacing="1",
                            align="center",
                        ),
                        href="https://reflex.dev",
                        is_external=True,
                        text_decoration="none",
                        _hover={"opacity": "0.8"},
                    ),
                    rx.text("·", color=COLORS["text_muted"], font_size="13px"),
                    rx.link(
                        rx.hstack(
                            rx.icon("cpu", size=12, color="#58a6ff"),
                            rx.text("Ollama", font_size="13px",
                                    color=COLORS["text_secondary"],
                                    font_weight="500"),
                            spacing="1",
                            align="center",
                        ),
                        href="https://ollama.ai",
                        is_external=True,
                        text_decoration="none",
                        _hover={"opacity": "0.8"},
                    ),
                    spacing="2",
                    align="center",
                    wrap="wrap",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.box(
                        width="6px", height="6px",
                        background=COLORS["accent_green"],
                        border_radius="50%",
                        animation="pulse 2s infinite",
                    ),
                    rx.text("All analysis runs locally — your code never leaves your machine.",
                            font_size="12px", color=COLORS["text_muted"]),
                    spacing="2",
                    align="center",
                    display=rx.breakpoints({"0px": "none", "768px": "flex"}),
                ),
                align="center",
                width="100%",
                max_width="1200px",
                margin="0 auto",
                padding_x="48px",
            ),
            padding_y="16px",
            border_top=f"1px solid {COLORS['border']}",
            background=COLORS["bg_primary"],
            width="100%",
        ),

        width="100%",
    )
