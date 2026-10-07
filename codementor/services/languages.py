"""
Language registry — single source of truth for every language the app knows.

Each entry describes how a language is detected (extensions / filenames),
which tree-sitter grammar parses it, which lizard reader measures its
complexity, how its line comments start, and which family it belongs to
("code" languages get the full pipeline; "data"/"markup" get validation only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Language:
    id: str
    label: str
    extensions: tuple[str, ...]
    ts_name: str = ""             # tree-sitter-language-pack grammar name
    lizard_ext: str = ""          # extension lizard uses to pick its reader
    comment: tuple[str, ...] = ("//",)
    kind: str = "code"            # code | markup | data | docs
    filenames: tuple[str, ...] = field(default_factory=tuple)


_LANGS: list[Language] = [
    Language("python", "Python", (".py", ".pyw", ".pyi"), "python", ".py", ("#",)),
    Language("javascript", "JavaScript", (".js", ".mjs", ".cjs", ".jsx"), "javascript", ".js"),
    Language("typescript", "TypeScript", (".ts", ".mts", ".cts", ".tsx"), "typescript", ".ts"),
    Language("java", "Java", (".java",), "java", ".java"),
    Language("c", "C", (".c", ".h"), "c", ".c"),
    Language("cpp", "C++", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".ino"), "cpp", ".cpp"),
    Language("csharp", "C#", (".cs",), "csharp", ".cs"),
    Language("go", "Go", (".go",), "go", ".go"),
    Language("rust", "Rust", (".rs",), "rust", ".rs"),
    Language("kotlin", "Kotlin", (".kt", ".kts"), "kotlin", ".kt"),
    Language("swift", "Swift", (".swift",), "swift", ".swift"),
    Language("ruby", "Ruby", (".rb", ".rake", ".gemspec"), "ruby", ".rb", ("#",),
             filenames=("Rakefile", "Gemfile")),
    Language("php", "PHP", (".php", ".phtml"), "php", ".php", ("//", "#")),
    Language("scala", "Scala", (".scala", ".sc"), "scala", ".scala"),
    Language("dart", "Dart", (".dart",), "dart", ""),
    Language("lua", "Lua", (".lua",), "lua", ".lua", ("--",)),
    Language("perl", "Perl", (".pl", ".pm"), "perl", ".pl", ("#",)),
    Language("r", "R", (".r", ".R"), "r", ".r", ("#",)),
    Language("julia", "Julia", (".jl",), "julia", "", ("#",)),
    Language("haskell", "Haskell", (".hs",), "haskell", "", ("--",)),
    Language("elixir", "Elixir", (".ex", ".exs"), "elixir", "", ("#",)),
    Language("erlang", "Erlang", (".erl", ".hrl"), "erlang", ".erl", ("%",)),
    Language("clojure", "Clojure", (".clj", ".cljs", ".cljc"), "clojure", "", (";",)),
    Language("ocaml", "OCaml", (".ml", ".mli"), "ocaml", "", ()),
    Language("objectivec", "Objective-C", (".m", ".mm"), "objc", ".m"),
    Language("zig", "Zig", (".zig",), "zig", ".zig"),
    Language("solidity", "Solidity", (".sol",), "solidity", ".sol"),
    Language("fortran", "Fortran", (".f90", ".f95", ".f03", ".f"), "fortran", ".f90", ("!",)),
    Language("groovy", "Groovy", (".groovy", ".gradle"), "groovy", ""),
    Language("bash", "Bash / Shell", (".sh", ".bash", ".zsh"), "bash", "", ("#",)),
    Language("powershell", "PowerShell", (".ps1", ".psm1"), "powershell", "", ("#",)),
    Language("sql", "SQL", (".sql",), "sql", "", ("--",)),
    Language("vue", "Vue", (".vue",), "vue", "", ("//",), "markup"),
    Language("svelte", "Svelte", (".svelte",), "svelte", "", ("//",), "markup"),
    Language("html", "HTML", (".html", ".htm"), "html", "", (), "markup"),
    Language("css", "CSS", (".css",), "css", "", (), "markup"),
    Language("scss", "SCSS", (".scss", ".sass"), "scss", "", ("//",), "markup"),
    Language("dockerfile", "Dockerfile", (".dockerfile",), "dockerfile", "", ("#",), "code",
             filenames=("Dockerfile", "Containerfile")),
    Language("makefile", "Makefile", (".mk",), "make", "", ("#",), "code",
             filenames=("Makefile", "GNUmakefile")),
    Language("hcl", "Terraform / HCL", (".tf", ".hcl"), "hcl", "", ("#", "//"), "data"),
    Language("json", "JSON", (".json", ".jsonc"), "json", "", (), "data"),
    Language("yaml", "YAML", (".yaml", ".yml"), "yaml", "", ("#",), "data"),
    Language("toml", "TOML", (".toml",), "toml", "", ("#",), "data"),
    Language("xml", "XML", (".xml", ".xsd", ".svg"), "xml", "", (), "data"),
    Language("markdown", "Markdown", (".md", ".markdown"), "markdown", "", (), "docs"),
    Language("text", "Plain text", (".txt",), "", "", (), "docs"),
]

LANGUAGES: dict[str, Language] = {lang.id: lang for lang in _LANGS}
_BY_EXT: dict[str, str] = {}
for _lang in _LANGS:
    for _ext in _lang.extensions:
        _BY_EXT.setdefault(_ext.lower(), _lang.id)
_BY_FILENAME: dict[str, str] = {
    name: lang.id for lang in _LANGS for name in lang.filenames
}

# Languages shown in the editor's selector (code first, then markup/data)
LANGUAGE_IDS: list[str] = [lang.id for lang in _LANGS if lang.kind == "code"] + [
    lang.id for lang in _LANGS if lang.kind != "code"
]

# Aliases people (and older saved snippets) use
_ALIASES = {
    "py": "python", "js": "javascript", "ts": "typescript", "c++": "cpp",
    "c#": "csharp", "cs": "csharp", "golang": "go", "rs": "rust", "rb": "ruby",
    "sh": "bash", "shell": "bash", "zsh": "bash", "kt": "kotlin", "yml": "yaml",
    "md": "markdown", "objc": "objectivec", "jsx": "javascript", "tsx": "typescript",
}


def get(lang_id: str) -> Language:
    """Return the Language for an id (or alias). Unknown → plain text."""
    lang_id = normalize(lang_id)
    return LANGUAGES.get(lang_id, LANGUAGES["text"])


def normalize(lang_id: str) -> str:
    lang_id = (lang_id or "").strip().lower()
    return _ALIASES.get(lang_id, lang_id)


def label(lang_id: str) -> str:
    return get(lang_id).label


def is_code(lang_id: str) -> bool:
    return get(lang_id).kind == "code"


def default_extension(lang_id: str) -> str:
    lang = get(lang_id)
    return lang.extensions[0] if lang.extensions else ".txt"


def from_filename(path: str) -> str:
    """Detect language from a path; '' if unknown."""
    name = path.rsplit("/", 1)[-1]
    if name in _BY_FILENAME:
        return _BY_FILENAME[name]
    if name.lower().startswith("dockerfile"):
        return "dockerfile"
    if "." not in name:
        return ""
    ext = "." + name.rsplit(".", 1)[-1]
    return _BY_EXT.get(ext, _BY_EXT.get(ext.lower(), ""))


# ─── Content-based detection ─────────────────────────────────────────────────

# (language, regex, weight) — scored together; highest total wins.
_SIGNALS: list[tuple[str, str, int]] = [
    ("python", r"^\s*def \w+\(.*\)\s*(->\s*[\w\[\], .]+)?:\s*$", 4),
    ("python", r"^\s*(from [\w.]+ )?import [\w., ]+$", 2),
    ("python", r"^\s*(elif|except\b.*|class \w+(\(.*\))?):\s*$", 3),
    ("python", r"\bprint\(|\bself\.|__name__ == ['\"]__main__['\"]", 2),
    ("python", r"\binput\(|\bf['\"][^'\"]*\{|\brange\(|\blen\(|^\s*\w+\s*=\s*\[.*\]\s*$|\bNone\b|\bTrue\b|\bFalse\b", 1),
    ("javascript", r"\b(const|let|var) \w+ = |=> \{|\bfunction\s*\w*\s*\(", 2),
    ("javascript", r"console\.log\(|require\(['\"]|module\.exports|document\.", 3),
    ("typescript", r"^\s*(export )?(interface|type) \w+|:\s*(string|number|boolean|any|void)\b", 4),
    ("typescript", r"\bimport .* from ['\"]", 1),
    ("java", r"\bpublic\s+(static\s+)?(class|void|interface)\b|System\.out\.print", 4),
    ("java", r"^\s*package [\w.]+;\s*$|^\s*import java\.", 4),
    ("csharp", r"^\s*using System|\bnamespace \w+|Console\.Write", 4),
    ("c", r"^\s*#include\s*<(stdio|stdlib|string|math)\.h>", 4),
    ("c", r"\bprintf\s*\(|\bmalloc\s*\(|\bint main\s*\(", 2),
    ("cpp", r"^\s*#include\s*<(iostream|vector|string|map|algorithm)>|std::|\bcout\s*<<", 5),
    ("cpp", r"\btemplate\s*<|\bnamespace \w+\s*\{|::\w+\(", 2),
    ("go", r"^\s*package \w+\s*$|\bfunc (\(\w+ \*?\w+\) )?\w+\(|:= ", 3),
    ("go", r"\bfmt\.Print|\bimport \(", 4),
    ("rust", r"\bfn \w+\s*(<.*>)?\(|\blet mut\b|println!\(|\bimpl\b|->\s*Result<", 4),
    ("kotlin", r"\bfun \w+\(|\bval \w+\s*[:=]|\bprintln\(", 3),
    ("swift", r"\bfunc \w+\(.*\)\s*(->\s*\w+\s*)?\{|\bimport (SwiftUI|Foundation|UIKit)\b|\bguard let\b", 4),
    ("ruby", r"^\s*(def \w+[?!]?|end|class \w+( < \w+)?|module \w+)\s*$|\bputs\b|\.each do\b", 3),
    ("php", r"<\?php|\$\w+\s*=|\becho\b", 4),
    ("bash", r"^#!.*\b(bash|sh|zsh)\b|^\s*(if \[|fi$|done$|echo \$|export \w+=)", 4),
    ("sql", r"(?i)^\s*(select .+ from|insert into|create table|update \w+ set|delete from)\b", 5),
    ("html", r"(?i)<!doctype html|<html\b|<div\b|<body\b", 5),
    ("css", r"^\s*[.#]?[\w-]+\s*\{\s*$|^\s*[\w-]+\s*:\s*[^;]+;\s*$", 1),
    ("lua", r"\blocal \w+ = |\bfunction \w+\(.*\)$|\bend$", 2),
    ("r", r"<- |\blibrary\(\w+\)|\bdata\.frame\(", 3),
    ("dart", r"\bvoid main\(\)|\bimport 'package:|\bfinal \w+ = ", 3),
    ("scala", r"\bobject \w+|\bdef \w+\(.*\):\s*\w+\s*=|\bcase class\b", 3),
    ("elixir", r"\bdefmodule\b|\bdefp? \w+.*\bdo\b|\|>", 4),
    ("haskell", r"^\w+ :: .+->|^module \w+ where|\bwhere$", 4),
    ("perl", r"^\s*use strict;|\bmy \$\w+|\bsub \w+ \{", 4),
    ("powershell", r"\$\w+ = Get-|\bWrite-Host\b|\bparam\(", 4),
    ("dockerfile", r"^(FROM|RUN|COPY|CMD|ENTRYPOINT|WORKDIR) ", 4),
    ("yaml", r"^[\w-]+:\s*$|^\s*- \w+:", 1),
]
_COMPILED = [(lang, re.compile(rx, re.M), w) for lang, rx, w in _SIGNALS]


def detect_from_content(code: str) -> str:
    """Best-effort language guess from source text. '' if unsure."""
    text = code[:20_000]
    if not text.strip():
        return ""
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        import json
        try:
            json.loads(text)
            return "json"
        except Exception:
            pass
    if stripped.startswith("<?xml"):
        return "xml"

    scores: dict[str, int] = {}
    for lang, rx, weight in _COMPILED:
        hits = len(rx.findall(text))
        if hits:
            scores[lang] = scores.get(lang, 0) + weight * min(hits, 5)

    # TypeScript is a superset of JavaScript — let TS-only signals win ties
    if "typescript" in scores and "javascript" in scores:
        scores["typescript"] += scores["javascript"]
    # C++ is a superset of C
    if "cpp" in scores and "c" in scores:
        scores["cpp"] += scores["c"]
    if not scores:
        return ""
    best, best_score = max(scores.items(), key=lambda kv: kv[1])
    # A weak signal is enough when no other language matched at all
    return best if best_score >= 3 or (best_score >= 2 and len(scores) == 1) else ""


def detect(code: str, filename: str = "", fallback: str = "text") -> str:
    """Detect a language from filename first, then content."""
    by_name = from_filename(filename) if filename else ""
    if by_name and by_name != "text":
        return by_name
    return detect_from_content(code) or by_name or fallback
