"""Design tokens and reusable style dictionaries for AI Code Reviewer."""

# ─── Color Palette (GitHub Dark) ─────────────────────────────────────────────
COLORS = {
    "bg_primary":    "#0d1117",
    "bg_secondary":  "#161b22",
    "bg_tertiary":   "#21262d",
    "bg_overlay":    "#30363d",
    "border":        "#30363d",
    "border_light":  "#444c56",
    "text_primary":  "#e6edf3",
    "text_secondary":"#8b949e",
    "text_muted":    "#6e7681",
    "accent_blue":   "#58a6ff",
    "accent_green":  "#3fb950",
    "accent_yellow": "#d29922",
    "accent_red":    "#f85149",
    "accent_purple": "#bc8cff",
    "accent_orange": "#ffa657",
}

# ─── Typography ──────────────────────────────────────────────────────────────
FONT_MONO = "'Fira Code', 'Consolas', 'Monaco', 'Courier New', monospace"
FONT_SANS = "'Inter', 'Segoe UI', system-ui, sans-serif"

# ─── Shared style dicts ──────────────────────────────────────────────────────
NAVBAR_STYLE = {
    "background": COLORS["bg_secondary"],
    "border_bottom": f"1px solid {COLORS['border']}",
    "height": "56px",
    "position": "fixed",
    "top": "0",
    "width": "100%",
    "z_index": "200",
    "display": "flex",
    "align_items": "center",
    "padding": "0 24px",
}

PANEL_STYLE = {
    "background": COLORS["bg_secondary"],
    "border": f"1px solid {COLORS['border']}",
    "border_radius": "6px",
}

SIDEBAR_STYLE = {
    "background": COLORS["bg_secondary"],
    "border_right": f"1px solid {COLORS['border']}",
    "width": "240px",
    "min_width": "240px",
    "height": "100%",
    "overflow_y": "auto",
}

CODE_EDITOR_STYLE = {
    "background": COLORS["bg_primary"],
    "color": COLORS["text_primary"],
    "font_family": FONT_MONO,
    "font_size": "14px",
    "line_height": "1.6",
    "width": "100%",
    "height": "100%",
    "border": "none",
    "outline": "none",
    "resize": "none",
    "padding": "16px",
    "tab_size": "4",
    "white_space": "pre",
    "overflow_wrap": "normal",
    "overflow_x": "auto",
    "overflow_y": "auto",
}

TERMINAL_STYLE = {
    "background": COLORS["bg_primary"],
    "color": "#3fb950",
    "font_family": FONT_MONO,
    "font_size": "13px",
    "line_height": "1.5",
    "padding": "12px 16px",
    "width": "100%",
    "height": "100%",
    "overflow_y": "auto",
    "white_space": "pre-wrap",
    "word_break": "break-word",
}

CHAT_BUBBLE_USER = {
    "background": "#1f3a6e",
    "border": "1px solid #1f6feb",
    "border_radius": "12px 12px 2px 12px",
    "padding": "10px 14px",
}

CHAT_BUBBLE_AI = {
    "background": COLORS["bg_tertiary"],
    "border": f"1px solid {COLORS['border']}",
    "border_radius": "12px 12px 12px 2px",
    "padding": "10px 14px",
}

SEVERITY_COLORS = {
    "error":   COLORS["accent_red"],
    "warning": COLORS["accent_yellow"],
    "info":    COLORS["accent_blue"],
    "style":   COLORS["accent_purple"],
}

SCORE_COLOR = {
    "high":   COLORS["accent_green"],    # 80-100
    "medium": COLORS["accent_yellow"],   # 50-79
    "low":    COLORS["accent_red"],      # 0-49
}


def score_to_color(score: int) -> str:
    if score >= 80:
        return SCORE_COLOR["high"]
    elif score >= 50:
        return SCORE_COLOR["medium"]
    return SCORE_COLOR["low"]
