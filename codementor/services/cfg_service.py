"""
Control Flow Graph generation for any language.

Builders
  • Python       → stdlib `ast` (precise: if/elif/else, for/while-else, try/
                   except/finally, match/case, break/continue, return/raise)
  • 40+ others   → tree-sitter syntax trees, walked with a grammar-agnostic
                   model of if / loops / switch-match / try-catch / jumps
  • fallback     → callers may pass an AI-generated spec to `render_spec`

Every function gets its own graph (up to MAX_FUNCTIONS), consecutive simple
statements are merged into basic blocks, and graphs are drawn with a layered
top-down layout (no graphviz needed). Output: PNG data-URI + Mermaid source.
"""

from __future__ import annotations

import ast
import base64
from dataclasses import dataclass, field
from io import BytesIO

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must precede pyplot/figure imports
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib.patches as mpatches

from codementor.services import languages, syntax_service

MAX_FUNCTIONS = 6
MAX_NODES_PER_GRAPH = 70
LABEL_LEN = 38

KIND_COLORS = {
    "start": "#238636", "end": "#da3633", "func": "#8957e5", "stmt": "#1f6feb",
    "branch": "#d29922", "loop": "#bf8700", "return": "#f85149",
    "exception": "#db6d28", "jump": "#6e7681", "case": "#9e6a03",
}


# ─── Graph model ─────────────────────────────────────────────────────────────

@dataclass
class Graph:
    title: str
    nodes: dict[int, tuple[str, str]] = field(default_factory=dict)  # id → (label, kind)
    edges: list[tuple[int, int, str]] = field(default_factory=list)
    truncated: bool = False
    _next: int = 0

    def add(self, label: str, kind: str = "stmt") -> int:
        if len(self.nodes) >= MAX_NODES_PER_GRAPH:
            self.truncated = True
        nid = self._next
        self._next += 1
        label = label.replace("\n", " ").strip() or kind
        if len(label) > LABEL_LEN:
            label = label[: LABEL_LEN - 1] + "…"
        self.nodes[nid] = (label, kind)
        return nid

    def edge(self, src: int, dst: int, label: str = ""):
        self.edges.append((src, dst, label))

    def connect(self, preds: list[tuple[int, str]], dst: int):
        for src, label in preds:
            self.edge(src, dst, label)

    @property
    def decision_points(self) -> int:
        return sum(1 for _, kind in self.nodes.values() if kind in ("branch", "loop", "case"))


Preds = list[tuple[int, str]]


class _BaseBuilder:
    """Shared basic-block + loop bookkeeping for both builders."""

    def __init__(self, title: str):
        self.g = Graph(title)
        self.end: int | None = None
        self.loops: list[tuple[int, list]] = []  # (loop head, break preds)
        self.buffer: list[str] = []

    def flush(self, preds: Preds) -> Preds:
        if not self.buffer:
            return preds
        if len(self.buffer) <= 2:
            label = " ; ".join(self.buffer)
        else:
            label = f"{self.buffer[0]} … (+{len(self.buffer) - 1})"
        self.buffer = []
        nid = self.g.add(label, "stmt")
        self.g.connect(preds, nid)
        return [(nid, "")]

    def jump_return(self, label: str, preds: Preds) -> Preds:
        preds = self.flush(preds)
        nid = self.g.add(label, "return")
        self.g.connect(preds, nid)
        self.g.edge(nid, self.end, "")
        return []

    def jump_break(self, preds: Preds) -> Preds:
        preds = self.flush(preds)
        nid = self.g.add("break", "jump")
        self.g.connect(preds, nid)
        if self.loops:
            self.loops[-1][1].append((nid, "break"))
        return []

    def jump_continue(self, preds: Preds) -> Preds:
        preds = self.flush(preds)
        nid = self.g.add("continue", "jump")
        self.g.connect(preds, nid)
        if self.loops:
            self.g.edge(nid, self.loops[-1][0], "continue")
        return []


# ─── Python builder (ast) ────────────────────────────────────────────────────

