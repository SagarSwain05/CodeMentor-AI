"""
RAG (Retrieval-Augmented Generation) service for GitHub repo awareness.

Pipeline:
  1. Chunk  — AST-split each Python file into individual functions/classes.
              Other languages: split by size with overlap.
  2. Index  — Store chunks in ChromaDB (vector search) if available,
              else fall back to fast keyword/BM25-style matching.
  3. Retrieve — Given a user query, return the top-k most relevant chunks
                as a context string ready to inject into the LLM prompt.

Usage:
    from codementor.services.rag_service import index_repo, retrieve_context, clear_repo

    index_repo("github.com/owner/repo", file_dicts)   # call once after scan
    ctx = retrieve_context("github.com/owner/repo", "how does auth work?")
    # pass ctx to chat_with_ai(..., rag_context=ctx)
"""

import ast
import re
import math
from collections import defaultdict
from typing import Optional

# ChromaDB is optional — falls back to keyword search if not installed
try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    _CHROMA_CLIENT = chromadb.EphemeralClient()
    HAS_CHROMA = True
except Exception:
    HAS_CHROMA = False
    _CHROMA_CLIENT = None

# In-memory store: repo_id → list of chunk dicts
_repo_chunks: dict[str, list[dict]] = {}

# ChromaDB collections: repo_id → collection
_chroma_collections: dict[str, object] = {}


# ─── Chunking ─────────────────────────────────────────────────────────────────

def _chunk_python(code: str, filepath: str) -> list[dict]:
    """Split a Python file into top-level function + class chunks via AST."""
    chunks = []
    lines = code.splitlines()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Can't parse — treat whole file as one chunk
        return [_make_chunk(filepath, "module", filepath, code[:3000], 1, "file")]

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk_lines = lines[node.lineno - 1: node.end_lineno]
            chunks.append(_make_chunk(
                filepath, node.name,
                f"{filepath}::{node.name}",
                "\n".join(chunk_lines)[:2000],
                node.lineno, "function",
            ))
        elif isinstance(node, ast.ClassDef):
            chunk_lines = lines[node.lineno - 1: node.end_lineno]
            # Also emit each method separately for finer retrieval
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_lines = lines[child.lineno - 1: child.end_lineno]
                    chunks.append(_make_chunk(
                        filepath,
                        f"{node.name}.{child.name}",
                        f"{filepath}::{node.name}.{child.name}",
                        "\n".join(method_lines)[:2000],
                        child.lineno, "method",
                    ))
            # Whole class as a chunk too (truncated)
            chunks.append(_make_chunk(
                filepath, node.name,
                f"{filepath}::{node.name}",
                "\n".join(chunk_lines)[:2000],
                node.lineno, "class",
            ))

    if not chunks:
        # Module-level code only
        chunks.append(_make_chunk(filepath, "module", filepath, code[:3000], 1, "file"))

    return chunks


def _chunk_generic(code: str, filepath: str, chunk_size: int = 60) -> list[dict]:
    """Split any file into overlapping line-window chunks."""
    lines = code.splitlines()
    step = chunk_size // 2
    chunks = []
    for start in range(0, max(1, len(lines)), step):
        end = min(start + chunk_size, len(lines))
        snippet = "\n".join(lines[start:end])
        chunks.append(_make_chunk(
            filepath,
            f"lines {start + 1}-{end}",
            f"{filepath}::L{start + 1}",
            snippet[:2000],
            start + 1, "block",
        ))
    return chunks


def _make_chunk(filepath, name, chunk_id, code, line, kind) -> dict:
    return {
        "id":       chunk_id,
        "filepath": filepath,
        "name":     name,
        "code":     code,
        "line":     line,
        "kind":     kind,
        "text":     f"{filepath} {name} {code}",  # searchable text
    }


def _detect_language(filepath: str) -> str:
    ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
    return {
        "py": "python", "js": "javascript", "ts": "typescript",
        "jsx": "javascript", "tsx": "typescript",
    }.get(ext, "other")


# ─── Indexing ─────────────────────────────────────────────────────────────────

def index_repo(repo_id: str, files: list[dict]) -> int:
    """
    Chunk all repo files and store for retrieval.

    files: list of {"path": str, "code": str}
    Returns: number of chunks indexed.
    """
    chunks: list[dict] = []
    for f in files:
        path = f.get("path", "")
        code = f.get("code", "")
        if not code.strip():
            continue
        lang = _detect_language(path)
        if lang == "python":
            chunks.extend(_chunk_python(code, path))
        else:
            chunks.extend(_chunk_generic(code, path))

    _repo_chunks[repo_id] = chunks

    if HAS_CHROMA and chunks:
        _index_chroma(repo_id, chunks)

    return len(chunks)


