"""Hero section component for the AI Code Reviewer landing page."""

import reflex as rx
from codementor.components.theme import COLORS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _stat_item(value: str, label: str) -> rx.Component:
    return rx.vstack(
        rx.text(value, font_size="24px", font_weight="800",
                color=COLORS["text_primary"], line_height="1"),
        rx.text(label, font_size="11px", font_weight="500",
                color=COLORS["text_muted"], text_align="center"),
        spacing="1",
        align="center",
    )


def _badge_dot(color: str) -> rx.Component:
    return rx.box(
        width="7px", height="7px",
        background=color,
        border_radius="50%",
        animation="pulse 2s infinite",
    )


def _feature_pill(icon: str, label: str, color: str) -> rx.Component:
    return rx.hstack(
        rx.icon(icon, size=13, color=color),
        rx.text(label, font_size="12px", font_weight="500",
                color=COLORS["text_secondary"]),
        spacing="2",
        align="center",
        background=COLORS["bg_tertiary"],
        border=f"1px solid {COLORS['border']}",
        border_radius="20px",
        padding="5px 12px",
    )


# ── Mock code window (right side of hero) ────────────────────────────────────

_SAMPLE_CODE = """\
def calculate_avg(nums):
  total = 0           # ⚠ Bad indent
  for i in range(len(nums)):   # ⚠ Inefficient
    total = total + nums[i]
  return total / len(nums)

import os   # ⚠ Unused import
result = calculate_avg([10,20,30])
print(result)"""

_ANALYSIS_RESULTS = [
    ("circle_x",  "#f85149", "E302 — Missing blank lines (line 1)"),
    ("triangle_alert", "#d29922", "W0611 — Unused import 'os' (line 7)"),
    ("shield_alert",   "#d29922", "C0301 — Line too long (line 3)"),
    ("bot",        "#bc8cff", "AI: Use sum(nums)/len(nums) instead"),
]


def _code_window() -> rx.Component:
    return rx.box(
        # Window chrome
        rx.hstack(
            rx.hstack(
                rx.box(width="12px", height="12px", border_radius="50%",
                       background="#f85149"),
                rx.box(width="12px", height="12px", border_radius="50%",
                       background="#d29922"),
                rx.box(width="12px", height="12px", border_radius="50%",
                       background="#3fb950"),
                spacing="1",
            ),
            rx.spacer(),
            rx.text("example.py", font_size="11px",
                    color=COLORS["text_muted"], font_family="monospace"),
            align="center",
            padding="10px 14px",
            background=COLORS["bg_tertiary"],
            border_bottom=f"1px solid {COLORS['border']}",
            border_radius="10px 10px 0 0",
        ),
        # Code body
        rx.box(
            rx.code(
                _SAMPLE_CODE,
                display="block",
                white_space="pre",
                font_size="12px",
                font_family="'Fira Code', monospace",
                color=COLORS["text_primary"],
                line_height="1.7",
                padding="14px 16px",
                background=COLORS["bg_primary"],
                overflow_x="auto",
            ),
        ),
        # Analysis results panel
        rx.box(
            rx.text("Analysis Results", font_size="11px", font_weight="600",
                    color=COLORS["text_muted"], margin_bottom="8px"),
            rx.vstack(
                *[
                    rx.hstack(
                        rx.icon(icon, size=12, color=color),
                        rx.text(msg, font_size="11px", color=COLORS["text_secondary"],
                                line_height="1.4"),
                        spacing="2",
                        align="start",
                    )
                    for icon, color, msg in _ANALYSIS_RESULTS
                ],
                spacing="2",
                align="start",
            ),
            padding="12px 14px",
            background=COLORS["bg_secondary"],
            border_top=f"1px solid {COLORS['border']}",
            border_radius="0 0 10px 10px",
        ),
        border=f"1px solid {COLORS['border']}",
        border_radius="10px",
        box_shadow="0 24px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(88,166,255,0.08)",
        width="100%",
        max_width="480px",
        overflow="hidden",
    )


# ── Main Hero component ───────────────────────────────────────────────────────