def _unparse(node, limit: int = 30) -> str:
    try:
        text = ast.unparse(node)
    except Exception:
        text = type(node).__name__
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _PyBuilder(_BaseBuilder):
    def __init__(self, title: str, src_lines: list[str]):
        super().__init__(title)
        self.lines = src_lines

    def _line(self, node) -> str:
        ln = getattr(node, "lineno", 0)
        if 0 < ln <= len(self.lines):
            return self.lines[ln - 1].strip()
        return _unparse(node)

    def build(self, body: list, start_label: str) -> Graph:
        start = self.g.add(start_label, "func" if start_label.startswith("def") else "start")
        self.end = self.g.add("END", "end")
        out = self.block(body, [(start, "")])
        out = self.flush(out)
        self.g.connect(out, self.end)
        return self.g

    def block(self, stmts: list, preds: Preds) -> Preds:
        for stmt in stmts:
            if (not preds and not self.buffer) or self.g.truncated:
                break  # unreachable code after return/break, or graph too large
            preds = self.stmt(stmt, preds)
        return preds

    def stmt(self, s, preds: Preds) -> Preds:
        g = self.g
        if isinstance(s, ast.If):
            preds = self.flush(preds)
            cond = g.add(f"if {_unparse(s.test)}", "branch")
            g.connect(preds, cond)
            t = self.flush(self.block(s.body, [(cond, "True")]))
            f = self.flush(self.block(s.orelse, [(cond, "False")])) if s.orelse else [(cond, "False")]
            return t + f

        if isinstance(s, (ast.For, ast.AsyncFor, ast.While)):
            preds = self.flush(preds)
            label = (f"for {_unparse(s.target, 14)} in {_unparse(s.iter, 16)}"
                     if not isinstance(s, ast.While) else f"while {_unparse(s.test)}")
            head = g.add(label, "loop")
            g.connect(preds, head)
            self.loops.append((head, []))
            body_out = self.flush(self.block(s.body, [(head, "body")]))
            for src, lbl in body_out:
                g.edge(src, head, lbl or "next")
            _, breaks = self.loops.pop()
            exits: Preds = [(head, "done")]
            if s.orelse:
                exits = self.flush(self.block(s.orelse, exits))
            return exits + breaks

        if isinstance(s, (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())):
            preds = self.flush(preds)
            t = g.add("try", "stmt")
            g.connect(preds, t)
            body_out = self.flush(self.block(s.body, [(t, "")]))
            if s.orelse:
                body_out = self.flush(self.block(s.orelse, body_out))
            handler_out: Preds = []
            for h in s.handlers:
                name = _unparse(h.type, 24) if h.type is not None else "Exception"
                hn = g.add(f"except {name}", "exception")
                g.edge(t, hn, "raises")
                handler_out += self.flush(self.block(h.body, [(hn, "")]))
            merged = body_out + handler_out
            if s.finalbody:
                fin = g.add("finally", "stmt")
                g.connect(merged, fin)
                return self.flush(self.block(s.finalbody, [(fin, "")]))
            return merged

        if hasattr(ast, "Match") and isinstance(s, ast.Match):
            preds = self.flush(preds)
            m = g.add(f"match {_unparse(s.subject)}", "branch")
            g.connect(preds, m)
            outs: Preds = []
            for case in s.cases:
                c = g.add(f"case {_unparse(case.pattern, 24)}", "case")
                g.edge(m, c, "")
                outs += self.flush(self.block(case.body, [(c, "")]))
            return outs + [(m, "no match")]

        if isinstance(s, (ast.With, ast.AsyncWith)):
            preds = self.flush(preds)
            w = g.add(self._line(s), "stmt")
            g.connect(preds, w)
            return self.block(s.body, [(w, "")])

        if isinstance(s, (ast.Return, ast.Raise)):
            return self.jump_return(self._line(s), preds)
        if isinstance(s, ast.Break):
            return self.jump_break(preds)
        if isinstance(s, ast.Continue):
            return self.jump_continue(preds)

        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.buffer.append(f"def {s.name}()")
        elif isinstance(s, ast.ClassDef):
            self.buffer.append(f"class {s.name}")
        else:
            self.buffer.append(self._line(s))
        return preds


