"""
Complexity metrics for every language.

  • Python      → radon (cyclomatic complexity + Maintainability Index)
  • 20+ others  → lizard (C/C++, Java, C#, JS/TS, Go, Rust, Kotlin, Swift, Ruby,
                  PHP, Scala, Lua, Erlang, Fortran, Solidity, Objective-C, Zig …)
  • anything    → token-based Halstead approximation for the Maintainability Index
"""

from __future__ import annotations

import math
import re

from codementor.services import languages

try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit
    HAS_RADON = True
except ImportError:  # pragma: no cover
    HAS_RADON = False

try:
    import lizard
    HAS_LIZARD = True
except ImportError:  # pragma: no cover
    HAS_LIZARD = False


# Flag functions above rank A (complexity > 5)
COMPLEXITY_THRESHOLD = 5
LONG_FUNCTION_LINES = 80
MANY_PARAMS = 6


def rank_for(cc: int) -> str:
    """Radon's rank scale: A 1-5, B 6-10, C 11-20, D 21-30, E 31-40, F 41+."""
    for limit, rank in ((5, "A"), (10, "B"), (20, "C"), (30, "D"), (40, "E")):
        if cc <= limit:
            return rank
    return "F"


def function_metrics(code: str, lang_id: str) -> list[dict]:
    """
    Per-function metrics: name, lineno, end_line, complexity, nloc, params.
    Empty list when no analyzer supports the language.
    """
    if not code.strip():
        return []
    lang = languages.get(lang_id)

    if lang.id == "python" and HAS_RADON:
        try:
            out = []
            for b in cc_visit(code):
                name = b.name if not getattr(b, "classname", None) else f"{b.classname}.{b.name}"
                out.append({
                    "name": name,
                    "lineno": b.lineno,
                    "end_line": getattr(b, "endline", b.lineno),
                    "complexity": b.complexity,
                    "nloc": max(1, getattr(b, "endline", b.lineno) - b.lineno + 1),
                    "params": None,
                })
            return out
        except Exception:
            pass  # syntax error etc. → try lizard below

    if HAS_LIZARD and lang.lizard_ext:
        try:
            info = lizard.analyze_file.analyze_source_code(f"source{lang.lizard_ext}", code)
            out = []
            for fn in info.function_list:
                params = getattr(fn, "parameter_count", None)
                if callable(params):
                    params = params()
                out.append({
                    "name": fn.name or "(anonymous)",
                    "lineno": fn.start_line,
                    "end_line": fn.end_line,
                    "complexity": fn.cyclomatic_complexity,
                    "nloc": fn.nloc,
                    "params": params,
                })
            return out
        except Exception:
            return []
    return []


def check_complexity(code: str, lang_id: str = "python",
                     metrics: list[dict] | None = None) -> list[dict]:
    """Issues for functions that are too complex, too long, or take too many params."""
    metrics = metrics if metrics is not None else function_metrics(code, lang_id)
    issues = []
    for m in metrics:
        cc = m["complexity"]
        if cc > COMPLEXITY_THRESHOLD:
            rank = rank_for(cc)
            issues.append({
                "line": m["lineno"], "col": 1, "code": f"CC-{rank}",
                "message": f"'{m['name']}' has cyclomatic complexity {cc} (rank {rank}) — consider splitting it up",
                "severity": "error" if cc > 20 else "warning",
                "category": "complexity",
                "name": m["name"], "complexity": cc, "rank": rank,
            })
        if m.get("nloc", 0) > LONG_FUNCTION_LINES:
            issues.append({
                "line": m["lineno"], "col": 1, "code": "LONG-FN",
                "message": f"'{m['name']}' is {m['nloc']} lines long — long functions are hard to test",
                "severity": "info", "category": "complexity",
                "name": m["name"], "complexity": cc, "rank": rank_for(cc),
            })
        if (m.get("params") or 0) > MANY_PARAMS:
            issues.append({
                "line": m["lineno"], "col": 1, "code": "MANY-PARAMS",
                "message": f"'{m['name']}' takes {m['params']} parameters — consider a parameter object",
                "severity": "info", "category": "complexity",
                "name": m["name"], "complexity": cc, "rank": rank_for(cc),
            })
    return sorted(issues, key=lambda x: (-x["complexity"], x["line"]))


_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||[^\s\w]")


def maintainability_index(code: str, lang_id: str = "python",
                          metrics: list[dict] | None = None) -> int:
    """Maintainability Index 0–100 (higher = easier to maintain)."""
    if not code.strip():
        return 100
    if languages.normalize(lang_id) == "python" and HAS_RADON:
        try:
            return max(0, min(100, round(mi_visit(code, multi=True))))
        except Exception:
            pass

    # Classic MI formula with a token-based Halstead volume approximation
    lines = [ln for ln in code.splitlines() if ln.strip()]
    loc = max(len(lines), 1)
    tokens = _TOKEN_RE.findall(code)
    n_total = max(len(tokens), 1)
    n_unique = max(len(set(tokens)), 2)
    volume = n_total * math.log2(n_unique)
    metrics = metrics if metrics is not None else function_metrics(code, lang_id)
    cc = sum(m["complexity"] for m in metrics) if metrics else 1
    mi = 171 - 5.2 * math.log(max(volume, 1)) - 0.23 * cc - 16.2 * math.log(loc)
    return max(0, min(100, round(mi * 100 / 171)))