def hero() -> rx.Component:
    return rx.box(
        rx.box(
            # ── Left column — text ────────────────────────────────────────
            rx.vstack(
                # Status badge
                rx.hstack(
                    _badge_dot("#3fb950"),
                    rx.text("Powered by Ollama · qwen2.5-coder:7b · 100% Private",
                            font_size="12px", font_weight="500",
                            color=COLORS["text_secondary"]),
                    spacing="2",
                    align="center",
                    background="rgba(63,185,80,0.08)",
                    border="1px solid rgba(63,185,80,0.25)",
                    border_radius="20px",
                    padding="5px 14px",
                    width="fit-content",
                ),

                # Headline
                rx.vstack(
                    rx.heading(
                        "Review Your Code",
                        size="9",
                        color=COLORS["text_primary"],
                        font_weight="800",
                        line_height="1.05",
                        letter_spacing="-1px",
                    ),
                    rx.heading(
                        "with AI",
                        size="9",
                        background="linear-gradient(135deg, #58a6ff 0%, #bc8cff 100%)",
                        background_clip="text",
                        webkit_background_clip="text",
                        color="transparent",
                        font_weight="800",
                        line_height="1.05",
                        letter_spacing="-1px",
                    ),
                    spacing="0",
                    align="start",
                ),

                # Description
                rx.text(
                    "Paste your Python code and get instant bug detection, "
                    "PEP 8 style analysis, security scanning, complexity reports, "
                    "and AI-powered optimization — all running privately on your machine.",
                    font_size="16px",
                    color=COLORS["text_secondary"],
                    line_height="1.75",
                    max_width="480px",
                ),

                # Feature pills
                rx.hstack(
                    _feature_pill("bug",           "Bug Detection",   "#f85149"),
                    _feature_pill("shield_check",  "Security Scan",   "#d29922"),
                    _feature_pill("bot",           "AI Chat",         "#bc8cff"),
                    wrap="wrap",
                    spacing="2",
                ),
                rx.hstack(
                    _feature_pill("bar_chart_2",   "Complexity",      "#3fb950"),
                    _feature_pill("git_branch",    "Control Flow",    "#58a6ff"),
                    _feature_pill("github",        "GitHub Import",   "#8b949e"),
                    wrap="wrap",
                    spacing="2",
                ),

                # CTA Buttons
                rx.hstack(
                    rx.link(
                        rx.button(
                            rx.icon("play", size=16),
                            "Start Reviewing",
                            size="3",
                            color_scheme="blue",
                            variant="solid",
                            font_size="15px",
                            font_weight="600",
                            height="46px",
                            padding="0 28px",
                            border_radius="8px",
                            _hover={
                                "opacity": "0.9",
                                "transform": "translateY(-1px)",
                                "box_shadow": "0 8px 24px rgba(88,166,255,0.35)",
                            },
                            transition="all 0.2s ease",
                        ),
                        href="/analyze",
                    ),
                    rx.link(
                        rx.button(
                            rx.icon("eye", size=16),
                            "Try Demo",
                            size="3",
                            variant="outline",
                            color=COLORS["text_secondary"],
                            border_color=COLORS["border"],
                            font_size="15px",
                            height="46px",
                            padding="0 24px",
                            border_radius="8px",
                            _hover={
                                "border_color": COLORS["accent_blue"],
                                "color": COLORS["accent_blue"],
                                "background": "rgba(88,166,255,0.06)",
                            },
                            transition="all 0.2s ease",
                        ),
                        href="/analyze",
                    ),
                    spacing="3",
                ),

                # Stats row
                rx.hstack(
                    _stat_item("6+",    "Analysis\nModules"),
                    rx.separator(orientation="vertical", height="36px",
                                 color=COLORS["border"]),
                    _stat_item("PEP 8", "Style\nEnforced"),
                    rx.separator(orientation="vertical", height="36px",
                                 color=COLORS["border"]),
                    _stat_item("100%",  "Private\nLocal AI"),
                    rx.separator(orientation="vertical", height="36px",
                                 color=COLORS["border"]),
                    _stat_item("Free",  "Open\nSource"),
                    spacing="5",
                ),

                spacing="6",
                align="start",
                width="100%",
                max_width="520px",
            ),

            # ── Right column — code window ────────────────────────────────
            rx.box(
                _code_window(),
                display=rx.breakpoints({"0px": "none", "768px": "flex"}),
                align_items="center",
                justify_content="flex-end",
                flex="1",
                padding_left="40px",
            ),

            display="flex",
            flex_direction=rx.breakpoints({"0px": "column", "768px": "row"}),
            align_items="center",
            justify_content="space-between",
            gap="48px",
            max_width="1200px",
            margin="0 auto",
            padding_x="48px",
            padding_y="80px",
            width="100%",
        ),

        width="100%",
        background=COLORS["bg_primary"],
        position="relative",
        overflow="hidden",
        # Subtle radial glow behind hero
        _before={
            "content": "''",
            "position": "absolute",
            "top": "-200px",
            "left": "50%",
            "transform": "translateX(-50%)",
            "width": "800px",
            "height": "600px",
            "background": "radial-gradient(ellipse, rgba(88,166,255,0.06) 0%, transparent 70%)",
            "pointer_events": "none",
        },
    )
