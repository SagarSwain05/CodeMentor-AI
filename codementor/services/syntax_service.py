"""
Universal parsing layer built on tree-sitter (via tree-sitter-language-pack).

Gives every supported language:
  • syntax error detection (ERROR / MISSING nodes) with line + column
  • structure extraction (functions, classes, imports)
  • a parsed tree that cfg_service walks to build control-flow graphs

tree-sitter is optional at runtime: if the package or a grammar is missing,
every function degrades to an empty/None result and callers fall back to
heuristics, so the app never crashes because of a parser.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Any

from codementor.services import languages

try:
    from tree_sitter_language_pack import get_parser as _ts_get_parser
    HAS_TREE_SITTER = True
except Exception:  # pragma: no cover — optional dependency
    _ts_get_parser = None
    HAS_TREE_SITTER = False


# Some grammars have had different names across package versions
_ALT_NAMES = {
    "csharp": ("csharp", "c_sharp"),
    "objc": ("objc", "objective_c"),
    "make": ("make", "makefile"),
    "typescript": ("typescript", "tsx"),
}


@lru_cache(maxsize=64)
def _resolve_name(ts_name: str) -> str:
    """Find which grammar name this package version accepts ('' if none)."""
    if not HAS_TREE_SITTER or not ts_name:
        return ""
    for name in _ALT_NAMES.get(ts_name, (ts_name,)):
        try:
            _ts_get_parser(name)
            return name
        except Exception:
            continue
    return ""


# Parsers are not thread-safe; analysis runs in worker threads, so cache per thread.
_local = threading.local()


def prefetch_grammars() -> None:
    """
    tree-sitter-language-pack ≥1.0 downloads grammars on first use. Warm the
    cache in a daemon thread at startup so the first analysis of each language
    isn't slowed by a download. Safe to call repeatedly; never raises.
    """
    if not HAS_TREE_SITTER:
        return

    def _work():
        try:
            import tree_sitter_language_pack as tslp
            names = sorted({lang.ts_name for lang in languages.LANGUAGES.values() if lang.ts_name})
            if hasattr(tslp, "download"):
                tslp.download(names)
        except Exception:
            # Fall back to one-by-one so a single unknown name can't block the rest
            for lang in languages.LANGUAGES.values():
                if lang.ts_name:
                    _resolve_name(lang.ts_name)

    threading.Thread(target=_work, name="ts-grammar-prefetch", daemon=True).start()


def _parser_for(ts_name: str):
    name = _resolve_name(ts_name)
    if not name:
        return None
    cache = getattr(_local, "parsers", None)
    if cache is None:
        cache = _local.parsers = {}
    if name not in cache:
        try:
            cache[name] = _ts_get_parser(name)
        except Exception:
            return None
    return cache[name]


def has_grammar(lang_id: str) -> bool:
    return _parser_for(languages.get(lang_id).ts_name) is not None


def parse(code: str, lang_id: str, filename: str = ""):
    """Return a tree-sitter Tree, or None if unavailable."""
    lang = languages.get(lang_id)
    ts_name = lang.ts_name
    # .tsx / .jsx need the tsx grammar for JSX syntax
    if filename.endswith(".tsx") or (lang.id == "javascript" and filename.endswith(".jsx")):
        ts_name = "tsx" if lang.id == "typescript" else "javascript"
    parser = _parser_for(ts_name)
    if parser is None:
        return None
    try:
        return parser.parse(code.encode("utf-8", errors="replace"))
    except Exception:
        return None


# ─── Node helpers ────────────────────────────────────────────────────────────

def node_text(node, src: bytes, limit: int = 200) -> str:
    try:
        return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def first_line(node, src: bytes, limit: int = 42) -> str:
    text = node_text(node, src, 400).strip().splitlines()
    line = text[0].strip() if text else node.type
    return line if len(line) <= limit else line[: limit - 1] + "…"


def named_children(node) -> list:
    try:
        return [c for c in node.children if c.is_named]
    except Exception:
        return []


def is_comment(node) -> bool:
    return "comment" in node.type


# ─── Syntax errors ───────────────────────────────────────────────────────────

def syntax_errors(code: str, lang_id: str, filename: str = "", limit: int = 25) -> list[dict] | None:
    """
    Return syntax errors as issue dicts, or None if no grammar is available
    (so callers can distinguish "no errors" from "couldn't check").
    """
    tree = parse(code, lang_id, filename)
    if tree is None:
        return None
    root = tree.root_node
    if not getattr(root, "has_error", False):
        return []

    src = code.encode("utf-8", errors="replace")
    lines = code.splitlines()
    issues: list[dict] = []
    stack = [root]
    while stack and len(issues) < limit:
        node = stack.pop()
        if node.type == "ERROR" or getattr(node, "is_missing", False):
            row, col = node.start_point[0], node.start_point[1]
            if getattr(node, "is_missing", False):
                msg = f"Missing `{node.type}`"
            else:
                snippet = node_text(node, src, 60).strip().splitlines()
                near = snippet[0][:40] if snippet else ""
                msg = f"Syntax error near `{near}`" if near else "Syntax error"
            issues.append({
                "line": row + 1,
                "col": col + 1,
                "code": "SYNTAX",
                "message": msg,
                "severity": "error",
                "category": "error",
                "source": "tree-sitter",
                "context": lines[row].strip()[:120] if 0 <= row < len(lines) else "",
            })
            continue  # don't report nested errors inside an ERROR node
        if getattr(node, "has_error", False):
            # visit children in source order
            stack.extend(reversed(node.children))
    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


# ─── Structure extraction ────────────────────────────────────────────────────

FUNCTION_TYPES = {
    "function_definition", "function_declaration", "function_item",
    "method_declaration", "method_definition", "method", "singleton_method",
    "constructor_declaration", "function", "func_literal", "arrow_function",
    "function_expression", "generator_function_declaration", "local_function_statement",
    "function_signature_item", "fun_declaration", "anonymous_function",
    "lambda_expression", "init_declaration", "protocol_function_declaration",
    "subroutine", "function_statement",
}
NAMED_FUNCTION_TYPES = FUNCTION_TYPES - {
    "arrow_function", "function_expression", "func_literal", "lambda_expression",
    "anonymous_function",
}
CLASS_TYPES = {
    "class_definition", "class_declaration", "class_specifier", "struct_specifier",
    "struct_item", "enum_item", "trait_item", "impl_item", "interface_declaration",
    "enum_declaration", "struct_declaration", "record_declaration", "class",
    "module", "object_declaration", "protocol_declaration", "type_declaration",
    "trait_definition", "object_definition", "contract_declaration",
    "abstract_class_declaration",
}
IMPORT_TYPES = {
    "import_statement", "import_from_statement", "import_declaration",
    "preproc_include", "using_directive", "use_declaration", "import_header",
    "namespace_use_declaration", "require_call", "import_spec", "extern_crate_declaration",
}


def _name_of(node, src: bytes) -> str:
    named = node.child_by_field_name("name") if hasattr(node, "child_by_field_name") else None
    if named is not None:
        return node_text(named, src, 80)
    # C/C++: function_definition → declarator → (pointer_)declarator → identifier
    decl = node.child_by_field_name("declarator") if hasattr(node, "child_by_field_name") else None
    depth = 0
    while decl is not None and depth < 6:
        inner = decl.child_by_field_name("declarator")
        if inner is None:
            break
        decl = inner
        depth += 1
    if decl is not None:
        return node_text(decl, src, 80)
    for child in named_children(node):
        if child.type in ("identifier", "type_identifier", "constant", "simple_identifier",
                          "property_identifier", "field_identifier", "name"):
            return node_text(child, src, 80)
    return ""


def extract_structure(code: str, lang_id: str, filename: str = "") -> dict[str, Any] | None:
    """Functions / classes / imports via tree-sitter. None if no grammar."""
    tree = parse(code, lang_id, filename)
    if tree is None:
        return None
    src = code.encode("utf-8", errors="replace")
    functions, classes, imports = [], [], []
    stack = [(tree.root_node, None)]
    seen = 0
    while stack and seen < 50_000:
        node, current_class = stack.pop()
        seen += 1
        t = node.type
        if t in CLASS_TYPES:
            name = _name_of(node, src)
            if name:
                classes.append({"name": name, "lineno": node.start_point[0] + 1,
                                "bases": [], "docstring": ""})
                current_class = name
        elif t in NAMED_FUNCTION_TYPES:
            name = _name_of(node, src)
            if name:
                functions.append({
                    "name": name.split("(")[0].strip(),
                    "lineno": node.start_point[0] + 1,
                    "args": [],
                    "class": current_class,
                    "decorators": [],
                    "docstring": "",
                    "line_count": node.end_point[0] - node.start_point[0] + 1,
                })
        elif t in IMPORT_TYPES:
            imports.append(first_line(node, src, 80))
            continue
        for child in reversed(named_children(node)):
            stack.append((child, current_class))

    functions.sort(key=lambda f: f["lineno"])
    classes.sort(key=lambda c: c["lineno"])
    return {"functions": functions, "classes": classes, "imports": sorted(set(imports))}
