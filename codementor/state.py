"""
Single unified application state for CodeMentor AI.

Design notes
  • Long-running work (analysis, repo scans, AI chat, code execution) runs as
    Reflex *background* events, so the UI stays interactive while they run.
  • File contents live in a backend-only store (`_file_store`), not in the
    state that is synced to the browser — repo scans no longer ship megabytes
    of source to the client.
  • API keys entered in Settings are kept per session (`_session_keys`) and
    never written to os.environ, so one visitor's key is never used for others.
"""

import asyncio
import os
import time

import reflex as rx
from dotenv import load_dotenv

from codementor.services import languages as lang_registry

load_dotenv()


SAMPLE_CODE = '''# Welcome to CodeMentor AI!
# Paste code in ANY language and click Analyze 🔍

def calculate_average(numbers):
    total = 0
    for i in range(len(numbers)):
        total = total + numbers[i]
    avg = total / len(numbers)
    return avg

import os  # noqa: E402  (unused import example)

data = [10,20,30,40,50]
result = calculate_average(data)
print("Average:", result)
'''

# Backend store budget for repo files kept in memory per session
_REPO_STORE_BUDGET = 4_000_000  # characters
_SCAN_CONCURRENCY = 4


def _score_color(score: int) -> str:
    return "green" if score >= 80 else ("yellow" if score >= 50 else "red")


