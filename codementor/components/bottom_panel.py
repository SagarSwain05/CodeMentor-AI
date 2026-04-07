"""Bottom output panel with 4 tabs: Terminal | Errors | Optimizations | CFG."""

import reflex as rx
from codementor.state import State
from codementor.components.theme import COLORS, TERMINAL_STYLE, SEVERITY_COLORS


# ─── Tab: Terminal ─────────────────────────────────────────────────────────

def terminal_tab() -> rx.Component:
    return rx.box(
        # ── stdin input (multi-line) ─────────────────────────────────────────
        rx.box(
            rx.hstack(
                rx.icon("chevron_right", size=13, color=COLORS["accent_green"],
                        flex_shrink="0"),
                rx.text("stdin", font_size="11px", color=COLORS["text_muted"],
                        flex_shrink="0", font_family="monospace"),
                rx.text("(one value per line)", font_size="10px",
                        color=COLORS["text_muted"], flex_shrink="0"),
                spacing="2",
                align="center",
                padding="4px 12px 2px 12px",
            ),
            rx.el.textarea(
                default_value=State.stdin_input,
                on_blur=State.set_stdin_input,
                placeholder="Alice\n25\nEngineer",
                rows="3",
                style={
                    "background": COLORS["bg_primary"],
                    "border": "none",
                    "border_top": f"1px solid {COLORS['border']}",
                    "outline": "none",
                    "color": COLORS["accent_green"],
                    "font_family": "monospace",
                    "font_size": "12px",
                    "width": "100%",
                    "resize": "vertical",
                    "padding": "6px 12px",
                    "line_height": "1.5",
                    "caret_color": COLORS["accent_green"],
                    "min_height": "52px",
                    "max_height": "100px",
                },
            ),
            border_bottom=f"1px solid {COLORS['border']}",
            background=COLORS["bg_primary"],
            flex_shrink="0",
        ),

        # ── output area ──────────────────────────────────────────────────────
        rx.box(
            rx.cond(
                State.terminal_output != "",
                rx.text(State.terminal_output, style=TERMINAL_STYLE),
                rx.vstack(
                    rx.icon("terminal", size=28, color=COLORS["text_muted"]),
                    rx.text("Output will appear here after running your code.",
                            font_size="13px", color=COLORS["text_muted"]),
                    rx.text("Use the stdin bar above for programs that call input()",
                            font_size="12px", color=COLORS["text_muted"]),
                    spacing="2",
                    align="center",
                    padding_top="20px",
                ),
            ),
            flex="1",
            overflow_y="auto",
            padding="4px",
        ),

        display="flex",
        flex_direction="column",
        height="100%",
        overflow="hidden",
    )


# ─── Tab: Errors & Style ───────────────────────────────────────────────────

