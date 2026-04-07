"""Main Analyze page — 3-column IDE layout."""

import reflex as rx
from codementor.state import State
from codementor.components.navbar import navbar, notification_toast
from codementor.components.sidebar import sidebar
from codementor.components.code_editor import code_editor_area
from codementor.components.ai_chat import ai_chat_panel
from codementor.components.bottom_panel import bottom_panel
from codementor.components.github_import_modal import github_import_modal
from codementor.components.theme import COLORS


def analyze() -> rx.Component:
    return rx.box(
        navbar(),
        notification_toast(),
        github_import_modal(),

        # Main workspace (below fixed navbar)
        rx.box(
            # 3-column editor + chat area — fills all space above bottom panel
            rx.box(
                rx.hstack(
                    # Left: File explorer sidebar (collapsible)
                    sidebar(),

                    # Center: Code editor (fills remaining space)
                    code_editor_area(),

                    # Right: AI chat panel (collapsible, fixed width)
                    ai_chat_panel(),

                    spacing="0",
                    width="100%",
                    height="100%",
                    align="stretch",
                    overflow="hidden",
                    class_name="editor-chat-row",
                ),
                flex="1",
                min_height="0",
                overflow="hidden",
            ),

            # Bottom: Output panel (drag-resizable — handle is inside panel)
            bottom_panel(),

            margin_top="56px",
            height="calc(100vh - 56px)",
            display="flex",
            flex_direction="column",
            overflow="hidden",
        ),

        # Resize script — runs client-side only, no server round-trips
        rx.script(src="/resize_panel.js"),
        # Auto-scroll chat to bottom when new messages arrive
        rx.script(src="/chat_scroll.js"),

        background=COLORS["bg_primary"],
        height="100vh",
        overflow="hidden",
        max_width="100vw",
        class_name="page-ide",
    )