def _python_graphs(code: str) -> list[Graph] | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    lines = code.splitlines()
    graphs: list[Graph] = []

    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    funcs.sort(key=lambda n: n.lineno)
    for fn in funcs[:MAX_FUNCTIONS]:
        args = ", ".join(a.arg for a in fn.args.args)
        graphs.append(_PyBuilder(f"{fn.name}()", lines).build(fn.body, f"def {fn.name}({args})"))

    def _is_logic(n) -> bool:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
        return not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))  # docstring

    module_body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    if any(_is_logic(n) for n in module_body):
        graphs.insert(0, _PyBuilder("module", lines).build(module_body, "START"))
    return graphs[:MAX_FUNCTIONS]


# ─── Tree-sitter builder (any language) ──────────────────────────────────────

IF_TYPES = {"if_statement", "if_expression", "if", "unless", "if_let_expression", "guard_statement"}
LOOP_TYPES = {
    "for_statement", "for_in_statement", "for_of_statement", "enhanced_for_statement",
    "foreach_statement", "for_expression", "for_range_loop", "range_based_for_statement",
    "while_statement", "while_expression", "do_statement", "do_while_statement",
    "loop_expression", "for", "while", "until", "repeat_statement", "for_each_statement",
    "while_let_expression", "repeat_while_statement", "for_generic_clause",
}
SWITCH_TYPES = {
    "switch_statement", "switch_expression", "expression_switch_statement",
    "type_switch_statement", "match_expression", "when_expression", "case",
    "select_statement", "match_statement", "case_statement",
}
CASE_TYPES = {
    "switch_case", "case_clause", "switch_section", "match_arm", "when_entry",
    "expression_case", "type_case", "default_case", "communication_case", "when",
    "switch_default", "switch_block_statement_group", "switch_label", "switch_rule",
    "case_item", "default_clause", "switch_entry",
}
TRY_TYPES = {"try_statement", "try_expression", "begin", "try_block", "try_catch_statement"}
CATCH_TYPES = {"catch_clause", "except_clause", "rescue", "catch_block", "catch_declaration"}
FINALLY_TYPES = {"finally_clause", "ensure", "finally_block"}
RETURN_TYPES = {"return_statement", "return_expression", "throw_statement", "throw_expression",
                "raise_statement", "return", "yield_statement"}
BREAK_TYPES = {"break_statement", "break_expression", "break"}
CONTINUE_TYPES = {"continue_statement", "continue_expression", "next", "continue"}
BLOCK_TYPES = {
    "block", "compound_statement", "statement_block", "statement_list", "body_statement",
    "then", "else", "do_block", "block_statement", "function_body", "program",
    "source_file", "translation_unit", "module", "chunk", "else_clause", "elif_clause",
    "else_if_clause", "declaration_list", "constructor_body", "method_body", "do",
    "consequence", "switch_body", "switch_block", "match_block", "statements",
    "control_structure_body", "code_block", "body",
}
CONTROL_TYPES = IF_TYPES | LOOP_TYPES | SWITCH_TYPES | TRY_TYPES | RETURN_TYPES | BREAK_TYPES | CONTINUE_TYPES


