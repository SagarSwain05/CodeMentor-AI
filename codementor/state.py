"""
Single unified application state for AI Code Reviewer.
All state variables and event handlers live here.
"""

import os
import time
import reflex as rx
from dotenv import load_dotenv

# Load .env at import time so GEMINI_API_KEY is available immediately
load_dotenv()


SAMPLE_CODE = '''# Welcome to AI Code Reviewer!
# Paste your Python code here and click Analyze 🔍

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


class State(rx.State):
    """Main application state."""

    # ─── Editor ──────────────────────────────────────────────────────────────
    code: str = SAMPLE_CODE
    language: str = "python"
    current_file: str = "example.py"
    files: list[dict] = [{"name": "example.py", "code": SAMPLE_CODE}]

    # ─── Analysis results ────────────────────────────────────────────────────
    terminal_output: str = ""
    stdin_input: str = ""
    error_report: list[dict] = []
    style_report: list[dict] = []
    security_report: list[dict] = []
    complexity_report: list[dict] = []
    maintainability_index: int = 100
    ai_optimizations: str = ""
    cfg_image: str = ""
    cfg_error: str = ""
    style_score: int = 0
    total_issues: int = 0
    ast_info: dict = {}
    is_running: bool = False
    is_analyzing: bool = False

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
    bottom_panel_height: int = 280  # px — drag/button resizable

    @rx.var
    def panel_height_px(self) -> str:
        return f"{self.bottom_panel_height}px"

    def expand_panel(self):
        self.bottom_panel_height = min(self.bottom_panel_height + 80, 650)

    def shrink_panel(self):
        self.bottom_panel_height = max(self.bottom_panel_height - 80, 80)

    def reset_panel_height(self):
        self.bottom_panel_height = 280

    def set_panel_height(self, h: int):
        self.bottom_panel_height = max(80, min(h, 650))

    # ─── History ─────────────────────────────────────────────────────────────
    history: list[dict] = []
    is_loading_history: bool = False

    # ─── Notification toast ──────────────────────────────────────────────────
    notification: str = ""
    notification_type: str = "info"

    # ─── Settings ────────────────────────────────────────────────────────────
    gemini_api_key_input: str = ""
    api_key_saved: bool = bool(os.environ.get("OPENAI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", ""))
    github_token: str = ""
    github_token_input: str = ""
    github_token_saved: bool = False
    ollama_model_input: str = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
    ollama_status_label: str = "checking..."
    ollama_status_color: str = "gray"

    def set_ollama_model_input(self, value: str):
        self.ollama_model_input = value

    @rx.var
    def ollama_status_display(self) -> str:
        return self.ollama_status_label

    def save_ollama_model(self):
        model = self.ollama_model_input.strip()
        if model:
            os.environ["OLLAMA_MODEL"] = model
            # Reset client cache in gemini_service
            try:
                import codementor.services.gemini_service as _ai
                _ai._ollama_ok = None  # force re-check
            except Exception:
                pass
            self._notify(f"Ollama model set to: {model}", "success")

    def refresh_ollama_status(self):
        from codementor.services.gemini_service import _ollama_running, get_ai_status
        import codementor.services.gemini_service as _ai
        _ai._ollama_ok = None  # force fresh check
        status = get_ai_status()
        if status["backend"] == "ollama":
            self.ollama_status_label = f"Running — {status['model']}"
            self.ollama_status_color = "green"
        elif status["backend"] == "openai":
            self.ollama_status_label = "Offline (OpenAI fallback active)"
            self.ollama_status_color = "yellow"
        else:
            self.ollama_status_label = "Offline — start with: ollama serve"
            self.ollama_status_color = "red"

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
    is_repo_scanning: bool = False
    repo_name_display: str = ""

    # ─── Simple setters ──────────────────────────────────────────────────────

    def set_code(self, code: str):
        self.code = code

    def set_language(self, language: str):
        self.language = language

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

    # ─── Editor actions ──────────────────────────────────────────────────────

    def clear_editor(self):
        self.code = ""
        self.terminal_output = ""
        self.error_report = []
        self.style_report = []
        self.ai_optimizations = ""
        self.cfg_image = ""
        self.cfg_error = ""
        self.ast_info = {}
        self.style_score = 0
        self.total_issues = 0
        self._notify("Editor cleared", "info")

    def new_file(self):
        name = f"file_{len(self.files) + 1}.py"
        self.files = self.files + [{"name": name, "code": ""}]
        self.current_file = name
        self.code = ""

    def delete_file(self, filename: str):
        if len(self.files) <= 1:
            self._notify("Cannot delete the last file.", "error")
            return
        updated = [f for f in self.files if f["name"] != filename]
        self.files = updated
        if self.current_file == filename:
            self.current_file = updated[0]["name"]
            self.code = updated[0]["code"]
        self._notify(f"'{filename}' deleted.", "info")

    def select_file(self, filename: str):
        # Save current code to current file entry
        updated = []
        for f in self.files:
            if f["name"] == self.current_file:
                updated.append({"name": f["name"], "code": self.code})
            else:
                updated.append(f)
        self.files = updated

        # Load selected
        self.current_file = filename
        for f in self.files:
            if f["name"] == filename:
                self.code = f["code"]
                break

    def apply_fix(self, fix_code: str):
        if fix_code:
            self.code = fix_code
            self._notify("Fix applied to editor!", "success")

    def clear_chat(self):
        self.chat_messages = []

    # ─── File upload ─────────────────────────────────────────────────────────

    async def handle_upload(self, files: list[rx.UploadFile]):
        _ext_lang = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript",
            ".java": "java", ".c": "c", ".cpp": "cpp", ".cc": "cpp",
            ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
            ".swift": "swift", ".kt": "kotlin", ".cs": "csharp",
            ".sh": "bash", ".html": "html", ".css": "css",
            ".json": "json", ".sql": "sql", ".md": "markdown",
        }
        for file in files:
            content = await file.read()
            try:
                decoded = content.decode("utf-8")
                fname = file.filename or "uploaded.txt"
                ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                detected_lang = _ext_lang.get(ext, self.language)
                self.code = decoded
                self.current_file = fname
                self.language = detected_lang
                existing_names = [f["name"] for f in self.files]
                if fname not in existing_names:
                    self.files = self.files + [{"name": fname, "code": decoded}]
                else:
                    # Update existing
                    self.files = [
                        {"name": f["name"], "code": decoded if f["name"] == fname else f["code"]}
                        for f in self.files
                    ]
                self._notify(f"'{fname}' uploaded! Language: {detected_lang}", "success")
            except Exception as e:
                self._notify(f"Error reading file: {e}", "error")

    # ─── Code execution ──────────────────────────────────────────────────────

    async def run_code(self):
        from codementor.services.code_runner import run_code, format_terminal_output

        self.is_running = True
        self.active_bottom_tab = "terminal"
        self.terminal_output = f"⏳ Running {self.language}..."
        yield

        result = run_code(self.code, self.language, stdin=self.stdin_input)
        self.terminal_output = format_terminal_output(result)
        self.is_running = False

    # ─── Full analysis ───────────────────────────────────────────────────────

    async def analyze_code(self):
        from codementor.services.ast_analyzer import analyze_ast
        from codementor.services.linter_service import (
            check_errors, check_style, check_complexity,
            check_security, get_maintainability_index,
        )
        from codementor.services.cfg_service import generate_cfg
        from codementor.services.gemini_service import get_optimization_suggestions

        if not self.code.strip():
            self._notify("Please write some code first!", "error")
            return

        self.is_analyzing = True
        self.active_bottom_tab = "errors"
        self.error_report = []
        self.style_report = []
        self.security_report = []
        self.complexity_report = []
        self.ai_optimizations = ""
        self.cfg_image = ""
        self.cfg_error = ""
        yield

        lang = self.language

        # Step 1: AST (Python) / generic structure
        if lang == "python":
            self.ast_info = analyze_ast(self.code)
        else:
            self.ast_info = {
                "syntax_ok": True, "functions": [], "classes": [],
                "imports": [], "complexity": 0,
                "line_count": len(self.code.splitlines()), "node_count": 0,
            }
        yield

        # Step 2: Linting (pyflakes / pycodestyle / generic)
        self.error_report = check_errors(self.code, lang)
        style_result = check_style(self.code, lang)
        self.style_report = style_result["issues"]
        self.style_score = style_result["score"]
        yield

        # Step 3: Complexity + Security (Python only — free, no LLM tokens)
        if lang == "python":
            self.complexity_report = check_complexity(self.code)
            self.security_report   = check_security(self.code)
            self.maintainability_index = get_maintainability_index(self.code)
        else:
            self.complexity_report = []
            self.security_report   = []
            self.maintainability_index = 100

        self.total_issues = (
            len(self.error_report)
            + len(self.style_report)
            + len(self.security_report)
            + len(self.complexity_report)
        )
        yield

        # Step 4: CFG (Python only)
        if lang == "python":
            try:
                result = generate_cfg(self.code)
                if result:
                    self.cfg_image = result
                    self.cfg_error = ""
                else:
                    self.cfg_image = ""
                    self.cfg_error = "CFG could not be generated (empty or parse error)."
            except Exception as cfg_exc:
                self.cfg_image = ""
                self.cfg_error = f"CFG error: {cfg_exc}"
        else:
            self.cfg_image = ""
            self.cfg_error = f"Control Flow Graph is only available for Python (current: {lang})."
        yield

        # Step 5: AI suggestions — only sent to LLM if there's something worth flagging
        self.active_bottom_tab = "optimizations"
        self.ai_optimizations = f"🤖 Getting AI suggestions for {lang}..."
        yield

        suggestions = await get_optimization_suggestions(
            self.code,
            self.error_report,
            self.style_report,
            self.ast_info,
            language=lang,
            security_issues=self.security_report,
            complexity_report=self.complexity_report,
        )
        self.ai_optimizations = suggestions
        self.is_analyzing = False

        # Auto-save to history after every analysis
        from codementor.services.db_service import save_snippet as _save
        _save({
            "title": self.current_file,
            "code": self.code,
            "language": self.language,
            "style_score": self.style_score,
            "error_count": len(self.error_report),
            "style_issue_count": len(self.style_report),
        })
        yield State.load_history

        msg = (
            f"✅ Analysis complete — {self.total_issues} issues found, style score: {self.style_score}/100"
            if self.total_issues > 0
            else "✅ Analysis complete — No issues found!"
        )
        self._notify(msg, "success" if self.total_issues == 0 else "info")

    # ─── AI Chat ─────────────────────────────────────────────────────────────

    async def send_chat_message(self):
        from codementor.services.gemini_service import chat_with_ai

        msg = self.chat_input.strip()
        if not msg:
            return

        self.chat_messages = self.chat_messages + [{
            "role": "user",
            "content": msg,
            "ts": str(int(time.time())),
        }]
        self.chat_input = ""
        self.is_asking_ai = True
        yield

        # Retrieve relevant repo context (RAG) if a repo was scanned
        rag_context = ""
        if self.current_repo_id:
            from codementor.services.rag_service import retrieve_context
            rag_context = retrieve_context(self.current_repo_id, msg, top_k=3)

        response = await chat_with_ai(
            messages=self.chat_messages[:-1],
            user_message=msg,
            code=self.code,
            beginner_mode=self.explain_to_beginner,
            language=self.language,
            rag_context=rag_context,
        )

        self.chat_messages = self.chat_messages + [{
            "role": "assistant",
            "content": response,
            "ts": str(int(time.time())),
        }]
        self.is_asking_ai = False

    async def send_chat_on_enter(self, key: str):
        if key == "Enter":
            yield State.send_chat_message

    # ─── History / persistence ───────────────────────────────────────────────

    async def save_snippet(self):
        from codementor.services.db_service import save_snippet

        result = save_snippet({
            "title": self.current_file,
            "code": self.code,
            "language": self.language,
            "style_score": self.style_score,
            "error_count": len(self.error_report),
            "style_issue_count": len(self.style_report),
        })

        if result:
            self._notify("Snippet saved!", "success")
            yield State.load_history
        else:
            self._notify("Failed to save snippet.", "error")

    async def load_history(self):
        from codementor.services.db_service import get_snippets

        self.is_loading_history = True
        yield
        snippets = get_snippets()
        # Pre-compute display fields so components avoid comparison Vars
        for s in snippets:
            score = s.get("style_score", 0)
            s["score_color"] = (
                "green" if score >= 80 else ("yellow" if score >= 50 else "red")
            )
            s["has_errors"] = s.get("error_count", 0) > 0
            s["date_display"] = (s.get("created_at") or "")[:10]
        self.history = snippets
        self.is_loading_history = False

    async def delete_snippet(self, snippet_id: int):
        from codementor.services.db_service import delete_snippet

        delete_snippet(snippet_id)
        yield State.load_history

    def load_snippet_into_editor(self, code: str, language: str, title: str):
        self.code = code
        self.language = language
        self.current_file = title
        self._notify(f"Loaded '{title}' into editor!", "success")

    # ─── Settings ────────────────────────────────────────────────────────────

    def save_api_key(self):
        key = self.gemini_api_key_input.strip()
        if key:
            # Auto-detect key type
            if key.startswith("sk-"):
                os.environ["OPENAI_API_KEY"] = key
            else:
                os.environ["GEMINI_API_KEY"] = key
            self.api_key_saved = True
            self._notify("API key saved for this session!", "success")
        else:
            self._notify("Please enter a valid API key.", "error")

    def save_github_token(self):
        token = self.github_token_input.strip()
        if token:
            self.github_token = token
            self.github_token_saved = True
            self._notify("GitHub token saved for this session!", "success")
        else:
            self._notify("Please enter a valid GitHub token.", "error")

    # ─── GitHub import ───────────────────────────────────────────────────────

    async def import_from_github(self):
        """Main handler: single file import OR trigger repo scan."""
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
                "• https://github.com/owner/repo/blob/main/file.py\n"
                "• https://raw.githubusercontent.com/owner/repo/main/file.py"
            )
            self.github_is_fetching = False
            return

        if parsed["type"] == "single_file":
            result = fetch_single_file(
                parsed["owner"], parsed["repo"],
                parsed["branch"], parsed["path"],
                token=self.github_token or None,
            )
            if result["ok"]:
                fname = parsed["filename"]
                self.code = result["content"]
                self.current_file = fname
                existing_names = [f["name"] for f in self.files]
                if fname not in existing_names:
                    self.files = self.files + [{"name": fname, "code": result["content"]}]
                self.github_import_open = False
                self.github_is_fetching = False
                self._notify(f"'{fname}' imported from GitHub!", "success")
            else:
                self.github_fetch_error = result.get("error", "Failed to fetch file.")
                self.github_is_fetching = False
            return

        # Repo scan
        self.github_is_fetching = False
        self.github_import_open = False
        yield State.start_repo_scan

    async def start_repo_scan(self):
        """
        Full repo analysis:
        1. Fetch file tree
        2. Run AST + linting on every Python file (no API cost)
        3. Triage: flag files with complexity > 10, errors > 0, or style < 70
        4. Send top-5 flagged files to Gemini only
        """
        from codementor.services.github_service import (
            parse_github_url, fetch_repo_tree,
            fetch_file_content, triage_files,
        )
        from codementor.services.ast_analyzer import analyze_ast
        from codementor.services.linter_service import check_errors, check_style
        from codementor.services.gemini_service import get_optimization_suggestions

        parsed = parse_github_url(self.github_url_input.strip())
        owner = parsed.get("owner", "")
        repo = parsed.get("repo", "")
        branch = parsed.get("branch", "main")

        self.is_repo_scanning = True
        self.repo_scan_results = []
        self.repo_scan_gemini_output = ""
        self.active_bottom_tab = "repo_scan"
        self.repo_name_display = f"{owner}/{repo}"
        self.repo_scan_progress = f"Fetching file tree for {owner}/{repo}..."
        yield

        # Step 1: Get file tree
        tree_result = fetch_repo_tree(owner, repo, branch, token=self.github_token or None)
        if not tree_result["ok"]:
            self.repo_scan_progress = ""
            self.is_repo_scanning = False
            self._notify(tree_result.get("error", "Failed to fetch repo"), "error")
            return

        files = tree_result["files"]
        resolved_branch = tree_result["branch"]
        truncated = tree_result.get("truncated", False)
        total = len(files)

        if total == 0:
            self.repo_scan_progress = ""
            self.is_repo_scanning = False
            self._notify("No Python files found in this repository.", "info")
            return

        self.repo_scan_progress = f"Found {total} Python files. Analyzing..."
        yield

        # Step 2: Fetch + analyze each file
        file_analyses = []
        for i, file_meta in enumerate(files):
            path = file_meta["path"]
            self.repo_scan_progress = f"Analyzing {i + 1}/{total}: {path}"
            yield

            fetched = fetch_file_content(
                owner, repo, resolved_branch, path,
                token=self.github_token or None,
            )
            if fetched.get("content") is None:
                file_analyses.append({
                    "path": path,
                    "filename": file_meta["filename"],
                    "content": "",
                    "ast_info": {},
                    "errors": [],
                    "style_score": 100,
                    "fetch_error": fetched.get("error", "fetch failed"),
                    "flagged": False,
                    "priority_score": 0,
                    "complexity": 0,
                    "error_count": 0,
                })
                continue

            content = fetched["content"]
            ast_info = analyze_ast(content)
            errors = check_errors(content)
            style_result = check_style(content)

            file_analyses.append({
                "path": path,
                "filename": file_meta["filename"],
                "content": content,
                "ast_info": ast_info,
                "errors": errors,
                "style_score": style_result["score"],
                "fetch_error": "",
            })

        # Step 3: Triage
        triage = triage_files(file_analyses, max_gemini=5)
        flagged_count = len(triage["flagged"])
        clean_count = len(triage["clean"])

        # Build display results (no content, no ast_info — keep state small)
        display_results = []
        for item in file_analyses:
            triaged = next(
                (t for t in triage["flagged"] + triage["clean"]
                 if t["path"] == item["path"]), item
            )
            display_results.append({
                "path": item["path"],
                "filename": item["filename"],
                "complexity": triaged.get("complexity", 0),
                "error_count": triaged.get("error_count", 0),
                "style_score": triaged.get("style_score", 100),
                "flagged": triaged.get("flagged", False),
                "priority_score": triaged.get("priority_score", 0),
                "fetch_error": item.get("fetch_error", ""),
                # pre-computed display fields
                "score_color": (
                    "green" if triaged.get("style_score", 100) >= 80
                    else ("yellow" if triaged.get("style_score", 100) >= 50 else "red")
                ),
                "complexity_color": (
                    "red" if triaged.get("complexity", 0) > 10
                    else ("yellow" if triaged.get("complexity", 0) > 5 else "green")
                ),
                "error_color": "red" if triaged.get("error_count", 0) > 0 else "green",
                "status_label": "FLAGGED" if triaged.get("flagged") else "CLEAN",
                "status_color": "red" if triaged.get("flagged") else "green",
            })

        # Sort: flagged first, then by priority
        display_results.sort(key=lambda x: (not x["flagged"], -x["priority_score"]))
        self.repo_scan_results = display_results

        # ── Populate the sidebar with all fetched files ────────────────────
        repo_files = [
            {"name": item["filename"], "code": item["content"]}
            for item in file_analyses
            if item.get("content")
        ]
        if repo_files:
            self.files = repo_files
            # Auto-open the first flagged file (or first file if none flagged)
            first = next(
                (item for item in file_analyses
                 if item.get("content") and (item.get("errors") or item.get("style_score", 100) < 70)),
                next((item for item in file_analyses if item.get("content")), None),
            )
            if first:
                self.current_file = first["filename"]
                self.code = first["content"]
                # Detect language from extension
                ext = first["filename"].rsplit(".", 1)[-1].lower() if "." in first["filename"] else ""
                self.language = {
                    "py": "python", "js": "javascript", "ts": "typescript",
                    "jsx": "javascript", "tsx": "typescript", "java": "java",
                    "cpp": "cpp", "c": "c", "go": "go", "rs": "rust",
                    "rb": "ruby", "php": "php", "cs": "csharp", "swift": "swift",
                }.get(ext, "python")

        self.repo_scan_progress = (
            f"Static analysis done — {flagged_count} flagged, {clean_count} clean."
            + (" (Repo truncated at 200 files)" if truncated else "")
            + f"\n\nSending {len(triage['gemini_targets'])} flagged files to AI..."
        )
        yield

        # Step 4: Gemini on flagged files only
        gemini_parts = []
        for idx, target in enumerate(triage["gemini_targets"]):
            self.repo_scan_progress = (
                f"Getting AI analysis for flagged file {idx + 1}/{len(triage['gemini_targets'])}: "
                f"{target['filename']}..."
            )
            yield

            suggestions = await get_optimization_suggestions(
                target["content"][:4000],
                target["errors"][:10],
                [],  # style_issues passed separately to save tokens
                target["ast_info"],
            )
            gemini_parts.append(
                f"## 📄 `{target['path']}`\n"
                f"> Complexity: {target['complexity']} | "
                f"Errors: {target['error_count']} | "
                f"Style: {target['style_score']}/100\n\n"
                f"{suggestions}\n\n---\n"
            )

        self.repo_scan_gemini_output = "\n".join(gemini_parts) if gemini_parts else ""
        self.repo_scan_progress = (
            f"✅ Repo scan complete — {total} files analyzed, "
            f"{flagged_count} flagged, "
            f"{len(triage['gemini_targets'])} AI-reviewed."
        )
        self.is_repo_scanning = False
        self._notify(
            f"Repo scan done: {flagged_count}/{total} files flagged for review.",
            "success" if flagged_count == 0 else "info",
        )

    def load_repo_file_into_editor(self, path: str):
        """Load a repo scan file into the editor — find it in self.files by filename."""
        # Find the matching scan result to get the filename
        target_filename = None
        for item in self.repo_scan_results:
            if item["path"] == path:
                target_filename = item["filename"]
                break

        if not target_filename:
            return

        # Find the actual code in self.files (populated during scan)
        for f in self.files:
            if f["name"] == target_filename:
                self.current_file = target_filename
                self.code = f["code"]
                # Detect language from extension
                ext = target_filename.rsplit(".", 1)[-1].lower() if "." in target_filename else ""
                self.language = {
                    "py": "python", "js": "javascript", "ts": "typescript",
                    "jsx": "javascript", "tsx": "typescript", "java": "java",
                    "cpp": "cpp", "c": "c", "go": "go", "rs": "rust",
                    "rb": "ruby", "php": "php", "cs": "csharp", "swift": "swift",
                }.get(ext, "python")
                self._notify(
                    f"'{target_filename}' opened — click 🔍 Analyze to run full analysis.",
                    "success",
                )
                return

        # File wasn't fetched (e.g., fetch error during scan)
        self._notify(f"Could not load '{target_filename}' — it may have failed to fetch.", "error")

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _notify(self, message: str, ntype: str = "info"):
        self.notification = message
        self.notification_type = ntype
