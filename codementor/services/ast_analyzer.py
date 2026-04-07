"""Analyzes Python source code using the built-in ast module."""

import ast
from typing import Any


class ASTVisitor(ast.NodeVisitor):
    """Walks the AST and collects structural information."""

    def __init__(self):
        self.functions: list[dict] = []
        self.classes: list[dict] = []
        self.imports: list[str] = []
        self.variables: list[str] = []
        self.complexity: int = 1  # Start at 1 for the module itself
        self._current_class: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        entry = {
            "name": node.name,
            "lineno": node.lineno,
            "args": [a.arg for a in node.args.args],
            "class": self._current_class,
            "decorators": [
                ast.unparse(d) for d in node.decorator_list
            ],
            "docstring": ast.get_docstring(node) or "",
            "line_count": node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else 0,
        }
        self.functions.append(entry)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        prev = self._current_class
        self._current_class = node.name
        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "bases": [ast.unparse(b) for b in node.bases],
            "docstring": ast.get_docstring(node) or "",
        })
        self.generic_visit(node)
        self._current_class = prev

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")

    # Cyclomatic complexity: +1 for each decision branch
    def visit_If(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_For(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_While(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_ExceptHandler(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_With(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_Assert(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_BoolOp(self, node): self.complexity += len(node.values) - 1; self.generic_visit(node)


def analyze_ast(code: str) -> dict[str, Any]:
    """
    Parse Python code and return structural analysis.

    Returns a dict with: functions, classes, imports, complexity,
    line_count, syntax_ok, syntax_error
    """
    result: dict[str, Any] = {
        "syntax_ok": True,
        "syntax_error": None,
        "functions": [],
        "classes": [],
        "imports": [],
        "complexity": 0,
        "line_count": len(code.splitlines()),
        "node_count": 0,
    }

    if not code.strip():
        return result

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result["syntax_ok"] = False
        result["syntax_error"] = {
            "message": str(e.msg),
            "lineno": e.lineno,
            "offset": e.offset,
            "text": e.text or "",
        }
        return result

    visitor = ASTVisitor()
    visitor.visit(tree)

    result["functions"] = visitor.functions
    result["classes"] = visitor.classes
    result["imports"] = list(set(visitor.imports))
    result["complexity"] = visitor.complexity
    result["node_count"] = sum(1 for _ in ast.walk(tree))

    return result


def get_ast_summary(ast_info: dict) -> str:
    """Return a human-readable summary for the Gemini prompt."""
    if not ast_info.get("syntax_ok"):
        err = ast_info.get("syntax_error", {})
        return f"Syntax error at line {err.get('lineno', '?')}: {err.get('message', 'unknown')}"

    lines = [
        f"Lines of code: {ast_info['line_count']}",
        f"Cyclomatic complexity: {ast_info['complexity']}",
        f"Functions: {len(ast_info['functions'])} — {[f['name'] for f in ast_info['functions']]}",
        f"Classes: {len(ast_info['classes'])} — {[c['name'] for c in ast_info['classes']]}",
        f"Imports: {ast_info['imports']}",
    ]
    return "\n".join(lines)