def issue_row(issue: dict) -> rx.Component:
    # Use rx.cond for reactive severity comparisons
    severity = issue["severity"]
    is_error = severity == "error"
    is_warning = severity == "warning"
    icon_color = rx.cond(
        is_error, COLORS["accent_red"],
        rx.cond(is_warning, COLORS["accent_yellow"], COLORS["accent_blue"]),
    )
    badge_scheme = rx.cond(
        is_error, "red",
        rx.cond(is_warning, "yellow", "blue"),
    )
    return rx.hstack(
        # Severity icon
        rx.cond(
            is_error,
            rx.icon("circle_x", size=14, color=COLORS["accent_red"], flex_shrink="0"),
            rx.cond(
                is_warning,
                rx.icon("triangle_alert", size=14, color=COLORS["accent_yellow"], flex_shrink="0"),
                rx.icon("info", size=14, color=COLORS["accent_blue"], flex_shrink="0"),
            ),
        ),
        # Line number
        rx.badge(
            rx.text("L", issue["line"]),
            color_scheme="gray",
            variant="soft",
            font_size="11px",
            font_family="monospace",
            flex_shrink="0",
        ),
        # Code badge
        rx.badge(
            issue["code"],
            color_scheme=badge_scheme,
            variant="soft",
            font_size="11px",
            font_family="monospace",
            flex_shrink="0",
        ),
        # Category
        rx.badge(
            issue["category"],
            color_scheme="gray",
            variant="outline",
            font_size="10px",
            flex_shrink="0",
        ),
        # Message
        rx.text(
            issue["message"],
            font_size="13px",
            color=COLORS["text_secondary"],
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
            flex="1",
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="6px 12px",
        border_radius="4px",
        _hover={"background": COLORS["bg_tertiary"]},
    )


def _section_header(label: str, color: str) -> rx.Component:
    return rx.text(
        label,
        font_size="11px", font_weight="600",
        color=color, letter_spacing="0.5px",
        padding="8px 12px 4px 12px",
        text_transform="uppercase",
    )


def errors_tab() -> rx.Component:
    all_issues_count = State.total_issues

    return rx.box(
        rx.cond(
            all_issues_count > 0,
            rx.vstack(
                # ── Summary bar ────────────────────────────────────────────
                rx.hstack(
                    rx.hstack(
                        rx.icon("circle_x", size=13, color=COLORS["accent_red"]),
                        rx.text(State.error_report.length(), font_size="12px",
                                font_weight="600", color=COLORS["accent_red"]),
                        rx.text("errors", font_size="12px",
                                color=COLORS["text_muted"]),
                        spacing="1",
                    ),
                    rx.hstack(
                        rx.icon("triangle_alert", size=13,
                                color=COLORS["accent_yellow"]),
                        rx.text(State.style_report.length(), font_size="12px",
                                font_weight="600", color=COLORS["accent_yellow"]),
                        rx.text("style", font_size="12px",
                                color=COLORS["text_muted"]),
                        spacing="1",
                    ),
                    rx.cond(
                        State.security_report.length() > 0,
                        rx.hstack(
                            rx.icon("shield_alert", size=13,
                                    color="#f85149"),
                            rx.text(State.security_report.length(),
                                    font_size="12px", font_weight="600",
                                    color="#f85149"),
                            rx.text("security", font_size="12px",
                                    color=COLORS["text_muted"]),
                            spacing="1",
                        ),
                        rx.box(),
                    ),
                    rx.cond(
                        State.complexity_report.length() > 0,
                        rx.hstack(
                            rx.icon("activity", size=13,
                                    color=COLORS["accent_purple"]),
                            rx.text(State.complexity_report.length(),
                                    font_size="12px", font_weight="600",
                                    color=COLORS["accent_purple"]),
                            rx.text("complex", font_size="12px",
                                    color=COLORS["text_muted"]),
                            spacing="1",
                        ),
                        rx.box(),
                    ),
                    rx.spacer(),
                    rx.hstack(
                        rx.icon("award", size=13, color=COLORS["accent_green"]),
                        rx.text(
                            f"Style {State.style_score}/100  •  MI {State.maintainability_index}/100",
                            font_size="11px", font_weight="600",
                            color=rx.cond(
                                State.style_score >= 80,
                                COLORS["accent_green"],
                                rx.cond(State.style_score >= 50,
                                        COLORS["accent_yellow"],
                                        COLORS["accent_red"]),
                            ),
                        ),
                        spacing="1",
                    ),
                    spacing="3",
                    padding="6px 12px",
                    border_bottom=f"1px solid {COLORS['border']}",
                    width="100%",
                    align="center",
                    flex_wrap="wrap",
                ),
                # ── Issue lists ────────────────────────────────────────────
                rx.scroll_area(
                    rx.vstack(
                        rx.cond(
                            State.error_report.length() > 0,
                            rx.vstack(
                                _section_header("Errors & Warnings",
                                                COLORS["accent_red"]),
                                rx.foreach(State.error_report, issue_row),
                                spacing="0", width="100%",
                            ),
                            rx.box(),
                        ),
                        rx.cond(
                            State.security_report.length() > 0,
                            rx.vstack(
                                _section_header("Security Issues (Bandit)",
                                                "#f85149"),
                                rx.foreach(State.security_report, issue_row),
                                spacing="0", width="100%",
                            ),
                            rx.box(),
                        ),
                        rx.cond(
                            State.complexity_report.length() > 0,
                            rx.vstack(
                                _section_header("High Complexity (Radon)",
                                                COLORS["accent_purple"]),
                                rx.foreach(State.complexity_report, issue_row),
                                spacing="0", width="100%",
                            ),
                            rx.box(),
                        ),
                        rx.cond(
                            State.style_report.length() > 0,
                            rx.vstack(
                                _section_header("Style Issues (PEP8)",
                                                COLORS["accent_yellow"]),
                                rx.foreach(State.style_report, issue_row),
                                spacing="0", width="100%",
                            ),
                            rx.box(),
                        ),
                        spacing="0", width="100%",
                    ),
                    height="100%",
                ),
                spacing="0", height="100%", width="100%",
            ),
            # ── Empty / loading state ──────────────────────────────────────
            rx.cond(
                State.is_analyzing,
                rx.vstack(
                    rx.spinner(size="3", color=COLORS["accent_blue"]),
                    rx.text("Analyzing code...", font_size="13px",
                            color=COLORS["text_muted"]),
                    spacing="3", align="center", padding_top="24px",
                ),
                rx.vstack(
                    rx.icon("circle_check", size=28,
                            color=COLORS["accent_green"]),
                    rx.text("No issues found!", font_size="14px",
                            font_weight="600", color=COLORS["accent_green"]),
                    rx.text("Click 🔍 Analyze to check your code.",
                            font_size="12px", color=COLORS["text_muted"]),
                    spacing="2", align="center", padding_top="24px",
                ),
            ),
        ),
        height="100%",
        overflow_y="auto",
    )


# ─── Tab: AI Optimizations ────────────────────────────────────────────────

def optimizations_tab() -> rx.Component:
    return rx.box(
        rx.cond(
            State.ai_optimizations != "",
            rx.scroll_area(
                rx.box(
                    rx.markdown(
                        State.ai_optimizations,
                        class_name="markdown-content",
                        color=COLORS["text_secondary"],
                        font_size="13px",
                        line_height="1.6",
                    ),
                    padding="12px 16px",
                ),
                height="100%",
            ),
            rx.cond(
                State.is_analyzing,
                rx.vstack(
                    rx.spinner(size="3", color=COLORS["accent_purple"]),
                    rx.text("Getting AI suggestions...", font_size="13px",
                            color=COLORS["text_muted"]),
                    spacing="3",
                    align="center",
                    padding_top="24px",
                ),
                rx.vstack(
                    rx.icon("bot", size=28, color=COLORS["text_muted"]),
                    rx.text("AI optimization suggestions will appear here.",
                            font_size="13px", color=COLORS["text_muted"]),
                    rx.text("Click 🔍 Analyze to get suggestions.",
                            font_size="12px", color=COLORS["text_muted"]),
                    spacing="2",
                    align="center",
                    padding_top="24px",
                ),
            ),
        ),
        height="100%",
        overflow="hidden",
    )


# ─── Tab: Control Flow Graph ──────────────────────────────────────────────

def cfg_tab() -> rx.Component:
    return rx.box(
        rx.cond(
            State.cfg_image != "",
            rx.vstack(
                rx.hstack(
                    rx.text("Control Flow Graph",
                            font_size="12px", font_weight="600",
                            color=COLORS["text_muted"]),
                    rx.spacer(),
                    rx.link(
                        rx.icon_button(
                            rx.icon("download", size=13),
                            size="1",
                            variant="ghost",
                            color=COLORS["text_muted"],
                        ),
                        href=State.cfg_image,
                        download="cfg.png",
                    ),
                    padding="8px 12px",
                    width="100%",
                    border_bottom=f"1px solid {COLORS['border']}",
                ),
                rx.scroll_area(
                    rx.image(
                        src=State.cfg_image,
                        alt="Control Flow Graph",
                        max_width="100%",
                        border_radius="4px",
                        margin="8px auto",
                        display="block",
                    ),
                    height="100%",
                ),
                spacing="0",
                height="100%",
                width="100%",
            ),
            rx.cond(
                State.is_analyzing,
                rx.vstack(
                    rx.spinner(size="3", color=COLORS["accent_green"]),
                    rx.text("Generating control flow graph...",
                            font_size="13px", color=COLORS["text_muted"]),
                    spacing="3",
                    align="center",
                    padding_top="24px",
                ),
                rx.cond(
                    State.cfg_error != "",
                    rx.vstack(
                        rx.icon("triangle_alert", size=24,
                                color=COLORS["accent_yellow"]),
                        rx.text(State.cfg_error,
                                font_size="12px",
                                color=COLORS["text_muted"],
                                text_align="center",
                                max_width="320px"),
                        spacing="2",
                        align="center",
                        padding_top="24px",
                    ),
                    rx.vstack(
                        rx.icon("git_fork", size=28, color=COLORS["text_muted"]),
                        rx.text("Control Flow Graph will appear here.",
                                font_size="13px", color=COLORS["text_muted"]),
                        rx.text("The CFG visualizes how your code executes.",
                                font_size="12px", color=COLORS["text_muted"]),
                        rx.text("Click 🔍 Analyze to generate the graph.",
                                font_size="12px", color=COLORS["text_muted"]),
                        spacing="2",
                        align="center",
                        padding_top="24px",
                    ),
                ),
            ),
        ),
        height="100%",
        overflow="hidden",
    )


# ─── Tab: Repo Scan ───────────────────────────────────────────────────────

def repo_file_row(item: dict) -> rx.Component:
    return rx.hstack(
        # Status badge
        rx.badge(
            item["status_label"],
            color_scheme=item["status_color"],
            variant="soft",
            font_size="10px",
            flex_shrink="0",
        ),
        # Filename — clicking opens the file
        rx.text(
            item["filename"],
            font_size="12px",
            font_weight="600",
            color=COLORS["text_primary"],
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
            max_width="160px",
            font_family="monospace",
            flex_shrink="0",
        ),
        # Path (muted)
        rx.text(
            item["path"],
            font_size="11px",
            color=COLORS["text_muted"],
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
            flex="1",
        ),
        # Metrics badges
        rx.badge(
            rx.hstack(rx.text("CC:"), rx.text(item["complexity"]), spacing="1"),
            color_scheme=item["complexity_color"],
            variant="soft", font_size="10px", flex_shrink="0",
        ),
        rx.badge(
            rx.hstack(rx.text("E:"), rx.text(item["error_count"]), spacing="1"),
            color_scheme=item["error_color"],
            variant="soft", font_size="10px", flex_shrink="0",
        ),
        rx.badge(
            rx.hstack(rx.text(item["style_score"]), rx.text("/100"), spacing="0"),
            color_scheme=item["score_color"],
            variant="soft", font_size="10px", flex_shrink="0",
        ),
        # Open button
        rx.icon_button(
            rx.icon("external_link", size=12),
            on_click=State.load_repo_file_into_editor(item["path"]),
            size="1",
            variant="ghost",
            color=COLORS["accent_blue"],
            flex_shrink="0",
            title="Open in editor",
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="5px 12px",
        border_radius="4px",
        cursor="pointer",
        on_click=State.load_repo_file_into_editor(item["path"]),
        _hover={"background": COLORS["bg_tertiary"]},
        border_bottom=f"1px solid {COLORS['border']}",
    )


def repo_scan_tab() -> rx.Component:
    return rx.box(
        rx.cond(
            State.is_repo_scanning,
            # ── Scanning in progress ──
            rx.vstack(
                rx.hstack(
                    rx.spinner(size="2", color=COLORS["accent_blue"]),
                    rx.text(State.repo_scan_progress,
                            font_size="12px", color=COLORS["text_secondary"],
                            white_space="pre-wrap"),
                    spacing="3",
                    align="start",
                    padding="12px 16px",
                ),
                width="100%",
            ),
            # ── Results or empty ──
            rx.cond(
                State.repo_scan_results.length() > 0,
                rx.vstack(
                    # Summary bar
                    rx.hstack(
                        rx.icon("github", size=13, color=COLORS["text_muted"]),
                        rx.text(
                            State.repo_name_display,
                            font_size="12px", font_weight="600",
                            color=COLORS["text_secondary"],
                        ),
                        rx.separator(orientation="vertical",
                                     height="12px", color=COLORS["border"]),
                        rx.text(
                            State.repo_scan_results.length(),
                            font_size="12px",
                            color=COLORS["text_muted"],
                        ),
                        rx.text("files", font_size="12px",
                                color=COLORS["text_muted"]),
                        rx.separator(orientation="vertical",
                                     height="12px", color=COLORS["border"]),
                        rx.text(State.repo_scan_progress,
                                font_size="11px", color=COLORS["text_muted"],
                                flex="1", overflow="hidden",
                                text_overflow="ellipsis",
                                white_space="nowrap"),
                        spacing="2",
                        padding="6px 12px",
                        border_bottom=f"1px solid {COLORS['border']}",
                        width="100%",
                        align="center",
                    ),
                    # File table
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(State.repo_scan_results, repo_file_row),
                            spacing="0",
                            width="100%",
                        ),
                        height="120px",
                    ),
                    # Gemini AI section
                    rx.cond(
                        State.repo_scan_gemini_output != "",
                        rx.box(
                            rx.hstack(
                                rx.icon("bot", size=13,
                                        color=COLORS["accent_purple"]),
                                rx.text("AI Analysis of Flagged Files",
                                        font_size="11px", font_weight="600",
                                        color=COLORS["accent_purple"],
                                        letter_spacing="0.3px"),
                                spacing="2",
                                padding="6px 12px",
                                border_top=f"1px solid {COLORS['border']}",
                                border_bottom=f"1px solid {COLORS['border']}",
                            ),
                            rx.scroll_area(
                                rx.box(
                                    rx.markdown(
                                        State.repo_scan_gemini_output,
                                        class_name="markdown-content",
                                        font_size="12px",
                                        color=COLORS["text_secondary"],
                                    ),
                                    padding="8px 16px",
                                ),
                                height="80px",
                            ),
                        ),
                        rx.box(),
                    ),
                    spacing="0",
                    height="100%",
                    width="100%",
                ),
                # Empty state
                rx.vstack(
                    rx.icon("github", size=28, color=COLORS["text_muted"]),
                    rx.text("GitHub Repo Scanner",
                            font_size="13px", font_weight="600",
                            color=COLORS["text_secondary"]),
                    rx.text(
                        "Click the GitHub button in the toolbar, "
                        "paste a repo URL, and click Import.",
                        font_size="12px", color=COLORS["text_muted"],
                        text_align="center", max_width="360px",
                    ),
                    rx.hstack(
                        rx.badge("AST", color_scheme="blue", variant="soft",
                                 font_size="10px"),
                        rx.text("+", font_size="11px",
                                color=COLORS["text_muted"]),
                        rx.badge("Lint", color_scheme="yellow", variant="soft",
                                 font_size="10px"),
                        rx.text("+", font_size="11px",
                                color=COLORS["text_muted"]),
                        rx.badge("Gemini AI", color_scheme="purple",
                                 variant="soft", font_size="10px"),
                        rx.text("on every .py file",
                                font_size="11px", color=COLORS["text_muted"]),
                        spacing="1",
                        align="center",
                    ),
                    spacing="2",
                    align="center",
                    padding_top="20px",
                ),
            ),
        ),
        height="100%",
        overflow="hidden",
    )


