"""
Generates a Control Flow Graph (CFG) from Python source code.
Uses the ast module to identify blocks and networkx + matplotlib to render.
"""

import ast
import base64
from io import BytesIO

import networkx as nx
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — must be before pyplot import
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib.patches as mpatches


# ─── CFG Builder ─────────────────────────────────────────────────────────────

class CFGBuilder(ast.NodeVisitor):
    """Walks AST and builds a directed graph representing control flow."""

    def __init__(self, code: str):
        self.graph = nx.DiGraph()
        self.node_labels: dict[int, str] = {}
        self.node_colors: dict[int, str] = {}
        self._counter = 0
        self._current: int | None = None
        self._pending_returns: list[int] = []
        self._code_lines = code.splitlines()

    def _new_node(self, label: str, color: str = "#1f6feb") -> int:
        nid = self._counter
        self._counter += 1
        self.graph.add_node(nid)
        self.node_labels[nid] = label
        self.node_colors[nid] = color
        return nid

    def _add_edge(self, src: int, dst: int, label: str = ""):
        if src is not None:
            self.graph.add_edge(src, dst, label=label)

    def _get_line(self, node: ast.AST) -> str:
        if hasattr(node, "lineno"):
            ln = node.lineno
            if 0 < ln <= len(self._code_lines):
                return self._code_lines[ln - 1].strip()[:40]
        return ast.dump(node)[:40]

    def build(self, tree: ast.AST) -> nx.DiGraph:
        entry = self._new_node("START", "#238636")
        self._current = entry

        for stmt in ast.walk(tree):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._handle_function(stmt)
                break  # Only graph the first function for clarity

        if not any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            for n in ast.walk(tree)
        ):
            # Top-level code path
            for stmt in ast.iter_child_nodes(tree):
                self._handle_stmt(stmt)

        end = self._new_node("END", "#da3633")
        if self._current is not None:
            self._add_edge(self._current, end)
        for ret in self._pending_returns:
            self._add_edge(ret, end)

        return self.graph

    def _handle_function(self, node):
        fn_node = self._new_node(f"def {node.name}()", "#8957e5")
        self._add_edge(self._current, fn_node)
        self._current = fn_node
        for stmt in node.body:
            self._handle_stmt(stmt)

    def _handle_stmt(self, node: ast.AST):
        if isinstance(node, (ast.If,)):
            self._handle_if(node)
        elif isinstance(node, (ast.For, ast.While)):
            self._handle_loop(node)
        elif isinstance(node, ast.Try):
            self._handle_try(node)
        elif isinstance(node, (ast.Return, ast.Raise)):
            ret_node = self._new_node(self._get_line(node), "#f85149")
            self._add_edge(self._current, ret_node)
            self._pending_returns.append(ret_node)
            self._current = None
        else:
            label = self._get_line(node)
            if label:
                stmt_node = self._new_node(label, "#1f6feb")
                self._add_edge(self._current, stmt_node)
                self._current = stmt_node

    def _handle_if(self, node: ast.If):
        condition = f"if {ast.unparse(node.test)[:30]}"
        cond_node = self._new_node(condition, "#d29922")
        self._add_edge(self._current, cond_node)

        # True branch
        self._current = cond_node
        saved_current = cond_node
        for stmt in node.body:
            self._handle_stmt(stmt)
        true_end = self._current

        # False branch
        self._current = saved_current
        for stmt in node.orelse:
            self._handle_stmt(stmt)
        false_end = self._current

        # Merge
        merge = self._new_node("merge", "#30363d")
        if true_end is not None:
            self._add_edge(true_end, merge, "True")
        if false_end is not None:
            self._add_edge(false_end, merge, "False" if node.orelse else "")
        elif not node.orelse:
            self._add_edge(saved_current, merge, "False")

        self._current = merge

    def _handle_loop(self, node):
        if isinstance(node, ast.For):
            label = f"for {ast.unparse(node.target)[:20]} in ..."
        else:
            label = f"while {ast.unparse(node.test)[:25]}"

        loop_node = self._new_node(label, "#d29922")
        self._add_edge(self._current, loop_node)
        self._current = loop_node

        for stmt in node.body:
            self._handle_stmt(stmt)

        if self._current is not None:
            self._add_edge(self._current, loop_node, "loop")

        # After loop
        after = self._new_node("after loop", "#30363d")
        self._add_edge(loop_node, after, "exit")
        self._current = after

    def _handle_try(self, node: ast.Try):
        try_node = self._new_node("try:", "#1f6feb")
        self._add_edge(self._current, try_node)
        self._current = try_node

        for stmt in node.body:
            self._handle_stmt(stmt)

        except_merge = self._new_node("except merge", "#30363d")
        if self._current is not None:
            self._add_edge(self._current, except_merge)

        for handler in node.handlers:
            exc_label = f"except {handler.type and ast.unparse(handler.type) or 'Exception'}"
            exc_node = self._new_node(exc_label, "#f85149")
            self._add_edge(try_node, exc_node)
            saved = self._current
            self._current = exc_node
            for stmt in handler.body:
                self._handle_stmt(stmt)
            if self._current is not None:
                self._add_edge(self._current, except_merge)
            self._current = saved

        self._current = except_merge


