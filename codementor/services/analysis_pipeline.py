"""
Unified static-analysis pipeline.

One entry point — `analyze_source()` — used by BOTH the single-file Analyze
button and the GitHub repo scanner, so every language gets the same treatment
everywhere:

    language ─► structure ─► errors ─► style ─► complexity ─► security ─► MI ─► CFG
                (ast/TS)     (native/   (pycodestyle/ (radon/    (bandit/
                              pyflakes/  rule packs)   lizard)    rule pack)
                              TS/data)

Pure, synchronous, CPU-bound: callers run it in a worker thread.
"""

from __future__ import annotations

import re
from typing import Any

from codementor.services import languages, syntax_service
from codementor.services.ast_analyzer import analyze_ast
from codementor.services.cfg_service import build_cfg
from codementor.services.complexity_service import (
    HAS_LIZARD, HAS_RADON, check_complexity, function_metrics, maintainability_index,
)
from codementor.services.linter_service import check_errors, check_style, native_tool
from codementor.services.security_service import HAS_BANDIT, check_security

_SYNTAX_CODES = {"E999", "SYNTAX", "JSON", "YAML", "TOML", "XML", "UNBALANCED"}
_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+[\w.{}*, ]+|from\s+[\w.]+\s+import|#include\s*[<\"][^>\"]+[>\"]|"
    r"using\s+[\w.]+;|use\s+[\w:]+|require(?:_relative)?\s*\(?['\"][^'\"]+['\"]|"
    r"(?:const|let|var)\s+\w+\s*=\s*require\(['\"][^'\"]+['\"]\))", re.M)


def resolve_language(code: str, language: str, filename: str = "") -> str:
    """Normalize the requested language; auto-detect when unknown or 'auto'."""
    lang = languages.normalize(language)
    if lang in ("", "auto") or lang not in languages.LANGUAGES:
        return languages.detect(code, filename, fallback="text")
    return lang


def _structure(code: str, lang: str, filename: str, metrics: list[dict]) -> dict[str, Any]:
    line_count = len(code.splitlines())
    if lang == "python":
        info = analyze_ast(code)
    else:
        info = {"syntax_ok": True, "syntax_error": None, "functions": [], "classes": [],
                "imports": [], "complexity": 0, "line_count": line_count, "node_count": 0}
        ts = syntax_service.extract_structure(code, lang, filename) if languages.is_code(lang) or \
            languages.get(lang).kind == "markup" else None
        if ts:
            info.update(ts)
        if metrics:
            # lizard knows parameters + complexity; prefer it for the function list
            info["functions"] = [{
                "name": m["name"], "lineno": m["lineno"], "args": [], "class": None,
                "decorators": [], "docstring": "", "line_count": m.get("nloc", 0),
                "complexity": m["complexity"],
            } for m in metrics]
        if not info["imports"]:
            info["imports"] = sorted({m.group(0).strip()[:80] for m in _IMPORT_RE.finditer(code)})[:40]
    info["line_count"] = line_count
    info["max_complexity"] = max((m["complexity"] for m in metrics), default=0)
    if lang != "python":
        info["complexity"] = sum(m["complexity"] for m in metrics) if metrics else 0
    return info


