"""
Language-aware error detection and style analysis.

Errors
  • Python            → pyflakes (undefined names, unused imports, syntax)
  • JSON/YAML/TOML/XML → real parsers (exact error location)
  • Any language       → native compiler/linter when installed on the server
                         (gcc/clang, g++, javac, node, tsc, gofmt, rustc, php,
                         ruby, bash) — otherwise tree-sitter syntax analysis
Style
  • Python            → pycodestyle (PEP 8)
  • Every language    → universal rules + per-language rules (JS/TS, Java,
                         C/C++, Go, PHP, Kotlin, C# …)

Compatibility: check_complexity / check_security / get_maintainability_index
are re-exported so existing imports keep working.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile

import pyflakes.api
import pyflakes.messages
import pycodestyle

from codementor.services import languages, syntax_service
from codementor.services.complexity_service import (  # noqa: F401 — re-exports
    check_complexity as _check_complexity,
    maintainability_index as _maintainability_index,
)
from codementor.services.security_service import check_security as _check_security


# ─── Python error detection (pyflakes) ───────────────────────────────────────

class _FlakesReporter:
    SEVERITY_MAP = {
        pyflakes.messages.UndefinedName: "error",
        pyflakes.messages.UndefinedLocal: "error",
        pyflakes.messages.DuplicateArgument: "error",
        pyflakes.messages.ReturnOutsideFunction: "error",
        pyflakes.messages.UnusedImport: "warning",
        pyflakes.messages.ImportShadowedByLoopVar: "warning",
        pyflakes.messages.RedefinedWhileUnused: "warning",
        pyflakes.messages.UnusedVariable: "warning",
    }
    # Names differ across pyflakes versions — add the ones that exist
    for _name in ("BreakOutsideLoop", "ContinueOutsideLoop"):
        if hasattr(pyflakes.messages, _name):
            SEVERITY_MAP[getattr(pyflakes.messages, _name)] = "error"

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


def _python_errors(code: str) -> list[dict]:
    reporter = _FlakesReporter()
    pyflakes.api.check(code, filename="<code>", reporter=reporter)
    return reporter.issues


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
            "severity": "warning" if code.startswith(("E", "W")) else "info",
            "category": "style",
        })


def _python_style(code: str) -> list[dict]:
    lines = code.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    checker = pycodestyle.Checker(
        filename="<code>", lines=lines, reporter=_StyleCollector,
        max_line_length=100, show_source=False, show_pep8=False,
    )
    checker.check_all()
    return checker.report.issues


# ─── Data-format validation ──────────────────────────────────────────────────

def _issue(line, col, code, message, severity="error", category="error", **extra) -> dict:
    return {"line": int(line or 0), "col": int(col or 0), "code": code, "message": message,
            "severity": severity, "category": category, **extra}


def _data_errors(code: str, lang_id: str) -> list[dict] | None:
    if lang_id == "json":
        import json
        try:
            json.loads(code)
            return []
        except json.JSONDecodeError as e:
            return [_issue(e.lineno, e.colno, "JSON", e.msg)]
    if lang_id == "yaml":
        try:
            import yaml
        except ImportError:
            return None
        try:
            list(yaml.safe_load_all(code))
            return []
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            msg = getattr(e, "problem", None) or str(e).splitlines()[0]
            return [_issue(mark.line + 1 if mark else 0, mark.column + 1 if mark else 0, "YAML", msg)]
    if lang_id == "toml":
        try:
            import tomllib
        except ImportError:
            return None
        try:
            tomllib.loads(code)
            return []
        except Exception as e:
            m = re.search(r"line (\d+), column (\d+)", str(e))
            return [_issue(m.group(1) if m else 0, m.group(2) if m else 0, "TOML", str(e))]
    if lang_id == "xml":
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(code)
            return []
        except ET.ParseError as e:
            line, col = getattr(e, "position", (0, 0))
            return [_issue(line, col + 1, "XML", str(e).split(":")[0])]
    return None


# ─── Native toolchains (used when installed on the server) ──────────────────

_GCC_LINE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
    r"(?P<sev>fatal error|error|warning)(?:\[(?P<code>[^\]]+)\])?:\s*(?P<msg>.+)$", re.M)
_TSC_LINE = re.compile(r"^.+?\((?P<line>\d+),(?P<col>\d+)\): (?P<sev>error|warning) (?P<code>TS\d+): (?P<msg>.+)$", re.M)
_JAVAC_LINE = re.compile(r"^[^:\n]+\.java:(?P<line>\d+): (?P<sev>error|warning): (?P<msg>.+)$", re.M)
_PHP_LINE = re.compile(r"(?:PHP )?(?P<sev>Parse error|Fatal error|Warning):\s*(?P<msg>.+?) in .+? on line (?P<line>\d+)")
_BASH_LINE = re.compile(r"^.+?: line (?P<line>\d+): (?P<msg>.+)$", re.M)
_RUBY_LINE = re.compile(r"^.+?\.rb:(?P<line>\d+): (?P<sev>warning: )?(?P<msg>.+)$", re.M)
_NODE_LINE = re.compile(r"^.+?:(?P<line>\d+)\n(?:.*\n){0,3}?(?P<msg>SyntaxError: .+)$", re.M)
_GOFMT_LINE = re.compile(r"^[^:\n]+:(?P<line>\d+):(?P<col>\d+): (?P<msg>.+)$", re.M)

# Errors caused only by missing project context (headers, packages, deps)
_CONTEXT_NOISE = re.compile(
    r"file not found|No such file|does not exist|cannot find symbol|cannot find module|"
    r"unresolved import|could not find|can't find crate|use of undeclared crate|"
    r"Cannot find name|has no exported member|Cannot find module", re.I)


def _which(*names: str) -> str | None:
    for n in names:
        path = shutil.which(n)
        if path:
            return path
    return None


def _run_tool(cmd: list[str], cwd: str, timeout: int = 15) -> str:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": cwd, "LANG": "C.UTF-8",
           "GOCACHE": os.path.join(cwd, ".gocache")}
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return (res.stderr or "") + "\n" + (res.stdout or "")
    except Exception:
        return ""


_NATIVE_TOOLS = {
    "c": ("gcc", "clang"), "cpp": ("g++", "clang++"), "javascript": ("node",),
    "typescript": ("tsc",), "java": ("javac",), "go": ("gofmt",), "rust": ("rustc",),
    "php": ("php",), "ruby": ("ruby",), "bash": ("bash",),
}


def native_tool(lang_id: str) -> str:
    """Name of the native checker that will run for this language ('' if none installed)."""
    tool = _which(*_NATIVE_TOOLS.get(lang_id, ()))
    return os.path.basename(tool) if tool else ""


def _java_filename(code: str) -> str:
    m = re.search(r"\bpublic\s+(?:final\s+|abstract\s+|sealed\s+)*(?:class|interface|enum|record)\s+(\w+)", code)
    return f"{m.group(1) if m else 'Main'}.java"


def _native_errors(code: str, lang_id: str) -> list[dict] | None:
    """Run the language's own compiler/linter if available. None if not installed."""
    plan = {
        "c": (("gcc", "clang"), "main.c", lambda t, f: [t, "-fsyntax-only", "-Wall", "-Wextra", "-std=c17", f]),
        "cpp": (("g++", "clang++"), "main.cpp", lambda t, f: [t, "-fsyntax-only", "-Wall", "-Wextra", "-std=c++20", f]),
        "javascript": (("node",), "main.mjs", lambda t, f: [t, "--check", f]),
        "typescript": (("tsc",), "main.ts", lambda t, f: [t, "--noEmit", "--pretty", "false", "--strict",
                                                          "--target", "es2022", "--skipLibCheck", f]),
        "java": (("javac",), None, lambda t, f: [t, "-Xlint:all", "-d", "out", f]),
        "go": (("gofmt",), "main.go", lambda t, f: [t, "-e", "-l", f]),
        "rust": (("rustc",), "main.rs", lambda t, f: [t, "--edition", "2021", "--error-format=short",
                                                      "--emit=metadata", "--crate-type",
                                                      "bin" if re.search(r"\bfn\s+main\s*\(", code) else "lib",
                                                      "-o", "out.rmeta", f]),
        "php": (("php",), "main.php", lambda t, f: [t, "-l", f]),
        "ruby": (("ruby",), "main.rb", lambda t, f: [t, "-wc", f]),
        "bash": (("bash",), "main.sh", lambda t, f: [t, "-n", f]),
    }.get(lang_id)
    if not plan:
        return None
    tools, fname, build = plan
    tool = _which(*tools)
    if not tool:
        return None
    if lang_id == "java":
        fname = _java_filename(code)

    with tempfile.TemporaryDirectory(prefix="cm-lint-") as tmp:
        path = os.path.join(tmp, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        if lang_id == "java":
            os.makedirs(os.path.join(tmp, "out"), exist_ok=True)
        output = _run_tool(build(tool, fname), tmp)

    issues: list[dict] = []
    src = os.path.basename(tool)
    if lang_id in ("c", "cpp", "rust"):
        for m in _GCC_LINE.finditer(output):
            sev = "error" if "error" in m.group("sev") else "warning"
            issues.append(_issue(m.group("line"), m.group("col") or 1, m.group("code") or sev.upper(),
                                 m.group("msg").strip(), sev, source=src))
    elif lang_id == "typescript":
        for m in _TSC_LINE.finditer(output):
            issues.append(_issue(m.group("line"), m.group("col"), m.group("code"),
                                 m.group("msg").strip(), m.group("sev"), source=src))
    elif lang_id == "java":
        for m in _JAVAC_LINE.finditer(output):
            issues.append(_issue(m.group("line"), 1, "JAVAC", m.group("msg").strip(), m.group("sev"), source=src))
    elif lang_id == "php":
        for m in _PHP_LINE.finditer(output):
            sev = "warning" if m.group("sev") == "Warning" else "error"
            issues.append(_issue(m.group("line"), 1, "PHP", m.group("msg").strip(), sev, source=src))
    elif lang_id == "bash":
        for m in _BASH_LINE.finditer(output):
            issues.append(_issue(m.group("line"), 1, "BASH", m.group("msg").strip(), source=src))
    elif lang_id == "ruby":
        for m in _RUBY_LINE.finditer(output):
            if "Syntax OK" in m.group("msg"):
                continue
            sev = "warning" if m.group("sev") else "error"
            issues.append(_issue(m.group("line"), 1, "RUBY", m.group("msg").strip(), sev, source=src))
    elif lang_id == "javascript":
        for m in _NODE_LINE.finditer(output):
            issues.append(_issue(m.group("line"), 1, "SYNTAX", m.group("msg").strip(), source=src))
    elif lang_id == "go":
        for m in _GOFMT_LINE.finditer(output):
            issues.append(_issue(m.group("line"), m.group("col"), "SYNTAX", m.group("msg").strip(), source=src))

    # Missing headers / packages aren't the user's bug in a single-file view
    for issue in issues:
        if _CONTEXT_NOISE.search(issue["message"]):
            issue["severity"] = "info"
            issue["message"] += " (needs project context)"
    return issues


# ─── Fallback when no grammar/toolchain exists ───────────────────────────────

_STRING_RE = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`')


def _strip_strings(line: str) -> str:
    return _STRING_RE.sub('""', line)


def _strip_comments(code: str, lang_id: str) -> str:
    prefixes = languages.get(lang_id).comment
    code = re.sub(r"/\*[\s\S]*?\*/", lambda m: "\n" * m.group(0).count("\n"), code) \
        if "//" in prefixes else code
    out = []
    for line in code.splitlines():
        line = _strip_strings(line)
        for p in prefixes:
            idx = line.find(p)
            if idx >= 0:
                line = line[:idx]
        out.append(line)
    return "\n".join(out)


def _bracket_errors(code: str, lang_id: str) -> list[dict]:
    """Comment/string-aware bracket balance check (last-resort syntax check)."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    for lineno, line in enumerate(_strip_comments(code, lang_id).splitlines(), 1):
        for ch in line:
            if ch in "([{":
                stack.append((ch, lineno))
            elif ch in pairs:
                if stack and stack[-1][0] == pairs[ch]:
                    stack.pop()
                else:
                    return [_issue(lineno, 1, "UNBALANCED", f"Unexpected closing '{ch}'")]
    if stack:
        ch, lineno = stack[-1]
        return [_issue(lineno, 1, "UNBALANCED", f"Unclosed '{ch}'")]
    return []


# ─── Style rules ─────────────────────────────────────────────────────────────

_EMPTY_CATCH = re.compile(r"\bcatch\s*(\([^)]*\))?\s*\{\s*\}")

# (rule id, language ids, regex applied to string-stripped line, message, severity)
_STYLE_RULES = [
    ("NO_VAR", ("javascript", "typescript"), re.compile(r"^\s*var\s+"), "Prefer 'let' or 'const' over 'var'", "warning"),
    ("LOOSE_EQ", ("javascript", "typescript"), re.compile(r"[^=!<>]==[^=]|!=[^=]"), "Use strict equality (===/!==)", "warning"),
    ("CONSOLE", ("javascript", "typescript"), re.compile(r"\bconsole\.(log|debug)\("), "console.log() left in code", "info"),
    ("DEBUGGER", ("javascript", "typescript"), re.compile(r"^\s*debugger\s*;?\s*$"), "debugger statement left in code", "warning"),
    ("TS_ANY", ("typescript",), re.compile(r":\s*any\b|<any>|as any\b"), "Avoid 'any' — it disables type checking", "info"),
    ("SYSOUT", ("java",), re.compile(r"System\.(out|err)\.print"), "Use a logger instead of System.out", "info"),
    ("STR_EQ", ("java",), re.compile(r'""\s*==|==\s*""'), "Compare strings with .equals(), not ==", "warning"),
    ("NS_STD", ("cpp",), re.compile(r"^\s*using\s+namespace\s+std\s*;"), "'using namespace std' pollutes the global namespace", "info"),
    ("NULL_CPP", ("cpp",), re.compile(r"\bNULL\b"), "Prefer nullptr over NULL in C++", "info"),
    ("GOTO", ("c", "cpp", "csharp", "php"), re.compile(r"^\s*goto\s+\w+"), "goto makes control flow hard to follow", "info"),
    ("PANIC", ("go",), re.compile(r"\bpanic\("), "panic() — return an error instead where possible", "info"),
    ("ERR_IGNORED", ("go",), re.compile(r"^\s*_\s*(,\s*_)?\s*=\s*\w+[\w.]*\("), "Error return value ignored", "warning"),
    ("BANG_BANG", ("kotlin",), re.compile(r"!!"), "!! throws on null — prefer ?. or ?: ", "info"),
    ("PHP_LOOSE", ("php",), re.compile(r"[^=!<>]==[^=]"), "Loose comparison (==) — prefer ===", "info"),
    ("SELECT_STAR", ("sql",), re.compile(r"(?i)\bselect\s+\*"), "Avoid SELECT * — list the columns you need", "info"),
    ("PRINT_DBG", ("rust",), re.compile(r"\bdbg!\("), "dbg! macro left in code", "warning"),
]


def _universal_style(code: str, lang_id: str) -> list[dict]:
    issues = []
    lines = code.splitlines()
    max_len = 120
    tab_lines = space_lines = 0
    for i, line in enumerate(lines, 1):
        if len(line) > max_len and lang_id not in ("markdown", "text", "json"):
            issues.append(_issue(i, max_len + 1, "LINE_LEN", f"Line too long ({len(line)} > {max_len})",
                                 "warning", "style"))
        if line != line.rstrip():
            issues.append(_issue(i, len(line.rstrip()) + 1, "TRAIL_WS", "Trailing whitespace", "info", "style"))
        if line.startswith("\t"):
            tab_lines += 1
        elif line.startswith("    "):
            space_lines += 1
        upper = line.upper()
        for marker in ("TODO", "FIXME", "HACK", "XXX"):
            if re.search(rf"\b{marker}\b", upper):
                issues.append(_issue(i, 1, marker, f"{marker} marker found", "info", "style"))
                break
    if tab_lines and space_lines and lang_id not in ("go", "makefile"):
        issues.append(_issue(0, 0, "MIXED_INDENT",
                             f"Mixed indentation: {tab_lines} lines use tabs, {space_lines} use spaces",
                             "warning", "style"))
    if len(lines) > 1000:
        issues.append(_issue(0, 0, "FILE_LEN", f"File is {len(lines)} lines — consider splitting it",
                             "info", "style"))
    return issues


def _language_style(code: str, lang_id: str) -> list[dict]:
    issues = []
    rules = [r for r in _STYLE_RULES if lang_id in r[1]]
    check_catch = lang_id in ("java", "javascript", "typescript", "csharp", "kotlin", "php",
                              "swift", "dart", "scala", "cpp")
    in_block_comment = False
    prefixes = languages.get(lang_id).comment
    for i, raw in enumerate(code.splitlines(), 1):
        s = raw.strip()
        if in_block_comment:
            in_block_comment = "*/" not in s
            continue
        if s.startswith("/*"):
            in_block_comment = "*/" not in s
            continue
        if prefixes and s.startswith(prefixes):
            continue
        line = _strip_strings(raw)
        for rule_id, _, rx, msg, sev in rules:
            m = rx.search(line)
            if m:
                issues.append(_issue(i, m.start() + 1, rule_id, msg, sev, "style"))
        if check_catch and _EMPTY_CATCH.search(line):
            issues.append(_issue(i, 1, "EMPTY_CATCH", "Empty catch block silently swallows errors",
                                 "warning", "style"))
    return issues


# ─── Scoring ─────────────────────────────────────────────────────────────────

_STYLE_WEIGHT = {"error": 2.0, "warning": 1.0, "info": 0.25}


def style_score(issues: list[dict], line_count: int) -> int:
    """
    0–100 score based on weighted issue density per 100 lines, so a long file
    isn't punished for its size and a 5-line snippet can't hide 10 issues.
    """
    weighted = sum(_STYLE_WEIGHT.get(i.get("severity", "info"), 0.5) for i in issues)
    density = weighted / max(line_count, 20) * 100
    return max(0, min(100, round(100 * math.exp(-density / 40))))


# ─── Public API ──────────────────────────────────────────────────────────────

def check_errors(code: str, language: str = "python", filename: str = "",
                 allow_native: bool = True) -> list[dict]:
    """Errors & warnings for any language (see module docstring for tools)."""
    if not code.strip():
        return []
    lang_id = languages.normalize(language)

    if lang_id == "python":
        return sorted(_python_errors(code), key=lambda x: x["line"])

    data = _data_errors(code, lang_id)
    if data is not None:
        return data

    lang = languages.get(lang_id)
    if lang.kind == "docs":
        return []

    if filename.endswith((".jsx", ".tsx")):
        allow_native = False  # node/tsc single-file checks don't understand JSX here
    native = _native_errors(code, lang_id) if allow_native else None
    if native:
        return sorted(native, key=lambda x: (x["line"], x["col"]))

    ts = syntax_service.syntax_errors(code, lang_id, filename)
    if ts is not None:
        # native ran clean (native == []) → trust it over tree-sitter's grammar
        if native == [] and ts:
            return []
        return ts

    if native is not None:
        return native
    if lang.comment and ("//" in lang.comment or lang_id in ("ruby", "bash", "perl", "r", "lua")):
        return _bracket_errors(code, lang_id)
    return []


def check_style(code: str, language: str = "python") -> dict:
    if not code.strip():
        return {"issues": [], "score": 100}
    lang_id = languages.normalize(language)
    if lang_id == "python":
        issues = _python_style(code)
        issues += [i for i in _universal_style(code, lang_id) if i["code"] in ("TODO", "FIXME", "HACK", "XXX", "FILE_LEN")]
    else:
        issues = _universal_style(code, lang_id) + _language_style(code, lang_id)
    issues = sorted(issues, key=lambda x: x["line"])[:200]
    return {"issues": issues, "score": style_score(issues, len(code.splitlines()))}


# ─── Backwards-compatible wrappers ───────────────────────────────────────────

def check_complexity(code: str, language: str = "python") -> list[dict]:
    return _check_complexity(code, language)


def check_security(code: str, language: str = "python") -> list[dict]:
    return _check_security(code, language)


def get_maintainability_index(code: str, language: str = "python") -> int:
    return _maintainability_index(code, language)


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
