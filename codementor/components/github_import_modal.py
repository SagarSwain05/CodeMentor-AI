"""GitHub import modal — allows importing a single file or scanning a full repo."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS


def _url_example_row(label: str, example: str, color: str) -> rx.Component:
    return rx.hstack(
        rx.badge(label, color_scheme=color, variant="soft", font_size="10px",
                 flex_shrink="0"),
        rx.code(example, font_size="11px", color=COLORS["text_muted"],
                background="transparent", overflow_x="auto"),
        spacing="2",
        align="center",
        width="100%",
    )


def github_import_modal() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # ── Header ────────────────────────────────────────────────
                rx.hstack(
                    rx.hstack(
                        rx.icon("github", size=18, color=COLORS["text_primary"]),
                        rx.heading("Import from GitHub", size="4",
                                   color=COLORS["text_primary"], font_weight="700"),
                        spacing="2",
                        align="center",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.icon_button(
                            rx.icon("x", size=14),
                            on_click=State.close_github_import,
                            size="1",
                            variant="ghost",
                            color=COLORS["text_muted"],
                        ),
                    ),
                    width="100%",
                    align="center",
                ),

                rx.separator(color=COLORS["border"], width="100%"),

                # ── URL input ─────────────────────────────────────────────
                rx.vstack(
                    rx.text("GitHub URL", font_size="13px", font_weight="600",
                            color=COLORS["text_secondary"]),
                    rx.input(
                        placeholder="https://github.com/owner/repo",
                        value=State.github_url_input,
                        on_change=State.set_github_url_input,
                        size="2",
                        width="100%",
                        background=COLORS["bg_tertiary"],
                        border_color=COLORS["border"],
                        color=COLORS["text_primary"],
                        _focus={"border_color": COLORS["accent_blue"]},
                    ),
                    # Supported URL formats
                    rx.box(
                        rx.text("Supported formats:", font_size="11px",
                                color=COLORS["text_muted"], margin_bottom="6px"),
                        _url_example_row(
                            "REPO", "github.com/owner/repo", "blue"
                        ),
                        _url_example_row(
                            "FILE", "github.com/owner/repo/blob/main/app.py", "green"
                        ),
                        _url_example_row(
                            "RAW", "raw.githubusercontent.com/owner/repo/main/app.py", "purple"
                        ),
                        background=COLORS["bg_primary"],
                        border=f"1px solid {COLORS['border']}",
                        border_radius="6px",
                        padding="10px",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                ),

                # ── Error message ─────────────────────────────────────────
                rx.cond(
                    State.github_fetch_error != "",
                    rx.box(
                        rx.hstack(
                            rx.icon("triangle_alert", size=14,
                                    color=COLORS["accent_red"]),
                            rx.text(State.github_fetch_error,
                                    font_size="12px",
                                    color=COLORS["accent_red"],
                                    white_space="pre-wrap"),
                            spacing="2",
                            align="start",
                        ),
                        background="rgba(248,81,73,0.08)",
                        border=f"1px solid rgba(248,81,73,0.3)",
                        border_radius="6px",
                        padding="10px 12px",
                        width="100%",
                    ),
                    rx.box(),
                ),

                # ── Optional GitHub token ─────────────────────────────────
                rx.vstack(
                    rx.button(
                        rx.hstack(
                            rx.icon("key", size=12, color=COLORS["text_muted"]),
                            rx.text(
                                rx.cond(
                                    State.github_token_section_visible,
                                    "▾ GitHub Personal Access Token (optional)",
                                    "▸ GitHub Personal Access Token (optional)",
                                ),
                                font_size="12px",
                                color=COLORS["text_muted"],
                            ),
                            spacing="1",
                            align="center",
                        ),
                        on_click=State.toggle_github_token_section,
                        variant="ghost",
                        size="1",
                        padding="0",
                        height="auto",
                        _hover={"background": "transparent",
                                "color": COLORS["text_secondary"]},
                    ),
                    rx.cond(
                        State.github_token_section_visible,
                        rx.vstack(
                            rx.hstack(
                                rx.input(
                                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
                                    value=State.github_token_input,
                                    on_change=State.set_github_token_input,
                                    type="password",
                                    size="1",
                                    flex="1",
                                    background=COLORS["bg_tertiary"],
                                    border_color=COLORS["border"],
                                    color=COLORS["text_primary"],
                                ),
                                rx.button(
                                    "Save",
                                    on_click=State.save_github_token,
                                    size="1",
                                    variant="outline",
                                    color=COLORS["text_secondary"],
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            rx.cond(
                                State.github_token_saved,
                                rx.hstack(
                                    rx.icon("circle_check", size=12,
                                            color=COLORS["accent_green"]),
                                    rx.text("Token saved (5,000 req/hr)",
                                            font_size="11px",
                                            color=COLORS["accent_green"]),
                                    spacing="1",
                                ),
                                rx.text(
                                    "Without a token: 60 req/hr limit. "
                                    "With token: 5,000 req/hr.",
                                    font_size="11px",
                                    color=COLORS["text_muted"],
                                ),
                            ),
                            spacing="2",
                            width="100%",
                            padding_top="8px",
                        ),
                        rx.box(),
                    ),
                    spacing="0",
                    width="100%",
                    align="start",
                ),

                rx.separator(color=COLORS["border"], width="100%"),

                # ── What happens section ──────────────────────────────────
                rx.vstack(
                    rx.hstack(
                        rx.icon("info", size=12, color=COLORS["accent_blue"]),
                        rx.text("What happens when you import?",
                                font_size="12px", font_weight="600",
                                color=COLORS["text_secondary"]),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.badge("FILE", color_scheme="green",
                                     variant="soft", font_size="10px"),
                            rx.text("Loads the file directly into the code editor.",
                                    font_size="12px", color=COLORS["text_muted"]),
                            spacing="2",
                        ),
                        rx.hstack(
                            rx.badge("REPO", color_scheme="blue",
                                     variant="soft", font_size="10px"),
                            rx.vstack(
                                rx.text(
                                    "Runs AST + lint analysis on every .py file.",
                                    font_size="12px", color=COLORS["text_muted"],
                                ),
                                rx.text(
                                    "Only sends flagged files to Gemini AI — "
                                    "saves API quota.",
                                    font_size="12px", color=COLORS["text_muted"],
                                ),
                                spacing="0",
                                align="start",
                            ),
                            spacing="2",
                            align="start",
                        ),
                        spacing="2",
                    ),
                    spacing="2",
                    width="100%",
                ),

                # ── Action buttons ────────────────────────────────────────
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            on_click=State.close_github_import,
                            variant="outline",
                            color=COLORS["text_secondary"],
                            border_color=COLORS["border"],
                            size="2",
                        ),
                    ),
                    rx.button(
                        rx.icon("github", size=14),
                        "Import",
                        on_click=State.import_from_github,
                        loading=State.github_is_fetching,
                        color_scheme="blue",
                        variant="solid",
                        size="2",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),

                spacing="4",
                width="100%",
                padding="4px",
            ),
            background=COLORS["bg_secondary"],
            border=f"1px solid {COLORS['border']}",
            border_radius="10px",
            max_width="520px",
            width="90vw",
            padding="20px",
        ),
        open=State.github_import_open,
        on_open_change=State.close_github_import,
    )