def analyze_source(code: str, language: str = "auto", filename: str = "", *,
                   native: bool = True, include_cfg: bool = True) -> dict[str, Any]:
    """
    Run the full static pipeline. Never raises; each stage fails independently.

    Returns:
      language, language_label, ast_info, errors, style_issues, style_score,
      security, complexity, maintainability_index, cfg, tools, line_count
    """
    lang = resolve_language(code, language, filename)
    result: dict[str, Any] = {
        "language": lang, "language_label": languages.label(lang),
        "ast_info": {}, "errors": [], "style_issues": [], "style_score": 100,
        "security": [], "complexity": [], "maintainability_index": 100,
        "cfg": {"image": "", "mermaid": "", "functions": [], "summary": "", "error": "", "engine": ""},
        "tools": [], "line_count": len(code.splitlines()), "stage_errors": [],
    }
    if not code.strip():
        return result

    def stage(name, fn, default):
        try:
            return fn()
        except Exception as exc:  # isolate failures per stage
            result["stage_errors"].append(f"{name}: {exc}")
            return default

    is_code = languages.is_code(lang)
    metrics = stage("metrics", lambda: function_metrics(code, lang), []) if is_code else []
    result["ast_info"] = stage("structure", lambda: _structure(code, lang, filename, metrics), {})
    result["errors"] = stage("errors", lambda: check_errors(code, lang, filename, allow_native=native), [])
    style = stage("style", lambda: check_style(code, lang), {"issues": [], "score": 100})
    result["style_issues"], result["style_score"] = style["issues"], style["score"]
    if is_code or lang in ("html", "vue", "svelte", "yaml", "json", "toml", "hcl"):
        result["security"] = stage("security", lambda: check_security(code, lang), [])
    if is_code:
        result["complexity"] = stage("complexity", lambda: check_complexity(code, lang, metrics), [])
        result["maintainability_index"] = stage("mi", lambda: maintainability_index(code, lang, metrics), 100)
    if include_cfg:
        result["cfg"] = stage("cfg", lambda: build_cfg(code, lang, filename), result["cfg"])

    syntax_errors = [e for e in result["errors"] if e.get("code") in _SYNTAX_CODES and e["severity"] == "error"]
    if result["ast_info"] is not None and syntax_errors:
        result["ast_info"]["syntax_ok"] = False
        first = syntax_errors[0]
        result["ast_info"]["syntax_error"] = result["ast_info"].get("syntax_error") or {
            "message": first["message"], "lineno": first["line"], "offset": first["col"], "text": ""}

    result["tools"] = _tools_used(lang, result, native, filename)
    return result


def _tools_used(lang: str, result: dict, native: bool = False, filename: str = "") -> list[str]:
    tools: list[str] = []
    if lang == "python":
        tools += ["pyflakes", "pycodestyle", "python-ast"]
        if HAS_RADON:
            tools.append("radon")
        if HAS_BANDIT:
            tools.append("bandit")
    else:
        sources = {e.get("source") for e in result["errors"] if e.get("source")}
        if native and not filename.endswith((".jsx", ".tsx")) and (tool := native_tool(lang)):
            sources.add(tool)
        tools += sorted(s for s in sources if s)
        if lang in ("json", "yaml", "toml", "xml"):
            tools.append(f"{lang}-parser")
        elif syntax_service.has_grammar(lang):
            if "tree-sitter" not in tools:
                tools.append("tree-sitter")
        if HAS_LIZARD and languages.get(lang).lizard_ext:
            tools.append("lizard")
        tools.append("style-rules")
        if result["security"] is not None and languages.is_code(lang):
            tools.append("security-rules")
    engine = result["cfg"].get("engine")
    if engine and engine not in tools:
        tools.append(f"cfg:{engine}")
    return tools


# ─── Repo triage ─────────────────────────────────────────────────────────────

def triage(report: dict) -> dict:
    """Flag + prioritize one analyzed file for the repo scanner."""
    errors = [e for e in report["errors"] if e["severity"] == "error"]
    warnings = [e for e in report["errors"] if e["severity"] == "warning"]
    security_high = [s for s in report["security"] if s["severity"] == "error"]
    max_cc = report["ast_info"].get("max_complexity", 0) if report["ast_info"] else 0
    style = report["style_score"]
    flagged = bool(errors or security_high or max_cc > 10 or style < 60)
    priority = (len(errors) * 4 + len(security_high) * 5 + len(warnings)
                + max(0, max_cc - 10) * 2 + max(0, 60 - style) // 10)
    top = (errors or security_high or warnings or report["complexity"] or report["style_issues"] or [None])[0]
    return {
        "flagged": flagged,
        "priority_score": priority,
        "error_count": len(errors) + len(warnings),
        "security_count": len(report["security"]),
        "complexity": max_cc,
        "top_issue": f"L{top['line']}: {top['message']}"[:140] if top else "",
    }