# ─── Renderer ────────────────────────────────────────────────────────────────

def _render_graph(graph: nx.DiGraph, labels: dict, colors: dict) -> str:
    """Render networkx graph to a base64 PNG string (OO API, thread-safe)."""
    if len(graph.nodes) == 0:
        return ""

    # Use OO API to avoid global pyplot state (safe in async/threaded contexts)
    fig = Figure(figsize=(10, 8), facecolor="#0d1117")
    FigureCanvasAgg(fig)  # attaches canvas so fig.savefig() works
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0d1117")

    try:
        pos = nx.drawing.nx_agraph.graphviz_layout(graph, prog="dot")
    except Exception:
        pos = nx.spring_layout(graph, seed=42, k=2)

    node_list = list(graph.nodes)
    node_color_list = [colors.get(n, "#1f6feb") for n in node_list]
    label_map = {n: labels.get(n, str(n)) for n in node_list}

    nx.draw_networkx_nodes(
        graph, pos,
        nodelist=node_list,
        node_color=node_color_list,
        node_size=2000,
        ax=ax,
        alpha=0.9,
    )
    nx.draw_networkx_labels(
        graph, pos,
        labels=label_map,
        font_size=7,
        font_color="white",
        ax=ax,
    )
    nx.draw_networkx_edges(
        graph, pos,
        edge_color="#8b949e",
        arrows=True,
        arrowsize=15,
        ax=ax,
        connectionstyle="arc3,rad=0.1",
    )

    edge_labels = nx.get_edge_attributes(graph, "label")
    nx.draw_networkx_edge_labels(
        graph, pos,
        edge_labels=edge_labels,
        font_size=6,
        font_color="#8b949e",
        ax=ax,
    )

    # Legend
    legend_elements = [
        mpatches.Patch(color="#238636", label="Start/End"),
        mpatches.Patch(color="#1f6feb", label="Statement"),
        mpatches.Patch(color="#d29922", label="Branch/Loop"),
        mpatches.Patch(color="#f85149", label="Return/Exception"),
        mpatches.Patch(color="#8957e5", label="Function"),
    ]
    ax.legend(handles=legend_elements, loc="upper right",
              facecolor="#161b22", edgecolor="#30363d",
              labelcolor="white", fontsize=7)

    ax.axis("off")
    fig.tight_layout(pad=0.5)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor="#0d1117")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{img_b64}"


# ─── Public API ──────────────────────────────────────────────────────────────

def generate_cfg(code: str) -> str:
    """
    Parse Python code and return a base64-encoded PNG of the CFG.
    Returns empty string on failure.
    """
    if not code.strip():
        return ""

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""

    try:
        builder = CFGBuilder(code)
        graph = builder.build(tree)
        return _render_graph(graph, builder.node_labels, builder.node_colors)
    except Exception as e:
        print(f"CFG generation error: {e}")
        return ""