def _index_chroma(repo_id: str, chunks: list[dict]):
    """Store chunks in ChromaDB for semantic vector search."""
    try:
        # Safe collection name
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_id)[:60] or "repo"
        # Delete old collection if exists
        try:
            _CHROMA_CLIENT.delete_collection(safe_id)
        except Exception:
            pass
        col = _CHROMA_CLIENT.create_collection(
            safe_id,
            embedding_function=DefaultEmbeddingFunction(),
        )
        # Batch upsert
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            col.add(
                ids=[c["id"] for c in batch],
                documents=[c["text"] for c in batch],
                metadatas=[{"filepath": c["filepath"], "name": c["name"],
                            "kind": c["kind"], "line": c["line"]} for c in batch],
            )
        _chroma_collections[repo_id] = col
    except Exception:
        # ChromaDB error — keyword fallback still works
        pass


# ─── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_context(repo_id: str, query: str, top_k: int = 4) -> str:
    """
    Return a formatted context string of the most relevant code chunks
    for the given query.  Empty string if no repo indexed.
    """
    chunks = _repo_chunks.get(repo_id, [])
    if not chunks:
        return ""

    # Try ChromaDB semantic search first
    if HAS_CHROMA and repo_id in _chroma_collections:
        results = _chroma_search(repo_id, query, top_k)
        if results:
            return _format_context(results)

    # Fallback: BM25-style keyword search
    results = _keyword_search(chunks, query, top_k)
    return _format_context(results)


def _chroma_search(repo_id: str, query: str, top_k: int) -> list[dict]:
    try:
        col = _chroma_collections[repo_id]
        res = col.query(query_texts=[query], n_results=min(top_k, len(_repo_chunks[repo_id])))
        ids = res["ids"][0]
        chunks = _repo_chunks[repo_id]
        id_map = {c["id"]: c for c in chunks}
        return [id_map[i] for i in ids if i in id_map]
    except Exception:
        return []


def _keyword_search(chunks: list[dict], query: str, top_k: int) -> list[dict]:
    """BM25-inspired keyword ranking without external deps."""
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return chunks[:top_k]

    # Build IDF (inverse document frequency)
    doc_count = len(chunks)
    df: dict[str, int] = defaultdict(int)
    tokenized = []
    for c in chunks:
        tokens = _tokenize(c["text"])
        tokenized.append(tokens)
        for t in set(tokens):
            df[t] += 1

    k1, b, avgdl = 1.5, 0.75, sum(len(t) for t in tokenized) / max(doc_count, 1)

    scores = []
    for idx, (chunk, tokens) in enumerate(zip(chunks, tokenized)):
        score = 0.0
        dl = len(tokens)
        tf_map: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf_map[t] += 1
        for qt in query_tokens:
            if qt not in df:
                continue
            tf  = tf_map.get(qt, 0)
            idf = math.log((doc_count - df[qt] + 0.5) / (df[qt] + 0.5) + 1)
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
            score += idf * tf_norm
        scores.append((score, idx))

    scores.sort(key=lambda x: -x[0])
    return [chunks[i] for s, i in scores[:top_k] if s > 0]


def _tokenize(text: str) -> list[str]:
    """Lowercase + split on non-alphanumeric boundaries (good for identifiers)."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for c in chunks:
        parts.append(
            f"// {c['filepath']} — {c['kind']} `{c['name']}` (line {c['line']})\n"
            f"```\n{c['code'][:800]}\n```"
        )
    return "\n\n".join(parts)


# ─── Utilities ────────────────────────────────────────────────────────────────

def clear_repo(repo_id: str):
    _repo_chunks.pop(repo_id, None)
    if repo_id in _chroma_collections:
        try:
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_id)[:60]
            _CHROMA_CLIENT.delete_collection(safe_id)
        except Exception:
            pass
        _chroma_collections.pop(repo_id, None)


def get_repo_stats(repo_id: str) -> dict:
    chunks = _repo_chunks.get(repo_id, [])
    by_kind: dict[str, int] = defaultdict(int)
    for c in chunks:
        by_kind[c["kind"]] += 1
    return {
        "total_chunks": len(chunks),
        "functions": by_kind["function"],
        "methods":   by_kind["method"],
        "classes":   by_kind["class"],
        "files":     len(set(c["filepath"] for c in chunks)),
        "has_chroma": HAS_CHROMA and repo_id in _chroma_collections,
    }
