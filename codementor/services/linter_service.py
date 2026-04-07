"""
Language-aware linting service.
Python: pyflakes + pycodestyle + radon (complexity) + bandit (security).
Other languages: basic structural checks.
"""

import re
import json
import tempfile
import os
import subprocess

import pyflakes.api
import pyflakes.messages
import pycodestyle

try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit
    HAS_RADON = True
except ImportError:
    HAS_RADON = False

try:
    import bandit  # noqa: F401 — just check it's installed
    HAS_BANDIT = True
except ImportError:
    HAS_BANDIT = False


# ─── Python error detection (pyflakes) ───────────────────────────────────────

class _FlakesReporter:
    SEVERITY_MAP = {
        pyflakes.messages.UndefinedName: "error",
        pyflakes.messages.UndefinedLocal: "error",
        pyflakes.messages.DuplicateArgument: "error",
        pyflakes.messages.ReturnOutsideFunction: "error",
        pyflakes.messages.BreakOutsideLoop: "error",
        pyflakes.messages.ContinueOutsideLoop: "error",
        pyflakes.messages.UnusedImport: "warning",
        pyflakes.messages.ImportShadowedByLoopVar: "warning",
        pyflakes.messages.RedefinedWhileUnused: "warning",
        pyflakes.messages.UnusedVariable: "warning",
    }

    def __init__(self):
        self.issues: list[dict] = []

    def unexpectedError(self, filename, msg):
        self.issues.append({"line": 0, "col": 0, "code": "E999",
                            "message": f"Unexpected error: {msg}",
                            "severity": "error", "category": "error"})

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.issues.append({"line": lineno or 0, "col": offset or 0,
                            "code": "E999", "message": f"SyntaxError: {msg}",
                            "severity": "error", "category": "error"})

    def flake(self, message):
        severity = self.SEVERITY_MAP.get(type(message), "info")
        self.issues.append({
            "line": message.lineno,
            "col": message.col + 1 if hasattr(message, "col") else 1,
            "code": type(message).__name__,
            "message": str(message.message % message.message_args),
            "severity": severity,
            "category": "error",
        })


# ─── Python style (pycodestyle) ──────────────────────────────────────────────

class _StyleCollector(pycodestyle.BaseReport):
    def __init__(self, options):
        super().__init__(options)
        self.issues: list[dict] = []

    def error(self, line_number, offset, text, check):
        code = text[:4]
        super().error(line_number, offset, text, check)
        self.issues.append({
            "line": line_number, "col": offset + 1, "code": code,
            "message": text[5:].strip(),
            "severity": "error" if code.startswith("E") else "warning",
            "category": "style",
        })


# ─── Generic checks for non-Python languages ─────────────────────────────────

def _generic_checks(code: str, language: str) -> list[dict]:
    """Basic static checks valid for any C-style or brace-based language."""
    issues = []
    lines = code.splitlines()

    # Long lines
    max_len = 120
    for i, line in enumerate(lines, 1):
        if len(line) > max_len:
            issues.append({
                "line": i, "col": max_len + 1,
                "code": "LINE_LEN",
                "message": f"Line too long ({len(line)} > {max_len} chars)",
                "severity": "warning", "category": "style",
            })

    # Trailing whitespace
    for i, line in enumerate(lines, 1):
        if line != line.rstrip():
            issues.append({
                "line": i, "col": len(line.rstrip()) + 1,
                "code": "TRAIL_WS",
                "message": "Trailing whitespace",
                "severity": "warning", "category": "style",
            })

    # Unbalanced brackets (very basic)
    opens = {"(": 0, "[": 0, "{": 0}
    closes = {")": "(", "]": "[", "}": "{"}
    in_string = False
    string_char = ""
    for ch in code:
        if in_string:
            if ch == string_char:
                in_string = False
        elif ch in ('"', "'"):
            in_string = True
            string_char = ch
        elif ch in opens:
            opens[ch] += 1
        elif ch in closes:
            opens[closes[ch]] -= 1

    for bracket, count in opens.items():
        if count != 0:
            issues.append({
                "line": 0, "col": 0, "code": "UNBALANCED",
                "message": f"Unbalanced bracket '{bracket}' (net: {count:+d})",
                "severity": "error", "category": "error",
            })

    # TODO/FIXME markers
    for i, line in enumerate(lines, 1):
        stripped = line.strip().upper()
        for marker in ("TODO", "FIXME", "HACK", "XXX"):
            if marker in stripped:
                issues.append({
                    "line": i, "col": 1, "code": marker,
                    "message": f"{marker} marker found",
                    "severity": "info", "category": "style",
                })
                break

    return issues[:50]  # cap


