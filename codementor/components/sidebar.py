"""File explorer sidebar component."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS, SIDEBAR_STYLE


def file_item(file: dict) -> rx.Component:
    is_active = file["name"] == State.current_file
    return rx.hstack(
        rx.icon("file_code", size=13, color=COLORS["accent_blue"],
                flex_shrink="0"),
        rx.text(
            file["name"],
            font_size="12px",
            color=rx.cond(is_active, COLORS["text_primary"], COLORS["text_secondary"]),
            font_weight=rx.cond(is_active, "600", "400"),
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
            flex="1",
            min_width="0",
            cursor="pointer",
            on_click=State.select_file(file["name"]),
        ),
        # Delete button — only visible on hover via CSS
        rx.icon_button(
            rx.icon("x", size=11),
            on_click=State.delete_file(file["name"]),
            size="1",
            variant="ghost",
            color=COLORS["text_muted"],
            _hover={"color": COLORS["accent_red"], "background": "rgba(248,81,73,0.12)"},
            flex_shrink="0",
            class_name="file-delete-btn",
        ),
        spacing="1",
        align="center",
        width="100%",
        padding="4px 8px 4px 12px",
        border_radius="4px",
        background=rx.cond(is_active, COLORS["bg_tertiary"], "transparent"),
        _hover={"background": COLORS["bg_tertiary"]},
        class_name="file-row",
        transition="background 0.1s",
    )


def sidebar() -> rx.Component:
    return rx.cond(
        State.sidebar_visible,
        rx.box(
            # ── Header ──────────────────────────────────────────────────
            rx.hstack(
                rx.text("EXPLORER", font_size="11px", font_weight="600",
                        color=COLORS["text_muted"], letter_spacing="0.8px"),
                rx.spacer(),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("file_plus", size=14),
                        on_click=State.new_file,
                        size="1", variant="ghost",
                        color=COLORS["text_secondary"],
                        _hover={"color": COLORS["text_primary"],
                                "background": COLORS["bg_tertiary"]},
                    ),
                    content="New File",
                ),
                # Upload button
                rx.upload.root(
                    rx.tooltip(
                        rx.icon_button(
                            rx.icon("upload", size=14),
                            size="1", variant="ghost",
                            color=COLORS["text_secondary"],
                            _hover={"color": COLORS["text_primary"],
                                    "background": COLORS["bg_tertiary"]},
                        ),
                        content="Upload File",
                    ),
                    accept={
                        "text/x-python": [".py"],
                        "text/javascript": [".js", ".jsx"],
                        "text/typescript": [".ts", ".tsx"],
                        "text/plain": [
                            ".txt", ".java", ".c", ".cpp", ".go",
                            ".rs", ".rb", ".php", ".swift", ".kt",
                            ".cs", ".sh", ".html", ".css", ".sql", ".md",
                        ],
                        "application/json": [".json"],
                    },
                    on_drop=State.handle_upload(
                        rx.upload_files(upload_id="sidebar_upload")
                    ),
                    id="sidebar_upload",
                    max_files=10,
                    border="none",
                    padding="0",
                    background="transparent",
                ),
                align="center",
                width="100%",
                padding="10px 8px 6px 12px",
            ),

            # ── Drop zone hint ───────────────────────────────────────────
            rx.upload.root(
                rx.box(
                    rx.vstack(
                        rx.icon("cloud_upload", size=20,
                                color=COLORS["text_muted"]),
                        rx.text("Drop files here",
                                font_size="11px", color=COLORS["text_muted"],
                                text_align="center"),
                        spacing="1",
                        align="center",
                    ),
                    border=f"1px dashed {COLORS['border']}",
                    border_radius="6px",
                    padding="10px",
                    margin="0 8px 8px 8px",
                    background=COLORS["bg_primary"],
                    cursor="pointer",
                    _hover={"border_color": COLORS["accent_blue"],
                            "background": "rgba(88,166,255,0.04)"},
                    transition="all 0.15s",
                ),
                accept={
                    "text/x-python": [".py"],
                    "text/javascript": [".js", ".jsx"],
                    "text/typescript": [".ts", ".tsx"],
                    "text/plain": [
                        ".txt", ".java", ".c", ".cpp", ".go",
                        ".rs", ".rb", ".php", ".swift", ".kt",
                        ".cs", ".sh", ".html", ".css", ".sql", ".md",
                    ],
                    "application/json": [".json"],
                },
                on_drop=State.handle_upload(
                    rx.upload_files(upload_id="drop_zone_upload")
                ),
                id="drop_zone_upload",
                max_files=10,
                border="none",
                padding="0",
                background="transparent",
                width="100%",
            ),

            rx.separator(color=COLORS["border"]),

            # ── File list ────────────────────────────────────────────────
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(State.files, file_item),
                    spacing="0",
                    width="100%",
                    padding_top="4px",
                ),
                flex="1",
                min_height="0",
            ),

            rx.separator(color=COLORS["border"], margin_y="8px"),

            # ── Code info panel ──────────────────────────────────────────
            rx.box(
                rx.text("CODE INFO", font_size="11px", font_weight="600",
                        color=COLORS["text_muted"], letter_spacing="0.8px",
                        padding="0 12px 6px 12px"),
                rx.vstack(
                    rx.hstack(
                        rx.icon("git_branch", size=12, color=COLORS["text_muted"]),
                        rx.text("Lines:", font_size="12px",
                                color=COLORS["text_muted"]),
                        rx.text(State.code.split("\n").length(),
                                font_size="12px", color=COLORS["text_secondary"]),
                        spacing="1",
                    ),
                    rx.hstack(
                        rx.icon("zap", size=12, color=COLORS["text_muted"]),
                        rx.text("Style:", font_size="12px",
                                color=COLORS["text_muted"]),
                        rx.text(
                            State.style_score,
                            font_size="12px",
                            color=rx.cond(
                                State.style_score >= 80, COLORS["accent_green"],
                                rx.cond(State.style_score >= 50,
                                        COLORS["accent_yellow"],
                                        COLORS["accent_red"]),
                            ),
                            font_weight="600",
                        ),
                        rx.text("/100", font_size="12px", color=COLORS["text_muted"]),
                        spacing="1",
                    ),
                    rx.hstack(
                        rx.icon("circle_alert", size=12, color=COLORS["text_muted"]),
                        rx.text("Issues:", font_size="12px",
                                color=COLORS["text_muted"]),
                        rx.text(
                            State.total_issues,
                            font_size="12px",
                            color=rx.cond(
                                State.total_issues > 0,
                                COLORS["accent_yellow"],
                                COLORS["accent_green"],
                            ),
                            font_weight="600",
                        ),
                        spacing="1",
                    ),
                    spacing="2",
                    padding="4px 12px 10px 12px",
                ),
            ),

            **SIDEBAR_STYLE,
            display="flex",
            flex_direction="column",
        ),
        rx.box(),
    )
