"""Code editor + toolbar component."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS, CODE_EDITOR_STYLE


LANGUAGES = ["python", "javascript", "typescript", "java", "c", "cpp", "go", "rust"]

LANG_ICONS = {
    "python": "🐍",
    "javascript": "🟨",
    "typescript": "🔷",
    "java": "☕",
    "c": "🔵",
    "cpp": "🔷",
    "go": "🐹",
    "rust": "⚙️",
}


def toolbar() -> rx.Component:
    return rx.hstack(
        # Language selector
        rx.select(
            LANGUAGES,
            value=State.language,
            on_change=State.set_language,
            size="1",
            variant="soft",
            color_scheme="gray",
            width="120px",
        ),

        rx.separator(orientation="vertical", height="24px", color=COLORS["border"]),

        # Run Code button
        rx.button(
            rx.icon("play", size=14),
            rx.text("Run", font_size="13px"),
            on_click=State.run_code,
            loading=State.is_running,
            color_scheme="green",
            variant="solid",
            size="1",
            _hover={"opacity": "0.85"},
        ),

        # Analyze button
        rx.button(
            rx.icon("search", size=14),
            rx.text("Analyze", font_size="13px"),
            on_click=State.analyze_code,
            loading=State.is_analyzing,
            color_scheme="blue",
            variant="solid",
            size="1",
            _hover={"opacity": "0.85"},
        ),

        # Ask AI button
        rx.button(
            rx.icon("bot", size=14),
            rx.text("Ask AI", font_size="13px"),
            on_click=State.toggle_ai_chat,
            color_scheme="purple",
            variant=rx.cond(State.ai_chat_visible, "solid", "outline"),
            size="1",
            _hover={"opacity": "0.85"},
        ),

        # GitHub import button
        rx.button(
            rx.icon("github", size=14),
            rx.text("GitHub", font_size="13px"),
            on_click=State.open_github_import,
            color_scheme="gray",
            variant="outline",
            size="1",
            _hover={
                "border_color": COLORS["text_primary"],
                "color": COLORS["text_primary"],
                "background": COLORS["bg_tertiary"],
            },
        ),

        rx.separator(orientation="vertical", height="24px", color=COLORS["border"]),

        # Save Snippet
        rx.tooltip(
            rx.icon_button(
                rx.icon("save", size=14),
                on_click=State.save_snippet,
                size="1",
                variant="ghost",
                color=COLORS["text_secondary"],
                _hover={"color": COLORS["text_primary"],
                        "background": COLORS["bg_tertiary"]},
            ),
            content="Save Snippet",
        ),

        # Clear button
        rx.tooltip(
            rx.icon_button(
                rx.icon("trash_2", size=14),
                on_click=State.clear_editor,
                size="1",
                variant="ghost",
                color=COLORS["text_secondary"],
                _hover={"color": COLORS["accent_red"],
                        "background": COLORS["bg_tertiary"]},
            ),
            content="Clear Editor",
        ),

        # Toggle sidebar
        rx.tooltip(
            rx.icon_button(
                rx.icon("panel_left", size=14),
                on_click=State.toggle_sidebar,
                size="1",
                variant="ghost",
                color=COLORS["text_secondary"],
                _hover={"color": COLORS["text_primary"],
                        "background": COLORS["bg_tertiary"]},
            ),
            content="Toggle Sidebar",
        ),

        rx.spacer(),

        # File name badge
        rx.badge(
            State.current_file,
            color_scheme="gray",
            variant="soft",
            font_size="12px",
            font_family="monospace",
        ),

        # Style score badge
        rx.cond(
            State.style_score > 0,
            rx.badge(
                rx.hstack(
                    rx.icon("award", size=12),
                    rx.text(f"Style: {State.style_score}/100"),
                    spacing="1",
                ),
                color_scheme=rx.cond(
                    State.style_score >= 80, "green",
                    rx.cond(State.style_score >= 50, "yellow", "red")
                ),
                variant="soft",
                font_size="12px",
            ),
            rx.box(),
        ),

        spacing="2",
        align="center",
        width="100%",
        padding="8px 16px",
        background=COLORS["bg_secondary"],
        border_bottom=f"1px solid {COLORS['border']}",
        height="48px",
    )


def line_numbers(code: str) -> rx.Component:
    """Generate line number column. Uses JS trick via CSS counter."""
    return rx.box(
        background=COLORS["bg_secondary"],
        border_right=f"1px solid {COLORS['border']}",
        width="48px",
        min_width="48px",
        padding="16px 8px",
        height="100%",
        overflow="hidden",
        display="flex",
        flex_direction="column",
    )


def code_editor_area() -> rx.Component:
    return rx.box(
        toolbar(),
        rx.hstack(
            # Uncontrolled textarea — using default_value + key avoids cursor-jump.
            # key=current_file remounts the element on file switch so new content loads.
            # on_blur syncs content to state when user moves focus away.
            rx.el.textarea(
                default_value=State.code,
                key=State.current_file,
                on_blur=State.set_code,
                placeholder="# Paste or type your code here...\n# Click ▶ Run to execute  |  🔍 Analyze to review",
                spell_check=False,
                auto_complete="off",
                auto_correct="off",
                auto_capitalize="off",
                style=CODE_EDITOR_STYLE,
            ),
            spacing="0",
            width="100%",
            height="100%",
            align="stretch",
        ),
        display="flex",
        flex_direction="column",
        flex="1",
        height="100%",
        min_width="0",
        overflow="hidden",
    )