class _TSBuilder(_BaseBuilder):
    def __init__(self, title: str, src: bytes):
        super().__init__(title)
        self.src = src

    def text(self, node, limit: int = LABEL_LEN) -> str:
        return syntax_service.first_line(node, self.src, limit)

    def build(self, body_node, start_label: str, kind: str = "func") -> Graph:
        start = self.g.add(start_label, kind)
        self.end = self.g.add("END", "end")
        out = self.stmts(self.children_of(body_node), [(start, "")])
        out = self.flush(out)
        self.g.connect(out, self.end)
        return self.g

    def children_of(self, node) -> list:
        if node is None:
            return []
        if node.type in BLOCK_TYPES:
            return [c for c in syntax_service.named_children(node) if not syntax_service.is_comment(c)]
        return [node]

    def stmts(self, nodes: list, preds: Preds) -> Preds:
        for n in nodes:
            if (not preds and not self.buffer) or self.g.truncated:
                break
            preds = self.stmt(n, preds)
        return preds

    @staticmethod
    def _field(node, name):
        try:
            return node.child_by_field_name(name)
        except Exception:
            return None

    @staticmethod
    def _same(a, b) -> bool:
        # tree-sitter returns fresh wrapper objects, so compare by span + type
        return a is not None and b is not None and (a.start_byte, a.end_byte, a.type) == (b.start_byte, b.end_byte, b.type)

    def _case_body(self, case) -> list:
        if case.type == "match_arm":  # Rust: `pattern => value`
            value = self._field(case, "value")
            return [value] if value is not None else []
        pattern = self._field(case, "value") or self._field(case, "pattern")
        skip = {"switch_label", "case_switch_label", "default_switch_label", "case_pattern",
                "when_condition", "switch_pattern"}
        return [k for k in syntax_service.named_children(case)
                if not syntax_service.is_comment(k) and k.type not in skip and not self._same(k, pattern)]

    def _unwrap(self, node):
        # `if x {}` in Rust/Kotlin arrives wrapped as expression_statement
        if node.type in ("expression_statement", "statement", "expression"):
            kids = [c for c in syntax_service.named_children(node) if not syntax_service.is_comment(c)]
            if len(kids) == 1 and kids[0].type in CONTROL_TYPES:
                return kids[0]
        return node

    def stmt(self, node, preds: Preds) -> Preds:
        node = self._unwrap(node)
        t = node.type
        g = self.g

        if t in BLOCK_TYPES:
            return self.stmts(self.children_of(node), preds)

        if t in IF_TYPES:
            preds = self.flush(preds)
            cond_node = self._field(node, "condition")
            cond_txt = syntax_service.node_text(cond_node, self.src, 60).strip() if cond_node else ""
            label = f"{'unless' if t == 'unless' else 'if'} {cond_txt}".strip() if cond_txt else self.text(node)
            cond = g.add(label, "branch")
            g.connect(preds, cond)
            cons = self._field(node, "consequence") or self._field(node, "body")
            alt = self._field(node, "alternative")
            if cons is None:  # grammar without field names → condition, body…, else
                kids = [c for c in syntax_service.named_children(node) if not self._same(c, cond_node)]
                cons = kids[0] if kids else None
                alt = kids[1] if len(kids) > 1 and alt is None else alt
            t_out = self.flush(self.stmts(self.children_of(cons), [(cond, "True")]))
            if alt is not None:
                f_out = self.flush(self.stmts(self.children_of(alt), [(cond, "False")]))
            else:
                f_out = [(cond, "False")]
            return t_out + f_out

        if t in LOOP_TYPES:
            preds = self.flush(preds)
            header = self.text(node).split("{")[0].strip() or t.replace("_", " ")
            head = g.add(header, "loop")
            g.connect(preds, head)
            body = self._field(node, "body")
            if body is None:
                kids = syntax_service.named_children(node)
                body = kids[-1] if kids else None
            self.loops.append((head, []))
            body_out = self.flush(self.stmts(self.children_of(body), [(head, "body")]))
            for src, lbl in body_out:
                g.edge(src, head, lbl or "next")
            _, breaks = self.loops.pop()
            return [(head, "done")] + breaks

        if t in SWITCH_TYPES:
            preds = self.flush(preds)
            value = self._field(node, "value") or self._field(node, "condition") or self._field(node, "subject")
            label = f"switch {syntax_service.node_text(value, self.src, 30).strip()}" if value else self.text(node)
            sw = g.add(label, "branch")
            g.connect(preds, sw)
            cases = self._find_cases(node)
            outs: Preds = []
            self.loops.append((sw, []))  # `break` inside a case exits the switch
            for case in cases[:12]:
                c = g.add(self.text(case, 26), "case")
                g.edge(sw, c, "")
                outs += self.flush(self.stmts(self._case_body(case), [(c, "")]))
            _, breaks = self.loops.pop()
            def _is_default(c) -> bool:
                # Java/C# reuse the case node type for `default:`; Kotlin uses `else ->`
                head = self.text(c, 12).lstrip()
                return (c.type in ("default_case", "switch_default", "default_clause")
                        or head.startswith(("default", "else", "_ =>", "_ ->")))
            if not any(_is_default(c) for c in cases):
                outs.append((sw, "no match"))
            return outs + breaks

        if t in TRY_TYPES:
            preds = self.flush(preds)
            tr = g.add("try", "stmt")
            g.connect(preds, tr)
            body = self._field(node, "body")
            kids = syntax_service.named_children(node)
            if body is None:
                body = next((k for k in kids if k.type in BLOCK_TYPES), None)
            out = self.flush(self.stmts(self.children_of(body), [(tr, "")]))
            for k in kids:
                if k.type in CATCH_TYPES:
                    h = g.add(self.text(k, 30).split("{")[0], "exception")
                    g.edge(tr, h, "raises")
                    hb = self._field(k, "body") or next(
                        (c for c in syntax_service.named_children(k) if c.type in BLOCK_TYPES), None)
                    out += self.flush(self.stmts(self.children_of(hb), [(h, "")]))
            fin = next((k for k in kids if k.type in FINALLY_TYPES), None)
            if fin is not None:
                f = g.add("finally", "stmt")
                g.connect(out, f)
                fb = next((c for c in syntax_service.named_children(fin) if c.type in BLOCK_TYPES), fin)
                return self.flush(self.stmts(self.children_of(fb) if fb is not fin else [], [(f, "")]))
            return out

        if t in RETURN_TYPES:
            return self.jump_return(self.text(node), preds)
        if t in BREAK_TYPES:
            return self.jump_break(preds)
        if t in CONTINUE_TYPES:
            return self.jump_continue(preds)

        if syntax_service.is_comment(node):
            return preds
        self.buffer.append(self.text(node, 30))
        return preds

    def _find_cases(self, node) -> list:
        found, frontier = [], [node]
        for _ in range(3):  # cases sit at most a couple of levels below the switch
            nxt = []
            for n in frontier:
                for c in syntax_service.named_children(n):
                    if c.type in CASE_TYPES:
                        found.append(c)
                    else:
                        nxt.append(c)
            if found:
                break
            frontier = nxt
        return found


