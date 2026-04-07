"""History page — grid of saved code snippets."""

import reflex as rx
from codementor.state import State
from codementor.components.navbar import navbar, notification_toast
from codementor.components.theme import COLORS


def score_badge(snippet: dict) -> rx.Component:
    return rx.badge(
        rx.hstack(
            rx.icon("award", size=11),
            rx.text(snippet["style_score"], "/100"),
            spacing="1",
        ),
        color_scheme=snippet["score_color"],
        variant="soft",
        font_size="11px",
    )


def snippet_card(snippet: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            # Card header
            rx.hstack(
                rx.hstack(
                    rx.icon("file_code", size=14, color=COLORS["accent_blue"]),
                    rx.text(
                        snippet["title"],
                        font_size="13px",
                        font_weight="600",
                        color=COLORS["text_primary"],
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                        max_width="160px",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.badge(
                    snippet["language"],
                    color_scheme="blue",
                    variant="soft",
                    font_size="11px",
                ),
                align="center",
                width="100%",
            ),

            # Code preview
            rx.box(
                rx.code(
                    snippet["code"],
                    display="block",
                    white_space="pre",
                    font_size="11px",
                    font_family="monospace",
                    color=COLORS["text_secondary"],
                    overflow="hidden",
                    max_height="80px",
                    text_overflow="ellipsis",
                ),
                background=COLORS["bg_primary"],
                border=f"1px solid {COLORS['border']}",
                border_radius="4px",
                padding="8px",
                width="100%",
                overflow="hidden",
            ),

            # Stats row
            rx.hstack(
                score_badge(snippet),
                rx.cond(
                    snippet["has_errors"],
                    rx.badge(
                        rx.hstack(
                            rx.icon("circle_x", size=11),
                            rx.text(snippet["error_count"], " errors"),
                            spacing="1",
                        ),
                        color_scheme="red",
                        variant="soft",
                        font_size="11px",
                    ),
                    rx.badge(
                        rx.hstack(
                            rx.icon("circle_check", size=11),
                            rx.text("No errors"),
                            spacing="1",
                        ),
                        color_scheme="green",
                        variant="soft",
                        font_size="11px",
                    ),
                ),
                rx.spacer(),
                rx.text(
                    snippet["date_display"],
                    font_size="11px",
                    color=COLORS["text_muted"],
                ),
                spacing="2",
                align="center",
                width="100%",
            ),

            # Action buttons
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.icon("external_link", size=12),
                        "Open in Editor",
                        size="1",
                        color_scheme="blue",
                        variant="soft",
                        on_click=State.load_snippet_into_editor(
                            snippet["code"],
                            snippet["language"],
                            snippet["title"],
                        ),
                        width="100%",
                    ),
                    href="/analyze",
                    width="100%",
                ),
                rx.icon_button(
                    rx.icon("trash_2", size=13),
                    on_click=State.delete_snippet(snippet["id"]),
                    size="1",
                    variant="ghost",
                    color=COLORS["text_muted"],
                    _hover={"color": COLORS["accent_red"],
                            "background": "rgba(248,81,73,0.1)"},
                ),
                spacing="2",
                align="center",
                width="100%",
            ),

            spacing="3",
            width="100%",
        ),
        background=COLORS["bg_secondary"],
        border=f"1px solid {COLORS['border']}",
        border_radius="8px",
        padding="16px",
        _hover={
            "border_color": COLORS["accent_blue"],
            "box_shadow": "0 4px 16px rgba(0,0,0,0.3)",
        },
        transition="all 0.2s ease",
    )


def empty_history() -> rx.Component:
    return rx.vstack(
        rx.icon("clock", size=48, color=COLORS["text_muted"]),
        rx.heading("No saved snippets yet",
                   size="5", color=COLORS["text_secondary"]),
        rx.text("Analyze some code and click 💾 Save Snippet to see it here.",
                font_size="14px", color=COLORS["text_muted"],
                text_align="center", max_width="380px"),
        rx.link(
            rx.button(
                rx.icon("play", size=16),
                "Start Analyzing",
                size="2",
                color_scheme="blue",
                variant="solid",
            ),
            href="/analyze",
        ),
        spacing="4",
        align="center",
        padding_top="80px",
    )


def history() -> rx.Component:
    return rx.box(
        navbar(),
        notification_toast(),
        rx.box(
            rx.vstack(
                # Page header
                rx.hstack(
                    rx.vstack(
                        rx.heading("History",
                                   size="7", color=COLORS["text_primary"],
                                   font_weight="700"),
                        rx.text("Your saved code snippets and past analyses.",
                                font_size="14px", color=COLORS["text_secondary"]),
                        spacing="1",
                        align="start",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon("refresh_cw", size=15),
                        "Refresh",
                        on_click=State.load_history,
                        loading=State.is_loading_history,
                        variant="outline",
                        color=COLORS["text_secondary"],
                        border_color=COLORS["border"],
                        size="2",
                    ),
                    align="center",
                    width="100%",
                    padding_bottom="24px",
                ),

                rx.separator(color=COLORS["border"]),

                # Content
                rx.cond(
                    State.is_loading_history,
                    rx.center(
                        rx.vstack(
                            rx.spinner(size="3", color=COLORS["accent_blue"]),
                            rx.text("Loading history...",
                                    font_size="13px", color=COLORS["text_muted"]),
                            spacing="3",
                        ),
                        padding_top="60px",
                    ),
                    rx.cond(
                        State.history.length() > 0,
                        rx.grid(
                            rx.foreach(State.history, snippet_card),
                            columns="3",
                            spacing="4",
                            width="100%",
                        ),
                        empty_history(),
                    ),
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
        class_name="page-scroll",
        on_mount=State.load_history,
    )