# ─── Tab bar ──────────────────────────────────────────────────────────────

def tab_trigger(label: str, tab_id: str, icon_name: str, count_var=None) -> rx.Component:
    is_active = State.active_bottom_tab == tab_id
    return rx.hstack(
        rx.icon(icon_name, size=13),
        rx.text(label, font_size="12px", font_weight="500"),
        rx.cond(
            count_var is not None,
            rx.cond(
                count_var > 0,
                rx.badge(
                    count_var,
                    color_scheme="red",
                    variant="solid",
                    font_size="10px",
                    border_radius="full",
                ),
                rx.box(),
            ),
            rx.box(),
        ) if count_var is not None else rx.box(),
        spacing="1",
        align="center",
        padding="6px 14px",
        cursor="pointer",
        border_bottom=rx.cond(
            is_active,
            f"2px solid {COLORS['accent_blue']}",
            "2px solid transparent",
        ),
        color=rx.cond(is_active, COLORS["text_primary"], COLORS["text_secondary"]),
        background=rx.cond(is_active, COLORS["bg_tertiary"], "transparent"),
        border_radius="4px 4px 0 0",
        on_click=State.set_active_bottom_tab(tab_id),
        _hover={"color": COLORS["text_primary"],
                "background": COLORS["bg_tertiary"]},
        transition="all 0.15s",
    )