def _ts_graphs(code: str, lang_id: str, filename: str = "") -> list[Graph] | None:
    tree = syntax_service.parse(code, lang_id, filename)
    if tree is None:
        return None
    src = code.encode("utf-8", errors="replace")
    root = tree.root_node

    funcs = []
    stack = [root]
    while stack and len(funcs) < MAX_FUNCTIONS:
        node = stack.pop()
        if node.type in syntax_service.NAMED_FUNCTION_TYPES:
            body = node.child_by_field_name("body")
            if body is None:  # grammars that don't name the body field (Kotlin, Ruby …)
                body = next((c for c in syntax_service.named_children(node)
                             if c.type in BLOCK_TYPES or c.type == "body_statement"), None)
            if body is not None:
                funcs.append((node, body))
                continue  # nested functions are rarely worth a separate graph
        stack.extend(reversed(syntax_service.named_children(node)))

    graphs = []
    for node, body in funcs:
        name = syntax_service._name_of(node, src).split("(")[0].strip() or "function"
        graphs.append(_TSBuilder(f"{name}()", src).build(body, syntax_service.first_line(node, src, LABEL_LEN).split("{")[0]))

    if not graphs:
        graphs.append(_TSBuilder("program", src).build(root, "START", "start"))
    return graphs


# ─── AI spec → graph ─────────────────────────────────────────────────────────

def graphs_from_spec(spec: dict) -> list[Graph]:
    """
    Convert an AI-produced spec into graphs:
      {"graphs": [{"title": str, "nodes": [{"id", "label", "kind"}],
                   "edges": [{"from", "to", "label"}]}]}
    """
    graphs = []
    for gspec in (spec.get("graphs") or [])[:MAX_FUNCTIONS]:
        g = Graph(str(gspec.get("title", "flow"))[:40])
        id_map = {}
        for n in (gspec.get("nodes") or [])[:MAX_NODES_PER_GRAPH]:
            kind = n.get("kind", "stmt")
            id_map[str(n.get("id"))] = g.add(str(n.get("label", "")), kind if kind in KIND_COLORS else "stmt")
        for e in gspec.get("edges") or []:
            a, b = id_map.get(str(e.get("from"))), id_map.get(str(e.get("to")))
            if a is not None and b is not None:
                g.edge(a, b, str(e.get("label", ""))[:12])
        if g.nodes:
            graphs.append(g)
    return graphs