class State(rx.State):
    """Main application state."""

    # ─── Editor ──────────────────────────────────────────────────────────────
    code: str = SAMPLE_CODE
    language: str = "python"
    current_file: str = "example.py"                     # path key into _file_store
    files: list[dict] = [{"name": "example.py", "path": "example.py", "language": "python"}]
    editor_version: int = 0                              # bump to remount the editor
    _file_store: dict[str, str] = {"example.py": SAMPLE_CODE}

    # ─── Analysis results ────────────────────────────────────────────────────
    terminal_output: str = ""
    stdin_input: str = ""
    error_report: list[dict] = []
    style_report: list[dict] = []
    security_report: list[dict] = []
    complexity_report: list[dict] = []
    ai_report: list[dict] = []
    maintainability_index: int = 100
    ai_optimizations: str = ""
    ai_optimized_code: str = ""
    cfg_image: str = ""
    cfg_error: str = ""
    cfg_mermaid: str = ""
    cfg_summary: str = ""
    style_score: int = 0
    total_issues: int = 0
    ast_info: dict = {}
    analysis_tools: str = ""
    analyzed_language: str = ""
    is_running: bool = False
    is_analyzing: bool = False
    _last_analysis_summary: str = ""

    # ─── RAG (repo context for chat) ─────────────────────────────────────────
    current_repo_id: str = ""

    # ─── AI chat ─────────────────────────────────────────────────────────────
    chat_messages: list[dict] = []
    chat_input: str = ""
    explain_to_beginner: bool = False
    ai_chat_visible: bool = True
    is_asking_ai: bool = False

    # ─── UI ──────────────────────────────────────────────────────────────────
    active_bottom_tab: str = "terminal"
    sidebar_visible: bool = True
    bottom_panel_height: int = 280

    # ─── History ─────────────────────────────────────────────────────────────
    history: list[dict] = []
    is_loading_history: bool = False

    # ─── Notification toast ──────────────────────────────────────────────────
    notification: str = ""
    notification_type: str = "info"

    # ─── Settings ────────────────────────────────────────────────────────────
    gemini_api_key_input: str = ""          # generic "AI key" input (name kept for compat)
    api_key_saved: bool = False
    api_key_provider: str = ""
    _session_keys: dict[str, str] = {}
    github_token: str = ""
    github_token_input: str = ""
    github_token_saved: bool = False
    ollama_model_input: str = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
    ollama_status_label: str = "checking..."
    ollama_status_color: str = "gray"

    # ─── GitHub import ───────────────────────────────────────────────────────
    github_url_input: str = ""
    github_import_open: bool = False
    github_token_section_visible: bool = False
    github_is_fetching: bool = False
    github_fetch_error: str = ""

    # ─── Repo scan results ───────────────────────────────────────────────────
    repo_scan_results: list[dict] = []
    repo_scan_progress: str = ""
    repo_scan_gemini_output: str = ""
    repo_languages_display: str = ""
    is_repo_scanning: bool = False
    repo_name_display: str = ""
    _repo_ref: dict = {}

    # ─── Computed vars ───────────────────────────────────────────────────────

    @rx.var
    def panel_height_px(self) -> str:
        return f"{self.bottom_panel_height}px"

    @rx.var
    def editor_key(self) -> str:
        return f"{self.current_file}::{self.editor_version}"

    @rx.var
    def current_file_name(self) -> str:
        return self.current_file.rsplit("/", 1)[-1]

    @rx.var
    def language_label(self) -> str:
        return "Auto-detect" if self.language == "auto" else lang_registry.label(self.language)

    @rx.var
    def ollama_status_display(self) -> str:
        return self.ollama_status_label

    @rx.var
    def has_optimized_code(self) -> bool:
        return self.ai_optimized_code != ""

    # ─── Panel sizing ────────────────────────────────────────────────────────

    def expand_panel(self):
        self.bottom_panel_height = min(self.bottom_panel_height + 80, 650)

    def shrink_panel(self):
        self.bottom_panel_height = max(self.bottom_panel_height - 80, 80)

    def reset_panel_height(self):
        self.bottom_panel_height = 280

    def set_panel_height(self, h: int):
        self.bottom_panel_height = max(80, min(int(h), 650))

    # ─── Simple setters ──────────────────────────────────────────────────────

    def set_code(self, code: str):
        if code == self.code:
            return
        self.code = code
        self._store_put(self.current_file, code)
        # Brand-new files pick up their language from what the user pastes
        if (self.current_file.startswith("untitled") or self.language == "auto") and code.strip():
            detected = lang_registry.detect_from_content(code)
            if detected and detected != self.language:
                self.language = detected
                self._update_file_entry(self.current_file, language=detected)

    def set_language(self, language: str):
        self.language = language
        self._update_file_entry(self.current_file, language=language)

    def set_active_bottom_tab(self, tab: str):
        self.active_bottom_tab = tab

    def set_chat_input(self, text: str):
        self.chat_input = text

    def set_stdin_input(self, text: str):
        self.stdin_input = text

    def set_gemini_api_key_input(self, value: str):
        self.gemini_api_key_input = value

    def set_github_url_input(self, value: str):
        self.github_url_input = value
        self.github_fetch_error = ""

    def set_github_token_input(self, value: str):
        self.github_token_input = value

    def set_ollama_model_input(self, value: str):
        self.ollama_model_input = value

    def open_github_import(self):
        self.github_import_open = True
        self.github_fetch_error = ""

    def close_github_import(self):
        self.github_import_open = False
        self.github_fetch_error = ""
        self.github_token_section_visible = False

    def toggle_github_token_section(self):
        self.github_token_section_visible = not self.github_token_section_visible

    def toggle_beginner_mode(self):
        self.explain_to_beginner = not self.explain_to_beginner

    def toggle_ai_chat(self):
        self.ai_chat_visible = not self.ai_chat_visible

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible

    def clear_notification(self):
        self.notification = ""

    # ─── File management ─────────────────────────────────────────────────────

    def _update_file_entry(self, path: str, **fields):
        self.files = [{**f, **fields} if f["path"] == path else f for f in self.files]

    def _store_put(self, path: str, code: str):
        # reassign (not mutate) so the state manager always persists the change
        self._file_store = {**self._file_store, path: code}

    def _store_pop(self, path: str):
        self._file_store = {k: v for k, v in self._file_store.items() if k != path}

    def _open_in_editor(self, path: str, code: str, language: str = ""):
        """Load content into the editor and force the textarea to remount."""
        self._store_put(path, code)
        if not any(f["path"] == path for f in self.files):
            lang = language or lang_registry.detect(code, path, fallback=self.language)
            self.files = self.files + [{"name": path, "path": path, "language": lang}]
        self.current_file = path
        self.code = code
        entry = next((f for f in self.files if f["path"] == path), None)
        self.language = language or (entry or {}).get("language") or lang_registry.detect(code, path, "text")
        self.editor_version += 1

    def _reset_results(self):
        self.terminal_output = ""
        self.error_report = []
        self.style_report = []
        self.security_report = []
        self.complexity_report = []
        self.ai_report = []
        self.ai_optimizations = ""
        self.ai_optimized_code = ""
        self.cfg_image = ""
        self.cfg_error = ""
        self.cfg_mermaid = ""
        self.cfg_summary = ""
        self.ast_info = {}
        self.style_score = 0
        self.total_issues = 0
        self.analysis_tools = ""
        self.maintainability_index = 100

    def clear_editor(self):
        self.code = ""
        self._store_put(self.current_file, "")
        self.editor_version += 1
        self._reset_results()
        self._notify("Editor cleared", "info")

    def new_file(self):
        n = len(self.files) + 1
        name = f"untitled-{n}"
        while any(f["path"] == name for f in self.files):
            n += 1
            name = f"untitled-{n}"
        self._store_put(self.current_file, self.code)
        # New files start in auto mode; the language is detected from what's pasted
        self._open_in_editor(name, "", "auto")

    def delete_file(self, path: str):
        if len(self.files) <= 1:
            self._notify("Cannot delete the last file.", "error")
            return
        self.files = [f for f in self.files if f["path"] != path]
        self._store_pop(path)
        if self.current_file == path:
            first = self.files[0]
            self._open_in_editor(first["path"], self._file_store.get(first["path"], ""), first.get("language", ""))
        self._notify(f"'{path.rsplit('/', 1)[-1]}' deleted.", "info")

    def select_file(self, path: str):
        self._store_put(self.current_file, self.code)
        entry = next((f for f in self.files if f["path"] == path), None)
        if entry is None:
            return
        if path not in self._file_store and self._repo_ref:
            return State.load_repo_file_into_editor(path)
        self._open_in_editor(path, self._file_store.get(path, ""), entry.get("language", ""))

    def apply_fix(self, fix_code: str):
        if fix_code:
            self._open_in_editor(self.current_file, fix_code, self.language)
            self._notify("Fix applied to editor!", "success")

    def apply_optimized_code(self):
        if not self.ai_optimized_code:
            return
        self._open_in_editor(self.current_file, self.ai_optimized_code, self.language)
        self.ai_optimized_code = ""
        self._notify("Optimized code applied — click 🔍 Analyze to re-check it.", "success")

    def clear_chat(self):
        self.chat_messages = []

    # ─── File upload ─────────────────────────────────────────────────────────

    async def handle_upload(self, files: list[rx.UploadFile]):
        loaded = []
        for file in files:
            content = await file.read()
            fname = file.filename or "uploaded.txt"
            if b"\x00" in content[:4096]:
                self._notify(f"'{fname}' looks like a binary file — skipped.", "error")
                continue
            try:
                decoded = content.decode("utf-8")
            except UnicodeDecodeError:
                decoded = content.decode("latin-1")
            detected = lang_registry.detect(decoded, fname, fallback="text")
            self.files = [f for f in self.files if f["path"] != fname]
            self._open_in_editor(fname, decoded, detected)
            loaded.append(f"{fname} ({lang_registry.label(detected)})")
        if loaded:
            self._notify("Uploaded: " + ", ".join(loaded), "success")

    # ─── Code execution ──────────────────────────────────────────────────────

    @rx.event(background=True)
    async def run_code(self):
        from codementor.services.code_runner import run_code, format_terminal_output

        async with self:
            if self.is_running:
                return
            code, stdin = self.code, self.stdin_input
            language = self.language
            if language == "auto":
                language = lang_registry.detect(code, self.current_file, "python")
                self.language = language
            self.is_running = True
            self.active_bottom_tab = "terminal"
            self.terminal_output = f"⏳ Running {lang_registry.label(language)}..."

        result = await asyncio.to_thread(run_code, code, language, stdin=stdin)

        async with self:
            self.terminal_output = format_terminal_output(result)
            self.is_running = False

    # ─── Full analysis ───────────────────────────────────────────────────────

    @rx.event(background=True)
    async def analyze_code(self):
        from codementor.services.analysis_pipeline import analyze_source
        from codementor.services.cfg_service import render_spec
        from codementor.services.gemini_service import ai_review, ai_cfg_spec, providers

        async with self:
            if self.is_analyzing:
                return
            if not self.code.strip():
                self._notify("Please write some code first!", "error")
                return
            code, language, filename = self.code, self.language, self.current_file
            keys = dict(self._session_keys)
            self._reset_results()
            self.is_analyzing = True
            self.active_bottom_tab = "errors"

        # 1 — static pipeline (CPU-bound → worker thread)
        report = await asyncio.to_thread(analyze_source, code, language, filename,
                                         native=True, include_cfg=True)
        lang = report["language"]

        async with self:
            if self.language == "auto" or self.language != lang:
                self.language = lang
                self._update_file_entry(filename, language=lang)
            self.analyzed_language = report["language_label"]
            self.ast_info = report["ast_info"] or {}
            self.error_report = report["errors"]
            self.style_report = report["style_issues"]
            self.style_score = report["style_score"]
            self.security_report = report["security"]
            self.complexity_report = report["complexity"]
            self.maintainability_index = report["maintainability_index"]
            cfg = report["cfg"]
            self.cfg_image, self.cfg_error = cfg.get("image", ""), cfg.get("error", "")
            self.cfg_mermaid, self.cfg_summary = cfg.get("mermaid", ""), cfg.get("summary", "")
            self.analysis_tools = " · ".join(report["tools"])
            self._recount()
            self._last_analysis_summary = self._summarize(report)
            ai_ready = bool(providers(keys))
            self.ai_optimizations = (f"🤖 Getting AI review for {report['language_label']}..."
                                     if ai_ready else "")

        # 2 — AI review (+ AI CFG when no parser could build one), concurrently
        need_ai_cfg = (ai_ready and not cfg.get("image") and lang_registry.is_code(lang)
                       and "syntax" not in cfg.get("error", "").lower())
        review_task = ai_review(
            code, lang, errors=report["errors"], style_issues=report["style_issues"],
            security_issues=report["security"], complexity_report=report["complexity"],
            ast_info=report["ast_info"], filename=filename, keys=keys,
        )
        if need_ai_cfg:
            review, spec = await asyncio.gather(review_task, ai_cfg_spec(code, lang, keys))
        else:
            review, spec = await review_task, None
        ai_cfg = await asyncio.to_thread(render_spec, spec) if spec else None

        async with self:
            self.ai_optimizations = review["markdown"]
            self.ai_report = review["issues"]
            self.ai_optimized_code = review["optimized_code"]
            if ai_cfg and ai_cfg.get("image"):
                self.cfg_image, self.cfg_error = ai_cfg["image"], ""
                self.cfg_mermaid, self.cfg_summary = ai_cfg["mermaid"], ai_cfg["summary"] + " (AI-generated)"
            self._recount()
            self.is_analyzing = False
            self.active_bottom_tab = "errors" if self.total_issues else "optimizations"
            self._save_current_snippet()
            self._refresh_history()
            self._notify(
                f"✅ {report['language_label']} analysis complete — {self.total_issues} issues, "
                f"style {self.style_score}/100" if self.total_issues else
                f"✅ {report['language_label']} analysis complete — no issues found!",
                "info" if self.total_issues else "success",
            )

    def _recount(self):
        self.total_issues = (len(self.error_report) + len(self.style_report) + len(self.security_report)
                             + len(self.complexity_report) + len(self.ai_report))

    @staticmethod
    def _summarize(report: dict) -> str:
        def top(items, n=5):
            return "; ".join(f"L{i['line']} {i['message']}" for i in items[:n]) or "none"
        return (f"Language: {report['language_label']} · style {report['style_score']}/100 · "
                f"MI {report['maintainability_index']}/100\n"
                f"Errors: {top(report['errors'])}\nSecurity: {top(report['security'])}\n"
                f"Complexity: {top(report['complexity'], 3)}")

    # ─── AI Chat ─────────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def send_chat_message(self):
        from codementor.services.gemini_service import chat_with_ai

        async with self:
            msg = self.chat_input.strip()
            if not msg or self.is_asking_ai:
                return
            history = list(self.chat_messages)
            self.chat_messages = history + [{"role": "user", "content": msg, "ts": str(int(time.time()))}]
            self.chat_input = ""
            self.is_asking_ai = True
            code, language, repo_id = self.code, self.language, self.current_repo_id
            analysis, keys = self._last_analysis_summary, dict(self._session_keys)
            beginner = self.explain_to_beginner

        rag_context = ""
        if repo_id:
            from codementor.services.rag_service import retrieve_context
            rag_context = await asyncio.to_thread(retrieve_context, repo_id, msg, 4)

        response = await chat_with_ai(
            messages=history, user_message=msg, code=code, beginner_mode=beginner,
            language=language, rag_context=rag_context, analysis_context=analysis, keys=keys,
        )
        async with self:
            self.chat_messages = self.chat_messages + [
                {"role": "assistant", "content": response, "ts": str(int(time.time()))}]
            self.is_asking_ai = False

    def send_chat_on_enter(self, key: str):
        if key == "Enter":
            return State.send_chat_message

    # ─── History / persistence ───────────────────────────────────────────────

    def _save_current_snippet(self) -> bool:
        from codementor.services.db_service import save_snippet
        return bool(save_snippet({
            "title": self.current_file_name,
            "code": self.code,
            "language": self.language,
            "style_score": self.style_score,
            "error_count": len(self.error_report),
            "style_issue_count": len(self.style_report),
        }))

    def _refresh_history(self):
        from codementor.services.db_service import get_snippets
        snippets = get_snippets()
        for s in snippets:
            score = s.get("style_score", 0)
            s["score_color"] = _score_color(score)
            s["has_errors"] = s.get("error_count", 0) > 0
            s["date_display"] = (s.get("created_at") or "")[:10]
        self.history = snippets

    def save_snippet(self):
        if self._save_current_snippet():
            self._refresh_history()
            self._notify("Snippet saved!", "success")
        else:
            self._notify("Failed to save snippet.", "error")

    async def load_history(self):
        self.is_loading_history = True
        yield
        self._refresh_history()
        self.is_loading_history = False

    def delete_snippet(self, snippet_id: int):
        from codementor.services.db_service import delete_snippet
        delete_snippet(snippet_id)
        self._refresh_history()

    def load_snippet_into_editor(self, code: str, language: str, title: str):
        path = title or "snippet"
        self.files = [f for f in self.files if f["path"] != path]
        self._open_in_editor(path, code, lang_registry.normalize(language) or "text")
        self._notify(f"Loaded '{title}' into editor!", "success")

    # ─── Settings ────────────────────────────────────────────────────────────

    def save_api_key(self):
        from codementor.services.gemini_service import detect_key_provider
        key = self.gemini_api_key_input.strip()
        provider = detect_key_provider(key)
        if not key:
            self._notify("Please enter an API key.", "error")
            return
        if not provider:
            self._notify("Unrecognized key — expected Groq (gsk_…), Gemini (AIza…) or OpenAI (sk-…).", "error")
            return
        self._session_keys = {**self._session_keys, provider: key}
        self.api_key_saved = True
        self.api_key_provider = {"groq": "Groq", "gemini": "Google Gemini", "openai": "OpenAI"}[provider]
        self.gemini_api_key_input = ""
        self._notify(f"{self.api_key_provider} key saved for this session.", "success")
        return State.refresh_ollama_status

    def clear_api_keys(self):
        self._session_keys = {}
        self.api_key_saved = False
        self.api_key_provider = ""
        self._notify("Session API keys removed.", "info")
        return State.refresh_ollama_status

    def save_ollama_model(self):
        model = self.ollama_model_input.strip()
        if model:
            os.environ["OLLAMA_MODEL"] = model  # server-wide by design: Ollama is the operator's own
            import codementor.services.gemini_service as _ai
            _ai._ollama_ok = None
            self._notify(f"Ollama model set to: {model}", "success")

    def refresh_ollama_status(self):
        import codementor.services.gemini_service as _ai
        _ai._ollama_ok = None
        status = _ai.get_ai_status(self._session_keys)
        if status["backend"] == "none":
            self.ollama_status_label = "No AI configured — add a key below"
            self.ollama_status_color = "red"
        else:
            via = " (your key)" if status.get("source") == "session" else ""
            self.ollama_status_label = f"Active: {status['label']}{via}"
            self.ollama_status_color = "green"

    def save_github_token(self):
        token = self.github_token_input.strip()
        if token:
            self.github_token = token
            self.github_token_saved = True
            self.github_token_input = ""
            self._notify("GitHub token saved for this session!", "success")
        else:
            self._notify("Please enter a valid GitHub token.", "error")

    # ─── GitHub import ───────────────────────────────────────────────────────

    async def import_from_github(self):
        """Single file → load into editor. Repo / folder URL → full scan."""
        from codementor.services.github_service import parse_github_url, fetch_single_file

        url = self.github_url_input.strip()
        if not url:
            self.github_fetch_error = "Please enter a GitHub URL."
            return
        self.github_is_fetching = True
        self.github_fetch_error = ""
        yield

        parsed = parse_github_url(url)
        if parsed["type"] == "unknown":
            self.github_fetch_error = (
                "Cannot parse URL. Supported formats:\n"
                "• https://github.com/owner/repo\n"
                "• https://github.com/owner/repo/tree/main/src\n"
                "• https://github.com/owner/repo/blob/main/file.ext\n"
                "• https://raw.githubusercontent.com/owner/repo/main/file.ext"
            )
            self.github_is_fetching = False
            return

        if parsed["type"] == "single_file":
            result = await asyncio.to_thread(
                fetch_single_file, parsed["owner"], parsed["repo"], parsed["branch"],
                parsed["path"], self._gh_token())
            self.github_is_fetching = False
            if result["ok"]:
                path = parsed["path"]
                self.files = [f for f in self.files if f["path"] != path]
                self._open_in_editor(path, result["content"],
                                     lang_registry.detect(result["content"], path, "text"))
                self.github_import_open = False
                self._notify(f"'{parsed['filename']}' imported ({self.language_label}). Click 🔍 Analyze.", "success")
            else:
                self.github_fetch_error = result.get("error", "Failed to fetch file.")
            return

        self.github_is_fetching = False
        self.github_import_open = False
        yield State.start_repo_scan

    @rx.event(background=True)
    async def start_repo_scan(self):
        """
        Full repository review:
          1. download the repo as one zipball (any language, honours /tree/<branch>/<dir>)
          2. run the unified static pipeline on every file (concurrently, in threads)
          3. triage + rank files, index them for repo-aware chat (RAG)
          4. AI: one repository overview + deep reviews of the top flagged files
        """
        from codementor.services.github_service import parse_github_url, fetch_repo_snapshot
        from codementor.services.analysis_pipeline import analyze_source, triage
        from codementor.services.gemini_service import (
            analyze_repo_overview, get_optimization_suggestions, providers)
        from codementor.services.rag_service import index_repo, clear_repo

        async with self:
            if self.is_repo_scanning:
                return
            parsed = parse_github_url(self.github_url_input.strip())
            token, keys = self._gh_token(), dict(self._session_keys)
            owner, repo = parsed.get("owner", ""), parsed.get("repo", "")
            branch, subdir = parsed.get("branch", ""), parsed.get("subdir", "")
            self.is_repo_scanning = True
            self.repo_scan_results = []
            self.repo_scan_gemini_output = ""
            self.repo_languages_display = ""
            self.active_bottom_tab = "repo_scan"
            self.repo_name_display = f"{owner}/{repo}" + (f"/{subdir}" if subdir else "")
            self.repo_scan_progress = f"Downloading {self.repo_name_display}..."

        snapshot = await asyncio.to_thread(fetch_repo_snapshot, owner, repo, branch, subdir, token)
        if not snapshot["ok"]:
            async with self:
                self.repo_scan_progress = ""
                self.is_repo_scanning = False
                self._notify(snapshot.get("error", "Failed to fetch repository"), "error")
            return

        files = snapshot["files"]
        total = len(files)
        if total == 0:
            async with self:
                self.repo_scan_progress = ""
                self.is_repo_scanning = False
                self._notify("No source files found in this repository.", "info")
            return

        async with self:
            self.repo_scan_progress = f"Found {total} files on '{snapshot['branch']}'. Analyzing..."

        # ── Static analysis, in concurrent batches ───────────────────────────
        async def analyze_one(f: dict) -> dict:
            report = await asyncio.to_thread(
                analyze_source, f["content"], f["language"], f["path"],
                native=False, include_cfg=False)
            return {**f, "report": report, **triage(report)}

        analyzed: list[dict] = []
        for start in range(0, total, _SCAN_CONCURRENCY * 2):
            batch = files[start:start + _SCAN_CONCURRENCY * 2]
            analyzed += await asyncio.gather(*(analyze_one(f) for f in batch))
            async with self:
                self.repo_scan_progress = f"Analyzing {len(analyzed)}/{total}: {batch[-1]['path']}"

        rows, lang_counts = [], {}
        for item in analyzed:
            rep = item["report"]
            lang_counts[rep["language_label"]] = lang_counts.get(rep["language_label"], 0) + 1
            rows.append({
                "path": item["path"], "filename": item["filename"],
                "language": rep["language_label"],
                "complexity": item["complexity"], "error_count": item["error_count"],
                "security_count": item["security_count"], "style_score": rep["style_score"],
                "flagged": item["flagged"], "priority_score": item["priority_score"],
                "top_issue": item["top_issue"], "fetch_error": "",
                "score_color": _score_color(rep["style_score"]),
                "complexity_color": "red" if item["complexity"] > 10 else ("yellow" if item["complexity"] > 5 else "green"),
                "error_color": "red" if item["error_count"] else "green",
                "security_color": "red" if item["security_count"] else "green",
                "status_label": "FLAGGED" if item["flagged"] else "CLEAN",
                "status_color": "red" if item["flagged"] else "green",
            })
        rows.sort(key=lambda r: (not r["flagged"], -r["priority_score"], r["path"]))
        flagged = [r for r in rows if r["flagged"]]
        langs = ", ".join(f"{k} {v}" for k, v in sorted(lang_counts.items(), key=lambda kv: -kv[1]))

        # ── RAG index for repo-aware chat ────────────────────────────────────
        repo_id = f"github.com/{owner}/{repo}"
        await asyncio.to_thread(clear_repo, repo_id)
        chunks = await asyncio.to_thread(index_repo, repo_id, [{"path": f["path"], "code": f["content"]} for f in files])

        async with self:
            self.repo_scan_results = rows
            self.repo_languages_display = langs
            self.current_repo_id = repo_id
            self._repo_ref = {"owner": owner, "repo": repo, "branch": snapshot["branch"]}
            # keep file contents server-side, within a memory budget
            budget, store = _REPO_STORE_BUDGET, {}
            for f in sorted(files, key=lambda f: next((r["priority_score"] for r in rows if r["path"] == f["path"]), 0), reverse=True):
                if budget - len(f["content"]) < 0:
                    continue
                store[f["path"]] = f["content"]
                budget -= len(f["content"])
            self._file_store = store
            self.files = [{"name": f["path"], "path": f["path"],
                           "language": lang_registry.from_filename(f["path"]) or "text"} for f in files]
            first = next((r for r in rows if r["flagged"] and r["path"] in store), None) or \
                next((r for r in rows if r["path"] in store), None)
            if first:
                self._open_in_editor(first["path"], store[first["path"]])
            self.repo_scan_progress = (
                f"Static analysis done — {len(flagged)} flagged, {total - len(flagged)} clean · "
                f"{chunks} code chunks indexed for chat"
                + (" · repo truncated to 300 files" if snapshot.get("truncated") else "")
            )
            ai_ready = bool(providers(keys))
            repo_label = self.repo_name_display

        if not ai_ready:
            async with self:
                self.is_repo_scanning = False
                self._notify(f"Repo scan done: {len(flagged)}/{total} files flagged. Add an AI key for AI reviews.", "info")
            return

        # ── AI: repository overview, then deep dives on top flagged code files ──
        async with self:
            self.repo_scan_progress += "\n🤖 Writing repository overview..."
        stats = {"languages": langs, "files": total, "flagged": len(flagged),
                 "errors": sum(r["error_count"] for r in rows),
                 "security": sum(r["security_count"] for r in rows)}
        overview = await analyze_repo_overview(repo_label, stats, rows, keys)
        async with self:
            self.repo_scan_gemini_output = overview

        by_path = {item["path"]: item for item in analyzed}
        targets = [by_path[r["path"]] for r in flagged
                   if lang_registry.is_code(lang_registry.from_filename(r["path"]) or "text")][:3]
        for idx, target in enumerate(targets, 1):
            async with self:
                self.repo_scan_progress = f"🤖 AI review {idx}/{len(targets)}: {target['path']}"
            rep = target["report"]
            suggestions = await get_optimization_suggestions(
                target["content"][:8000], rep["errors"][:10], rep["style_issues"][:5],
                rep["ast_info"], language=rep["language"], security_issues=rep["security"][:6],
                complexity_report=rep["complexity"][:5], keys=keys, filename=target["path"],
            )
            async with self:
                self.repo_scan_gemini_output += (
                    f"\n\n---\n\n## 📄 `{target['path']}`\n"
                    f"> {rep['language_label']} · errors {target['error_count']} · "
                    f"security {target['security_count']} · max complexity {target['complexity']} · "
                    f"style {rep['style_score']}/100\n\n{suggestions}"
                )

        async with self:
            self.repo_scan_progress = (f"✅ Repo scan complete — {total} files · {len(flagged)} flagged · "
                                       f"{len(targets)} AI deep-reviews · chat now knows this repo")
            self.is_repo_scanning = False
            self._notify(f"Repo scan done: {len(flagged)}/{total} files flagged for review.",
                         "success" if not flagged else "info")

    async def load_repo_file_into_editor(self, path: str):
        """Open a scanned repo file (fetching it on demand if it wasn't kept in memory)."""
        self._store_put(self.current_file, self.code)
        content = self._file_store.get(path)
        if content is None and self._repo_ref:
            from codementor.services.github_service import fetch_single_file
            ref = self._repo_ref
            result = await asyncio.to_thread(fetch_single_file, ref["owner"], ref["repo"],
                                             ref["branch"], path, self._gh_token())
            content = result.get("content") if result.get("ok") else None
        if content is None:
            self._notify(f"Could not load '{path}'.", "error")
            return
        self._open_in_editor(path, content, lang_registry.from_filename(path) or "")
        self._notify(f"'{path.rsplit('/', 1)[-1]}' opened ({self.language_label}) — click 🔍 Analyze.", "success")

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _gh_token(self) -> str | None:
        """User's session token, else the server's GITHUB_TOKEN, else anonymous."""
        return self.github_token or os.environ.get("GITHUB_TOKEN") or None

    def _notify(self, message: str, ntype: str = "info"):
        self.notification = message
        self.notification_type = ntype
