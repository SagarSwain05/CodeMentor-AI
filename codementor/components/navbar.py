"""Top navigation bar component."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS, NAVBAR_STYLE


def nav_link(label: str, href: str) -> rx.Component:
    return rx.link(
        label,
        href=href,
        color=COLORS["text_secondary"],
        font_size="14px",
        font_weight="500",
        text_decoration="none",
        padding="6px 12px",
        border_radius="6px",
        _hover={
            "color": COLORS["text_primary"],
            "background": COLORS["bg_tertiary"],
        },
        transition="all 0.15s ease",
    )


def brand_logo() -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.box(
                rx.icon("file_code_2", size=17, color="white"),
                background="linear-gradient(135deg, #58a6ff, #bc8cff)",
                border_radius="8px",
                width="34px",
                height="34px",
                display="flex",
                align_items="center",
                justify_content="center",
                box_shadow="0 2px 8px rgba(88,166,255,0.35)",
            ),
            rx.vstack(
                rx.text("AI Code Reviewer", font_size="15px", font_weight="700",
                        color=COLORS["text_primary"], line_height="1"),
                rx.text("Powered by Ollama", font_size="10px",
                        color=COLORS["text_muted"], line_height="1"),
                spacing="0",
                align="start",
            ),
            spacing="2",
            align="center",
        ),
        href="/",
        text_decoration="none",
        _hover={"opacity": "0.9"},
    )


def notification_toast() -> rx.Component:
    return rx.cond(
        State.notification != "",
        rx.box(
            rx.hstack(
                rx.cond(
                    State.notification_type == "success",
                    rx.icon("circle_check", size=16, color=COLORS["accent_green"]),
                    rx.cond(
                        State.notification_type == "error",
                        rx.icon("circle_x", size=16, color=COLORS["accent_red"]),
                        rx.icon("info", size=16, color=COLORS["accent_blue"]),
                    ),
                ),
                rx.text(State.notification, font_size="13px",
                        color=COLORS["text_primary"]),
                rx.icon_button(
                    rx.icon("x", size=12),
                    on_click=State.clear_notification,
                    size="1",
                    variant="ghost",
                    color=COLORS["text_muted"],
                ),
                spacing="2",
                align="center",
            ),
            position="fixed",
            bottom="24px",
            right="24px",
            background=COLORS["bg_secondary"],
            border=f"1px solid {COLORS['border']}",
            border_radius="8px",
            padding="10px 16px",
            z_index="1000",
            box_shadow="0 8px 24px rgba(0,0,0,0.4)",
            animation="slideInUp 0.3s ease",
        ),
        rx.box(),
    )


def navbar() -> rx.Component:
    return rx.box(
        rx.hstack(
            brand_logo(),
            rx.hstack(
                nav_link("Home", "/"),
                nav_link("Review Code", "/analyze"),
                nav_link("History", "/history"),
                nav_link("About", "/about"),
                spacing="1",
            ),
            rx.spacer(),
            rx.hstack(
                # Start Reviewing CTA button
                rx.link(
                    rx.button(
                        rx.icon("play", size=14),
                        "Start Reviewing",
                        size="2",
                        color_scheme="blue",
                        variant="solid",
                        font_size="13px",
                        font_weight="600",
                        height="34px",
                        padding="0 16px",
                        border_radius="6px",
                        _hover={"opacity": "0.9"},
                    ),
                    href="/analyze",
                    text_decoration="none",
                ),
                rx.link(
                    rx.icon_button(
                        rx.icon("settings", size=16),
                        variant="ghost",
                        color=COLORS["text_secondary"],
                        size="2",
                        _hover={"color": COLORS["text_primary"],
                                "background": COLORS["bg_tertiary"]},
                    ),
                    href="/settings",
                ),
                rx.link(
                    rx.icon_button(
                        rx.icon("github", size=16),
                        variant="ghost",
                        color=COLORS["text_secondary"],
                        size="2",
                        _hover={"color": COLORS["text_primary"],
                                "background": COLORS["bg_tertiary"]},
                    ),
                    href="https://github.com/saanvi-sahoo",
                    is_external=True,
                ),
                spacing="2",
                align="center",
            ),
            width="100%",
            align="center",
            spacing="6",
        ),
        **NAVBAR_STYLE,
    )