def bottom_panel() -> rx.Component:
    return rx.box(
        # ── Drag handle at very top (grab & pull like VS Code) ─────────────────
        rx.box(
            # Grip dots
            rx.box(
                width="36px",
                height="3px",
                border_radius="2px",
                background=COLORS["border"],
            ),
            id="panel-resize-handle",
            width="100%",
            height="8px",
            display="flex",
            align_items="center",
            justify_content="center",
            cursor="row-resize",
            flex_shrink="0",
            background="transparent",
            _hover={"background": "rgba(88,166,255,0.15)"},
            transition="background 0.15s",
        ),

        # ── Tab bar with resize buttons on right ───────────────────────────────
        rx.hstack(
            tab_trigger("Terminal", "terminal", "terminal"),
            tab_trigger("Errors & Style", "errors", "circle_alert",
                        count_var=State.total_issues),
            tab_trigger("AI Optimizations", "optimizations", "bot"),
            tab_trigger("Control Flow", "cfg", "git_fork"),
            tab_trigger("Repo Scan", "repo_scan", "github"),
            rx.spacer(),
            # Resize controls
            rx.hstack(
                rx.icon_button(
                    rx.icon("chevron_up", size=13),
                    on_click=State.expand_panel,
                    size="1",
                    variant="ghost",
                    color=COLORS["text_muted"],
                    _hover={"color": COLORS["text_primary"],
                            "background": COLORS["bg_tertiary"]},
                    title="Expand panel",
                ),
                rx.icon_button(
                    rx.icon("chevron_down", size=13),
                    on_click=State.shrink_panel,
                    size="1",
                    variant="ghost",
                    color=COLORS["text_muted"],
                    _hover={"color": COLORS["text_primary"],
                            "background": COLORS["bg_tertiary"]},
                    title="Shrink panel",
                ),
                rx.icon_button(
                    rx.icon("minus", size=13),
                    on_click=State.reset_panel_height,
                    size="1",
                    variant="ghost",
                    color=COLORS["text_muted"],
                    _hover={"color": COLORS["text_primary"],
                            "background": COLORS["bg_tertiary"]},
                    title="Reset panel height",
                ),
                spacing="0",
                align="center",
                padding_right="8px",
                flex_shrink="0",
            ),
            spacing="0",
            padding="0 0 0 12px",
            background=COLORS["bg_secondary"],
            border_bottom=f"1px solid {COLORS['border']}",
            width="100%",
            overflow_x="auto",
            align="center",
            flex_shrink="0",
        ),
        # ── Tab content ────────────────────────────────────────────────────────
        rx.box(
            rx.match(
                State.active_bottom_tab,
                ("terminal", terminal_tab()),
                ("errors", errors_tab()),
                ("optimizations", optimizations_tab()),
                ("cfg", cfg_tab()),
                ("repo_scan", repo_scan_tab()),
                terminal_tab(),
            ),
            flex="1",
            min_height="0",
            overflow="hidden",
        ),
        id="bottom-panel-container",
        height=State.panel_height_px,
        min_height="80px",
        background=COLORS["bg_secondary"],
        border_top=f"1px solid {COLORS['border']}",
        display="flex",
        flex_direction="column",
        flex_shrink="0",
    )
