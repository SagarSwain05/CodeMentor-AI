"""AI Assistant chat sidebar component."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS, CHAT_BUBBLE_USER, CHAT_BUBBLE_AI


def chat_message(msg: dict) -> rx.Component:
    is_user = msg["role"] == "user"
    return rx.box(
        # ── sender label ─────────────────────────────────────────────────
        rx.hstack(
            rx.cond(
                is_user,
                rx.icon("user", size=12, color=COLORS["accent_blue"]),
                rx.icon("bot", size=12, color=COLORS["accent_purple"]),
            ),
            rx.text(
                rx.cond(is_user, "You", "AI Reviewer"),
                font_size="11px",
                font_weight="600",
                color=rx.cond(
                    is_user, COLORS["accent_blue"], COLORS["accent_purple"]
                ),
            ),
            spacing="1",
            align="center",
            margin_bottom="4px",
        ),
        # ── message body — plain text for user, markdown for AI ───────────
        rx.cond(
            is_user,
            rx.text(
                msg["content"],
                font_size="13px",
                color="#e6edf3",
                line_height="1.6",
                white_space="pre-wrap",
                word_break="break-word",
            ),
            rx.markdown(
                msg["content"],
                font_size="13px",
                color=COLORS["text_primary"],
                line_height="1.6",
                class_name="markdown-content",
            ),
        ),
        # ── bubble wrapper ────────────────────────────────────────────────
        style=rx.cond(is_user, CHAT_BUBBLE_USER, CHAT_BUBBLE_AI),
        margin_left=rx.cond(is_user, "auto", "0"),
        margin_right=rx.cond(is_user, "0", "auto"),
        max_width="88%",
        min_width="0",
        overflow="hidden",
        box_sizing="border-box",
        flex_shrink="0",
    )


def typing_indicator() -> rx.Component:
    return rx.cond(
        State.is_asking_ai,
        rx.hstack(
            rx.icon("bot", size=14, color=COLORS["accent_purple"]),
            rx.hstack(
                *[
                    rx.box(
                        width="6px", height="6px",
                        background=COLORS["accent_purple"],
                        border_radius="50%",
                        animation=f"bounce 1s infinite {delay}",
                    )
                    for delay in ["0s", "0.2s", "0.4s"]
                ],
                spacing="1",
                align="center",
            ),
            rx.text("Thinking...", font_size="12px",
                    color=COLORS["text_muted"], font_style="italic"),
            spacing="2",
            align="center",
            padding="8px 12px",
        ),
        rx.box(),
    )


def quick_prompts() -> rx.Component:
    prompts = [
        ("Explain this", "📖"),
        ("Find bugs", "🐛"),
        ("Optimize", "⚡"),
        ("Add docs", "📝"),
    ]
    return rx.hstack(
        *[
            rx.button(
                rx.hstack(
                    rx.text(emoji, font_size="11px"),
                    rx.text(label, font_size="11px"),
                    spacing="1",
                ),
                on_click=State.set_chat_input(label),
                size="1",
                variant="outline",
                color=COLORS["text_secondary"],
                border_color=COLORS["border"],
                _hover={
                    "border_color": COLORS["accent_purple"],
                    "color": COLORS["accent_purple"],
                    "background": "rgba(188,140,255,0.08)",
                },
            )
            for label, emoji in prompts
        ],
        wrap="wrap",
        spacing="1",
        padding="6px 12px",
        width="100%",
    )


def ai_chat_panel() -> rx.Component:
    return rx.cond(
        State.ai_chat_visible,
        rx.box(
            # ── Header ──────────────────────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.icon("bot", size=16, color=COLORS["accent_purple"]),
                    rx.text("AI Assistant", font_size="13px",
                            font_weight="600", color=COLORS["text_primary"]),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("graduation_cap", size=14),
                        on_click=State.toggle_beginner_mode,
                        size="1",
                        variant=rx.cond(State.explain_to_beginner, "solid", "ghost"),
                        color_scheme=rx.cond(
                            State.explain_to_beginner, "purple", "gray"
                        ),
                    ),
                    content=rx.cond(
                        State.explain_to_beginner,
                        "Beginner Mode: ON",
                        "Beginner Mode: OFF",
                    ),
                ),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("trash_2", size=14),
                        on_click=State.clear_chat,
                        size="1",
                        variant="ghost",
                        color=COLORS["text_muted"],
                        _hover={"color": COLORS["accent_red"]},
                    ),
                    content="Clear chat",
                ),
                rx.icon_button(
                    rx.icon("x", size=14),
                    on_click=State.toggle_ai_chat,
                    size="1",
                    variant="ghost",
                    color=COLORS["text_muted"],
                    _hover={"color": COLORS["text_primary"]},
                ),
                spacing="1",
                align="center",
                padding="0 12px",
                height="44px",
                flex_shrink="0",
                border_bottom=f"1px solid {COLORS['border']}",
                width="100%",
            ),

            # ── Beginner mode banner ─────────────────────────────────────
            rx.cond(
                State.explain_to_beginner,
                rx.box(
                    rx.hstack(
                        rx.icon("graduation_cap", size=12,
                                color=COLORS["accent_purple"]),
                        rx.text("Beginner mode ON",
                                font_size="11px", color=COLORS["accent_purple"]),
                        spacing="1",
                    ),
                    background="rgba(188,140,255,0.1)",
                    border_bottom=f"1px solid rgba(188,140,255,0.3)",
                    padding="5px 12px",
                    flex_shrink="0",
                ),
                rx.box(),
            ),

            # ── Messages ─────────────────────────────────────────────────
            # Use raw <div> elements (rx.el.div) — no Radix Box wrapper overhead.
            # Outer: flex:1 fills column space.  Inner: absolute fill → definite
            # pixel size → overflow-y:scroll always activates (ChatGPT-style).
            rx.el.div(
                rx.el.div(
                    rx.cond(
                        State.chat_messages.length() == 0,
                        rx.vstack(
                            rx.icon("bot", size=32,
                                    color=COLORS["accent_purple"],
                                    opacity="0.4"),
                            rx.text("Ask me anything about your code!",
                                    font_size="13px",
                                    color=COLORS["text_secondary"],
                                    text_align="center"),
                            rx.text("I can explain, debug, optimize, and teach.",
                                    font_size="12px",
                                    color=COLORS["text_muted"],
                                    text_align="center"),
                            spacing="2",
                            align="center",
                            width="100%",
                            padding_top="32px",
                        ),
                        rx.box(),
                    ),
                    rx.foreach(State.chat_messages, chat_message),
                    typing_indicator(),
                    id="chat-scroll-box",
                    class_name="chat-messages",
                    style={
                        "position": "absolute",
                        "top": "0",
                        "left": "0",
                        "right": "0",
                        "bottom": "0",
                        "overflowY": "scroll",
                        "overflowX": "hidden",
                        "padding": "12px",
                        "boxSizing": "border-box",
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "10px",
                    },
                ),
                style={
                    "position": "relative",
                    "flex": "1",
                    "minHeight": "0",
                    "width": "100%",
                    "overflow": "hidden",
                },
            ),

            # ── Quick prompts ────────────────────────────────────────────
            rx.box(
                quick_prompts(),
                border_top=f"1px solid {COLORS['border']}",
                flex_shrink="0",
            ),

            # ── Input area ───────────────────────────────────────────────
            rx.hstack(
                rx.el.textarea(
                    placeholder="Ask about your code... (Enter to send)",
                    value=State.chat_input,
                    on_change=State.set_chat_input,
                    on_key_down=State.send_chat_on_enter,
                    rows="2",
                    style={
                        "background": COLORS["bg_tertiary"],
                        "color": COLORS["text_primary"],
                        "border": f"1px solid {COLORS['border']}",
                        "border_radius": "6px",
                        "padding": "8px 10px",
                        "font_size": "13px",
                        "resize": "none",
                        "outline": "none",
                        "width": "100%",
                        "font_family": "inherit",
                        "line_height": "1.4",
                        "_focus": {
                            "border_color": COLORS["accent_purple"],
                            "box_shadow": f"0 0 0 2px rgba(188,140,255,0.15)",
                        },
                    },
                ),
                rx.icon_button(
                    rx.icon("send", size=15),
                    on_click=State.send_chat_message,
                    loading=State.is_asking_ai,
                    color_scheme="purple",
                    size="2",
                    variant="solid",
                    flex_shrink="0",
                ),
                spacing="2",
                align="end",
                padding="8px 12px",
                border_top=f"1px solid {COLORS['border']}",
                width="100%",
                flex_shrink="0",
            ),

            # ── Layout: flex column, fills height ────────────────────────
            display="flex",
            flex_direction="column",
            width="320px",
            min_width="280px",
            max_width="380px",
            height="100%",
            background=COLORS["bg_secondary"],
            border_left=f"1px solid {COLORS['border']}",
            overflow="hidden",
            flex_shrink="0",
            class_name="ai-chat-panel",
        ),
        rx.box(),
    )