# ─── Layout + rendering ──────────────────────────────────────────────────────

def _layers(g: Graph) -> tuple[dict[int, int], set[tuple[int, int]]]:
    """Longest-path layering over the DAG formed by removing back edges."""
    succ: dict[int, list[int]] = {n: [] for n in g.nodes}
    for a, b, _ in g.edges:
        if a in succ and b in g.nodes:
            succ[a].append(b)
    back: set[tuple[int, int]] = set()
    state: dict[int, int] = {}
    order: list[int] = []
    roots = [min(g.nodes)] + [n for n in g.nodes if n != min(g.nodes)]
    for root in roots:
        if root in state:
            continue
        stack = [(root, iter(succ[root]))]
        state[root] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                order.append(node)
                stack.pop()
            elif state.get(nxt) == 1:
                back.add((node, nxt))
            elif nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(succ[nxt])))
    layer = {n: 0 for n in g.nodes}
    for node in reversed(order):  # topological order
        for nxt in succ[node]:
            if (node, nxt) not in back:
                layer[nxt] = max(layer[nxt], layer[node] + 1)
    return layer, back


def _layout(g: Graph) -> tuple[dict[int, tuple[float, float]], set, float, int]:
    layer, back = _layers(g)
    rows: dict[int, list[int]] = {}
    for n, lv in layer.items():
        rows.setdefault(lv, []).append(n)
    preds: dict[int, list[int]] = {n: [] for n in g.nodes}
    for a, b, _ in g.edges:
        if (a, b) not in back and b in preds:
            preds[b].append(a)
    xpos: dict[int, float] = {}
    for lv in sorted(rows):
        row = rows[lv]
        row.sort(key=lambda n: (sum(xpos.get(p, 0) for p in preds[n]) / len(preds[n])) if preds[n] else 0)
        width = len(row)
        for i, n in enumerate(row):
            xpos[n] = (i - (width - 1) / 2) * 2.6
    pos = {n: (xpos[n], -layer[n] * 1.15) for n in g.nodes}
    span = max((max(xpos[n] for n in r) - min(xpos[n] for n in r)) for r in rows.values()) if rows else 0
    return pos, back, span + 2.8, (max(rows) + 1) if rows else 1


def _render(graphs: list[Graph]) -> str:
    graphs = [g for g in graphs if g.nodes]
    if not graphs:
        return ""
    layouts = [_layout(g) for g in graphs]
    total_w = sum(w for _, _, w, _ in layouts) + 0.8 * (len(graphs) - 1)
    max_h = max(h for _, _, _, h in layouts)
    fig_w = min(max(total_w * 0.95, 6), 30)
    fig_h = min(max(max_h * 0.75 + 1.2, 4), 32)

    fig = Figure(figsize=(fig_w, fig_h), facecolor="#0d1117")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0d1117")

    offset = 0.0
    for g, (pos, back, width, _height) in zip(graphs, layouts):
        cx = offset + width / 2
        placed = {n: (x + cx, y) for n, (x, y) in pos.items()}
        ax.text(cx, 1.0, g.title + ("  (truncated)" if g.truncated else ""),
                ha="center", va="center", color="#e6edf3", fontsize=9, fontweight="bold")
        for a, b, label in g.edges:
            if a not in placed or b not in placed:
                continue
            (x1, y1), (x2, y2) = placed[a], placed[b]
            is_back = (a, b) in back
            ax.annotate(
                "", xy=(x2, y2 + 0.22), xytext=(x1, y1 - 0.22),
                arrowprops=dict(
                    arrowstyle="-|>", color="#58a6ff" if is_back else "#8b949e", lw=0.9,
                    connectionstyle=f"arc3,rad={-0.45 if is_back else (0.0 if abs(x1 - x2) < 0.01 else 0.08)}",
                    shrinkA=2, shrinkB=2,
                ),
            )
            if label:
                ax.text((x1 + x2) / 2 + (0.35 if is_back else 0.12), (y1 + y2) / 2, label,
                        fontsize=6, color="#8b949e", ha="left", va="center")
        for n, (label, kind) in g.nodes.items():
            x, y = placed[n]
            ax.text(x, y, label, ha="center", va="center", fontsize=6.6, color="white",
                    family="monospace",
                    bbox=dict(boxstyle="round,pad=0.35" if kind not in ("branch", "loop", "case")
                              else "round4,pad=0.35",
                              fc=KIND_COLORS.get(kind, "#1f6feb"), ec="#30363d", lw=0.8))
        offset += width + 0.8

    legend = [mpatches.Patch(color=KIND_COLORS[k], label=lbl) for k, lbl in (
        ("func", "Entry"), ("stmt", "Statements"), ("branch", "Decision"), ("loop", "Loop"),
        ("exception", "Exception"), ("return", "Return/Throw"), ("end", "End"))]
    ax.legend(handles=legend, loc="lower right", facecolor="#161b22", edgecolor="#30363d",
              labelcolor="white", fontsize=6.5, ncol=1)
    ax.set_xlim(-0.4, offset)
    ax.set_ylim(-max_h * 1.15 - 0.4, 1.5)
    ax.axis("off")
    fig.tight_layout(pad=0.3)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor="#0d1117")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def to_mermaid(graphs: list[Graph]) -> str:
    out = ["flowchart TD"]
    for gi, g in enumerate(graphs):
        out.append(f'  subgraph G{gi}["{g.title}"]')
        for n, (label, kind) in g.nodes.items():
            safe = label.replace('"', "'")
            shape = ('{"', '"}') if kind in ("branch", "loop", "case") else (('(["', '"])') if kind in ("func", "start", "end") else ('["', '"]'))
            out.append(f"    g{gi}n{n}{shape[0]}{safe}{shape[1]}")
        for a, b, label in g.edges:
            arrow = f"-->|{label}|" if label else "-->"
            out.append(f"    g{gi}n{a} {arrow} g{gi}n{b}")
        out.append("  end")
    return "\n".join(out)


