"""Settings page — API key config, theme, default language."""

import reflex as rx
from codementor.state import State
from codementor.components.navbar import navbar, notification_toast
from codementor.components.theme import COLORS


def settings_section(title: str, icon_name: str, *children) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.icon(icon_name, size=16, color=COLORS["accent_blue"]),
            rx.text(title, font_size="14px", font_weight="600",
                    color=COLORS["text_primary"]),
            spacing="2",
            align="center",
            margin_bottom="16px",
        ),
        *children,
        background=COLORS["bg_secondary"],
        border=f"1px solid {COLORS['border']}",
        border_radius="8px",
        padding="20px",
        width="100%",
        margin_bottom="16px",
    )


def settings() -> rx.Component:
    return rx.box(
        navbar(),
        notification_toast(),
        rx.box(
            rx.vstack(
                rx.vstack(
                    rx.heading("Settings",
                               size="7", color=COLORS["text_primary"],
                               font_weight="700"),
                    rx.text("Configure AI Code Reviewer for your setup.",
                            font_size="14px", color=COLORS["text_secondary"]),
                    spacing="1",
                    margin_bottom="32px",
                ),

                rx.separator(color=COLORS["border"], width="100%",
                             margin_bottom="24px"),

                # Ollama (primary AI) section
                settings_section(
                    "Local AI — Ollama (Recommended)", "cpu",
                    rx.vstack(
                        rx.hstack(
                            rx.vstack(
                                rx.text("Free · Unlimited · Private · No API key needed",
                                        font_size="13px", font_weight="500",
                                        color=COLORS["text_secondary"]),
                                rx.text(
                                    "Run powerful coding LLMs directly on your machine. "
                                    "The app auto-detects Ollama — just start it and it works.",
                                    font_size="12px", color=COLORS["text_muted"],
                                    line_height="1.5",
                                ),
                                spacing="1", align="start", flex="1",
                            ),
                            rx.badge(
                                rx.hstack(
                                    rx.icon("circle", size=8),
                                    rx.text(State.ollama_status_label),
                                    spacing="1",
                                ),
                                color_scheme=State.ollama_status_color,
                                variant="soft",
                            ),
                            align="start", width="100%",
                        ),
                        # Model selector
                        rx.hstack(
                            rx.vstack(
                                rx.text("Model", font_size="12px",
                                        color=COLORS["text_muted"]),
                                rx.input(
                                    placeholder="qwen2.5-coder:7b",
                                    value=State.ollama_model_input,
                                    on_change=State.set_ollama_model_input,
                                    size="2",
                                    flex="1",
                                    background=COLORS["bg_tertiary"],
                                    border_color=COLORS["border"],
                                    color=COLORS["text_primary"],
                                    _focus={"border_color": COLORS["accent_blue"]},
                                ),
                                spacing="1", flex="1",
                            ),
                            rx.button(
                                rx.icon("save", size=14),
                                "Use Model",
                                on_click=State.save_ollama_model,
                                color_scheme="green",
                                variant="solid",
                                size="2",
                                align_self="flex-end",
                            ),
                            spacing="2", align="end", width="100%",
                        ),
                        # Quick-start instructions
                        rx.box(
                            rx.vstack(
                                rx.text("Quick start:", font_size="12px",
                                        font_weight="600",
                                        color=COLORS["text_secondary"]),
                                rx.code("1. brew install ollama  (or download from ollama.com)",
                                        font_size="11px", font_family="monospace",
                                        color=COLORS["accent_green"],
                                        background="transparent"),
                                rx.code("2. ollama serve",
                                        font_size="11px", font_family="monospace",
                                        color=COLORS["accent_green"],
                                        background="transparent"),
                                rx.code("3. ollama pull qwen2.5-coder:7b",
                                        font_size="11px", font_family="monospace",
                                        color=COLORS["accent_green"],
                                        background="transparent"),
                                rx.text("Reload the page — AI works automatically!",
                                        font_size="11px",
                                        color=COLORS["text_muted"]),
                                spacing="1", align="start",
                            ),
                            background=COLORS["bg_primary"],
                            border=f"1px solid {COLORS['border']}",
                            border_radius="6px",
                            padding="10px 14px",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.badge("qwen2.5-coder:7b", color_scheme="green",
                                     variant="soft", font_size="10px"),
                            rx.badge("deepseek-coder:6.7b", color_scheme="blue",
                                     variant="soft", font_size="10px"),
                            rx.badge("codellama:7b", color_scheme="purple",
                                     variant="soft", font_size="10px"),
                            rx.text("← Recommended models",
                                    font_size="11px", color=COLORS["text_muted"]),
                            spacing="2", align="center",
                        ),
                        spacing="3", width="100%",
                    ),
                ),

                # OpenAI fallback section
                settings_section(
                    "OpenAI Fallback (Cloud)", "key",
                    rx.vstack(
                        rx.text(
                            "Used when Ollama is not running. Requires credits.",
                            font_size="12px", color=COLORS["text_muted"],
                        ),
                        rx.hstack(
                            rx.input(
                                placeholder="sk-proj-...",
                                value=State.gemini_api_key_input,
                                on_change=State.set_gemini_api_key_input,
                                type="password",
                                size="2",
                                flex="1",
                                background=COLORS["bg_tertiary"],
                                border_color=COLORS["border"],
                                color=COLORS["text_primary"],
                                placeholder_color=COLORS["text_muted"],
                                _focus={"border_color": COLORS["accent_blue"]},
                            ),
                            rx.button(
                                rx.icon("save", size=14),
                                "Save Key",
                                on_click=State.save_api_key,
                                color_scheme="blue",
                                variant="solid",
                                size="2",
                            ),
                            spacing="2", align="center", width="100%",
                        ),
                        rx.cond(
                            State.api_key_saved,
                            rx.hstack(
                                rx.icon("circle_check", size=13,
                                        color=COLORS["accent_green"]),
                                rx.text("OpenAI key saved for this session.",
                                        font_size="12px",
                                        color=COLORS["accent_green"]),
                                spacing="1",
                            ),
                            rx.hstack(
                                rx.icon("external_link", size=12,
                                        color=COLORS["accent_blue"]),
                                rx.link(
                                    "Get an OpenAI API key →",
                                    href="https://platform.openai.com/api-keys",
                                    is_external=True,
                                    font_size="12px",
                                    color=COLORS["accent_blue"],
                                    text_decoration="none",
                                    _hover={"text_decoration": "underline"},
                                ),
                                spacing="1",
                            ),
                        ),
                        spacing="3", width="100%",
                    ),
                ),

                # GitHub integration section
                settings_section(
                    "GitHub Integration", "github",
                    rx.vstack(
                        rx.text(
                            "GitHub Personal Access Token",
                            font_size="13px",
                            font_weight="500",
                            color=COLORS["text_secondary"],
                        ),
                        rx.text(
                            "Optional but recommended. Without a token you are "
                            "limited to 60 API requests/hour. With a token: 5,000/hour. "
                            "Enables access to private repositories.",
                            font_size="12px",
                            color=COLORS["text_muted"],
                            line_height="1.5",
                        ),
                        rx.hstack(
                            rx.input(
                                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
                                value=State.github_token_input,
                                on_change=State.set_github_token_input,
                                type="password",
                                size="2",
                                flex="1",
                                background=COLORS["bg_tertiary"],
                                border_color=COLORS["border"],
                                color=COLORS["text_primary"],
                                _focus={"border_color": "#30363d"},
                            ),
                            rx.button(
                                rx.icon("save", size=14),
                                "Save Token",
                                on_click=State.save_github_token,
                                color_scheme="gray",
                                variant="solid",
                                size="2",
                            ),
                            spacing="2",
                            align="center",
                            width="100%",
                        ),
                        rx.cond(
                            State.github_token_saved,
                            rx.hstack(
                                rx.icon("circle_check", size=13,
                                        color=COLORS["accent_green"]),
                                rx.text("GitHub token saved (5,000 req/hr enabled).",
                                        font_size="12px",
                                        color=COLORS["accent_green"]),
                                spacing="1",
                            ),
                            rx.hstack(
                                rx.icon("external_link", size=12,
                                        color=COLORS["accent_blue"]),
                                rx.link(
                                    "Create a GitHub token (Settings → Developer Settings → PAT) →",
                                    href="https://github.com/settings/tokens/new",
                                    is_external=True,
                                    font_size="12px",
                                    color=COLORS["accent_blue"],
                                    text_decoration="none",
                                    _hover={"text_decoration": "underline"},
                                ),
                                spacing="1",
                            ),
                        ),
                        rx.hstack(
                            rx.icon("info", size=12, color=COLORS["text_muted"]),
                            rx.text(
                                "Required scopes: repo (for private), public_repo (for public only)",
                                font_size="11px",
                                color=COLORS["text_muted"],
                            ),
                            spacing="1",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),

                # Execution section
                settings_section(
                    "Code Execution", "terminal",
                    rx.vstack(
                        rx.hstack(
                            rx.vstack(
                                rx.text("Execution Timeout",
                                        font_size="13px", font_weight="500",
                                        color=COLORS["text_secondary"]),
                                rx.text("Code execution is limited to 10 seconds "
                                        "to prevent infinite loops.",
                                        font_size="12px",
                                        color=COLORS["text_muted"]),
                                spacing="1",
                                align="start",
                                flex="1",
                            ),
                            rx.badge("10 seconds", color_scheme="gray",
                                     variant="soft"),
                            align="center",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.vstack(
                                rx.text("Sandbox Mode",
                                        font_size="13px", font_weight="500",
                                        color=COLORS["text_secondary"]),
                                rx.text("Code runs in an isolated subprocess "
                                        "without network access.",
                                        font_size="12px",
                                        color=COLORS["text_muted"]),
                                spacing="1",
                                align="start",
                                flex="1",
                            ),
                            rx.badge(
                                rx.hstack(
                                    rx.icon("shield", size=11),
                                    rx.text("Always On"),
                                    spacing="1",
                                ),
                                color_scheme="green",
                                variant="soft",
                            ),
                            align="center",
                            width="100%",
                        ),
                        spacing="3",
                    ),
                ),

                # Database section
                settings_section(
                    "Database", "database",
                    rx.vstack(
                        rx.hstack(
                            rx.vstack(
                                rx.text("Storage Backend",
                                        font_size="13px", font_weight="500",
                                        color=COLORS["text_secondary"]),
                                rx.text(
                                    "Set DATABASE_URL environment variable for PostgreSQL (Neon.tech). "
                                    "Defaults to local SQLite for development.",
                                    font_size="12px",
                                    color=COLORS["text_muted"],
                                    line_height="1.5",
                                ),
                                spacing="1",
                                align="start",
                                flex="1",
                            ),
                            rx.badge("SQLite / PostgreSQL", color_scheme="blue",
                                     variant="soft"),
                            align="center",
                            width="100%",
                        ),
                        rx.box(
                            rx.code(
                                "DATABASE_URL=postgresql://user:pass@host/dbname",
                                font_size="12px",
                                font_family="monospace",
                                color=COLORS["text_secondary"],
                                background="transparent",
                            ),
                            background=COLORS["bg_primary"],
                            border=f"1px solid {COLORS['border']}",
                            border_radius="4px",
                            padding="8px 12px",
                            width="100%",
                        ),
                        spacing="3",
                    ),
                ),

                # About section
                settings_section(
                    "About", "info",
                    rx.vstack(
                        rx.hstack(
                            rx.text("Version", font_size="13px",
                                    color=COLORS["text_secondary"]),
                            rx.spacer(),
                            rx.badge("1.0.0", color_scheme="gray", variant="soft"),
                            width="100%",
                        ),
                        rx.hstack(
                            rx.text("Framework", font_size="13px",
                                    color=COLORS["text_secondary"]),
                            rx.spacer(),
                            rx.badge("Reflex (Python)", color_scheme="blue",
                                     variant="soft"),
                            width="100%",
                        ),
                        rx.hstack(
                            rx.text("AI Backend", font_size="13px",
                                    color=COLORS["text_secondary"]),
                            rx.spacer(),
                            rx.badge("Ollama (local) → OpenAI (fallback)",
                                     color_scheme="green", variant="soft"),
                            width="100%",
                        ),
                        rx.hstack(
                            rx.text("Static Analysis", font_size="13px",
                                    color=COLORS["text_secondary"]),
                            rx.spacer(),
                            rx.badge("pyflakes + radon + bandit",
                                     color_scheme="blue", variant="soft"),
                            width="100%",
                        ),
                        spacing="2",
                    ),
                ),

                max_width="640px",
                width="100%",
                margin="0 auto",
            ),
            margin_top="56px",
            padding="32px 48px",
            min_height="calc(100vh - 56px)",
            overflow_y="auto",
        ),
        background=COLORS["bg_primary"],
        min_height="100vh",
        class_name="page-scroll",
        on_mount=State.refresh_ollama_status,
    )
