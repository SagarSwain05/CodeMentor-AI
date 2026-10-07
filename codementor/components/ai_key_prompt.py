"""Inline 'add your API key' box shown wherever AI couldn't answer."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS


def ai_key_prompt(on_save, label: str = "Save key & retry") -> rx.Component:
    """Key input + retry button. The key is kept only for this browser session."""
    return rx.box(
        rx.hstack(
            rx.icon("key_round", size=14, color=COLORS["accent_yellow"]),
            rx.text("Add your own AI key to continue — it stays in your browser session only.",
                    font_size="12px", color=COLORS["text_secondary"]),
            spacing="2", align="center",
        ),
        rx.hstack(
            rx.input(
                placeholder="gsk_…  /  AIza… or AQ.…  /  sk-…",
                value=State.gemini_api_key_input,
                on_change=State.set_gemini_api_key_input,
                type="password", size="1", flex="1",
                background=COLORS["bg_tertiary"], border_color=COLORS["border"],
                color=COLORS["text_primary"],
            ),
            rx.button(rx.icon("refresh_cw", size=12), label, on_click=on_save,
                      size="1", color_scheme="purple", variant="solid"),
            spacing="2", width="100%", margin_top="8px",
        ),
        rx.hstack(
            rx.link("Free Groq key →", href="https://console.groq.com/keys", is_external=True,
                    font_size="11px", color=COLORS["accent_blue"]),
            rx.link("Free Gemini key →", href="https://aistudio.google.com/app/apikey", is_external=True,
                    font_size="11px", color=COLORS["accent_blue"]),
            spacing="3", margin_top="6px",
        ),
        background="rgba(210,153,34,0.08)",
        border="1px solid rgba(210,153,34,0.35)",
        border_radius="6px", padding="10px 12px", margin="8px 0", width="100%",
    )