def _result(graphs: list[Graph], engine: str) -> dict:
    nodes = sum(len(g.nodes) for g in graphs)
    decisions = sum(g.decision_points for g in graphs)
    return {
        "image": _render(graphs),
        "mermaid": to_mermaid(graphs),
        "functions": [g.title for g in graphs],
        "summary": f"{len(graphs)} graph(s) · {nodes} nodes · {decisions} decision points · engine: {engine}",
        "error": "",
        "engine": engine,
    }


# ─── Public API ──────────────────────────────────────────────────────────────

def build_cfg(code: str, lang_id: str = "python", filename: str = "") -> dict:
    """
    Build CFGs for the code. Returns
      {"image", "mermaid", "functions", "summary", "error", "engine"}
    `error` is set (and image empty) when no builder supports the input.
    """
    empty = {"image": "", "mermaid": "", "functions": [], "summary": "", "engine": ""}
    if not code.strip():
        return {**empty, "error": "Nothing to graph — the editor is empty."}
    lang_id = languages.normalize(lang_id)
    if not languages.is_code(lang_id):
        return {**empty, "error": f"Control flow graphs apply to programming languages, not {languages.label(lang_id)}."}
    try:
        if lang_id == "python":
            graphs = _python_graphs(code)
            if graphs is None:
                return {**empty, "error": "Fix the syntax error first — the CFG needs parseable code."}
            return _result(graphs, "python-ast")
        graphs = _ts_graphs(code, lang_id, filename)
        if graphs and any(len(g.nodes) > 2 for g in graphs):
            return _result(graphs, "tree-sitter")
    except Exception as exc:  # never break analysis because of the graph
        return {**empty, "error": f"CFG generation failed: {exc}"}
    return {**empty, "error": f"No parser available for {languages.label(lang_id)} — using AI instead."}


def render_spec(spec: dict) -> dict:
    """Render an AI-generated CFG spec (see graphs_from_spec)."""
    graphs = graphs_from_spec(spec)
    if not graphs:
        return {"image": "", "mermaid": "", "functions": [], "summary": "", "engine": "",
                "error": "AI could not produce a control flow graph."}
    return _result(graphs, "ai")


def generate_cfg(code: str) -> str:
    """Backwards-compatible: Python CFG as a PNG data-URI ('' on failure)."""
    return build_cfg(code, "python").get("image", "")