def _js_ts_checks(code: str) -> list[dict]:
    """JavaScript / TypeScript specific checks."""
    issues = list(_generic_checks(code, "javascript"))
    lines = code.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # var usage (prefer let/const)
        if re.match(r"^\s*var\s+", line):
            issues.append({
                "line": i, "col": 1, "code": "NO_VAR",
                "message": "Prefer 'let' or 'const' over 'var'",
                "severity": "warning", "category": "style",
            })
        # console.log left in
        if "console.log(" in stripped:
            issues.append({
                "line": i, "col": line.index("console.log(") + 1,
                "code": "CONSOLE_LOG",
                "message": "console.log() found — remove before production",
                "severity": "info", "category": "style",
            })
        # == instead of ===
        if re.search(r"[^=!<>]==[^=]", stripped):
            issues.append({
                "line": i, "col": 1, "code": "LOOSE_EQ",
                "message": "Use '===' (strict equality) instead of '=='",
                "severity": "warning", "category": "style",
            })
    return issues


# ─── Radon: Cyclomatic Complexity ────────────────────────────────────────────

# Rank guide: A=1-5 (simple), B=6-10 (moderate), C=11-15, D=16-20, E=21-25, F=26+
_COMPLEXITY_THRESHOLD = 5  # flag B and above (complexity > 5, rank B-F)

def check_complexity(code: str) -> list[dict]:
    """Return list of functions/methods with high cyclomatic complexity (rank B+)."""
    if not HAS_RADON or not code.strip():
        return []
    try:
        blocks = cc_visit(code)
        flagged = []
        for b in blocks:
            if b.complexity > _COMPLEXITY_THRESHOLD:
                rank = b.rank  # A–F
                flagged.append({
                    "line": b.lineno,
                    "col": 1,
                    "code": f"CC-{rank}",
                    "message": (
                        f"'{b.name}' has cyclomatic complexity {b.complexity} "
                        f"(rank {rank}) — consider refactoring"
                    ),
                    "severity": "error" if b.complexity > 20 else "warning",
                    "category": "complexity",
                    "name": b.name,
                    "complexity": b.complexity,
                    "rank": rank,
                })
        return sorted(flagged, key=lambda x: -x["complexity"])
    except Exception:
        return []


def get_maintainability_index(code: str) -> int:
    """Return Maintainability Index (0–100). Higher = easier to maintain."""
    if not HAS_RADON or not code.strip():
        return 100
    try:
        mi = mi_visit(code, multi=True)
        return max(0, min(100, round(mi)))
    except Exception:
        return 100


# ─── Bandit: Security Vulnerability Scanner ──────────────────────────────────

def check_security(code: str) -> list[dict]:
    """Run bandit on Python code and return security issues."""
    if not HAS_BANDIT or not code.strip():
        return []
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", tmp],
                capture_output=True,
                text=True,
                timeout=15,
            )
            raw = result.stdout.strip()
            if not raw:
                return []
            data = json.loads(raw)
            issues = []
            for r in data.get("results", []):
                sev = r.get("issue_severity", "LOW").upper()
                issues.append({
                    "line": r.get("line_number", 0),
                    "col": 1,
                    "code": r.get("test_id", "B000"),
                    "message": r.get("issue_text", "Security issue"),
                    "severity": "error" if sev in ("HIGH", "MEDIUM") else "warning",
                    "category": "security",
                    "bandit_severity": sev,
                    "bandit_confidence": r.get("issue_confidence", "LOW").upper(),
                    "cwe": r.get("issue_cwe", {}).get("id", ""),
                })
            return sorted(issues, key=lambda x: x["line"])
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return []


# ─── Public API ───────────────────────────────────────────────────────────────

def check_errors(code: str, language: str = "python") -> list[dict]:
    if not code.strip():
        return []
    if language == "python":
        reporter = _FlakesReporter()
        pyflakes.api.check(code, filename="<code>", reporter=reporter)
        return sorted(reporter.issues, key=lambda x: x["line"])
    if language in ("javascript", "typescript"):
        return [i for i in _js_ts_checks(code) if i["category"] == "error"]
    return [i for i in _generic_checks(code, language) if i["category"] == "error"]


def check_style(code: str, language: str = "python") -> dict:
    if not code.strip():
        return {"issues": [], "score": 100}

    if language == "python":
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name
        try:
            checker = pycodestyle.Checker(
                temp_file, reporter=_StyleCollector,
                max_line_length=100, show_source=False, show_pep8=False,
            )
            checker.check_all()
            issues = checker.report.issues
        finally:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
    elif language in ("javascript", "typescript"):
        issues = _js_ts_checks(code)
    else:
        issues = _generic_checks(code, language)

    total_lines = max(len(code.splitlines()), 1)
    penalty = min(len(issues) * 3, 100)
    score = max(0, 100 - penalty)
    return {"issues": sorted(issues, key=lambda x: x["line"]), "score": score}


def get_linter_summary(errors: list[dict], style_issues: list[dict]) -> str:
    lines = []
    if errors:
        lines.append(f"Errors/Warnings ({len(errors)}):")
        for e in errors[:10]:
            lines.append(f"  Line {e['line']}: [{e['code']}] {e['message']}")
    if style_issues:
        lines.append(f"Style Issues ({len(style_issues)}):")
        for s in style_issues[:10]:
            lines.append(f"  Line {s['line']}: [{s['code']}] {s['message']}")
    return "\n".join(lines) if lines else "No issues found."
