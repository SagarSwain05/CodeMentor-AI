"""
GitHub integration service.
Handles URL parsing, repo tree fetching, file content retrieval, and smart triage.
Uses only stdlib (urllib) — no new pip dependencies.
"""

import re
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any


# ─── URL Parsing ─────────────────────────────────────────────────────────────

def parse_github_url(url: str) -> dict[str, Any]:
    """
    Parse any GitHub URL and return a structured dict.

    Supported formats:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/blob/{branch}/{path}
      - https://github.com/owner/repo/tree/{branch}/{path}
      - https://raw.githubusercontent.com/owner/repo/{branch}/{path}

    Returns:
      {"type": "single_file", "owner", "repo", "branch", "path", "filename"}
      {"type": "repo",        "owner", "repo", "branch"}
      {"type": "unknown",     "error": str}
    """
    url = url.strip()

    # Raw file URL
    raw_match = re.match(
        r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)",
        url,
    )
    if raw_match:
        owner, repo, branch, path = raw_match.groups()
        return {
            "type": "single_file",
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "path": path,
            "filename": path.split("/")[-1],
        }

    # GitHub blob or tree URL
    blob_match = re.match(
        r"https://github\.com/([^/]+)/([^/]+)/(blob|tree)/([^/]+)/(.+)",
        url,
    )
    if blob_match:
        owner, repo, kind, branch, path = blob_match.groups()
        if kind == "blob":
            return {
                "type": "single_file",
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "path": path,
                "filename": path.split("/")[-1],
            }
        else:  # tree → treat as repo with subdir filter
            return {
                "type": "repo",
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "subdir": path,
            }

    # Bare repo URL: https://github.com/owner/repo  OR  github.com/owner/repo (no scheme)
    if not url.startswith("http"):
        url = "https://" + url
    bare_match = re.match(r"https://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$", url)
    if bare_match:
        owner, repo = bare_match.groups()
        # branch "" → resolved to the repo's real default branch at fetch time
        return {"type": "repo", "owner": owner, "repo": repo, "branch": ""}

    return {"type": "unknown", "error": f"Cannot parse GitHub URL: {url!r}"}


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _make_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Code-Reviewer/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, token: str | None = None) -> dict[str, Any]:
    """HTTP GET with GitHub headers. Returns {"ok", "data"|"error", "status"}."""
    req = urllib.request.Request(url, headers=_make_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return {"ok": True, "data": json.loads(body), "status": resp.status}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            msg = json.loads(body).get("message", body[:200])
        except Exception:
            msg = str(e)
        # Detect rate limit
        if e.code == 403 and "rate limit" in msg.lower():
            msg = ("GitHub rate limit reached (60 req/hr for unauthenticated). "
                   "Add a GitHub Personal Access Token in Settings for 5,000 req/hr.")
        if e.code == 404:
            msg = "Repository or file not found. It may be private — add a GitHub token."
        return {"ok": False, "error": msg, "status": e.code}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"Network error: {e.reason}", "status": 0}
    except Exception as e:
        return {"ok": False, "error": str(e), "status": 0}


def _get_raw(url: str, token: str | None = None) -> dict[str, Any]:
    """Fetch raw text content (not JSON)."""
    req = urllib.request.Request(url, headers=_make_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(204_800)  # cap at 200 KB
            try:
                content = body.decode("utf-8")
            except UnicodeDecodeError:
                return {"ok": False, "error": "Binary file — cannot analyze"}
            return {"ok": True, "content": content, "status": resp.status}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": "File not found", "status": 404}
        if e.code == 403:
            return {"ok": False, "error": "Access denied — add GitHub token", "status": 403}
        return {"ok": False, "error": f"HTTP {e.code}", "status": e.code}
    except Exception as e:
        return {"ok": False, "error": str(e), "status": 0}


# ─── Single file fetch ────────────────────────────────────────────────────────

def fetch_single_file(
    owner: str, repo: str, branch: str, path: str, token: str | None = None
) -> dict[str, Any]:
    """Fetch a single file's content from GitHub."""
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    result = _get_raw(raw_url, token)
    if result["ok"]:
        result["filename"] = path.split("/")[-1]
        result["path"] = path
    return result


# ─── Repo tree fetch ──────────────────────────────────────────────────────────

MAX_FILES = 200

# All supported code file extensions → language name
CODE_EXTENSIONS: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript",
    ".java": "java", ".c": "c", ".cpp": "cpp", ".cc": "cpp", ".h": "c",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
    ".swift": "swift", ".kt": "kotlin", ".cs": "csharp",
    ".sh": "bash", ".bash": "bash",
    ".html": "html", ".css": "css",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".sql": "sql",
}


def _ext_to_language(path: str) -> str:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return CODE_EXTENSIONS.get(ext, "")


def fetch_repo_tree(
    owner: str, repo: str, branch: str = "main", token: str | None = None
) -> dict[str, Any]:
    """
    Fetch the full recursive file tree for a repo.
    Returns all code files (any supported language), capped at MAX_FILES.
    Auto-retries with 'master' if 'main' returns 404.
    """
    # First, get the default branch commit SHA
    branch = branch or "main"
    branches_to_try = [branch] if branch != "main" else ["main", "master"]
    tree_data = None
    resolved_branch = branch

    for br in branches_to_try:
        # Get branch tip SHA
        ref_result = _get(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{br}",
            token,
        )
        if not ref_result["ok"]:
            continue
        sha = ref_result["data"]["object"]["sha"]
        resolved_branch = br

        # Get recursive tree
        tree_result = _get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1",
            token,
        )
        if tree_result["ok"]:
            tree_data = tree_result["data"]
            break

    if tree_data is None:
        return {
            "ok": False,
            "error": (
                "Could not fetch repository. Check that the URL is correct. "
                "For private repos, add a GitHub token in Settings."
            ),
        }

    # Filter to all supported code files, respect size cap
    code_files = [
        {
            "path": item["path"],
            "size": item.get("size", 0),
            "sha": item.get("sha", ""),
            "filename": item["path"].split("/")[-1],
            "language": _ext_to_language(item["path"]),
        }
        for item in tree_data.get("tree", [])
        if item["type"] == "blob"
        and _ext_to_language(item["path"])  # only known code extensions
        and item.get("size", 0) < 102_400   # skip files > 100 KB
        and not any(p in item["path"] for p in (
            "node_modules/", ".git/", "vendor/", "__pycache__/",
            "dist/", "build/", ".min.js", ".min.css",
        ))
    ]

    truncated = len(code_files) > MAX_FILES or tree_data.get("truncated", False)
    code_files = code_files[:MAX_FILES]

    return {
        "ok": True,
        "files": code_files,
        "branch": resolved_branch,
        "truncated": truncated,
        "total_py_files": len(code_files),  # kept for compat, now means all code files
    }


# ─── Batch file fetcher ───────────────────────────────────────────────────────

def fetch_file_content(
    owner: str, repo: str, branch: str, path: str, token: str | None = None
) -> dict[str, Any]:
    """Fetch one file, return {"path", "content"} or {"path", "error"}."""
    result = fetch_single_file(owner, repo, branch, path, token)
    if result["ok"]:
        return {"path": path, "content": result["content"]}
    return {"path": path, "content": None, "error": result.get("error", "fetch failed")}


# ─── Smart triage ─────────────────────────────────────────────────────────────

def triage_files(
    file_analyses: list[dict[str, Any]],
    max_gemini: int = 5,
) -> dict[str, Any]:
    """
    Split analysed files into flagged / clean and pick top candidates for Gemini.

    Each item in file_analyses must have keys:
      path, content, ast_info, errors, style_score

    Flagging criterion:
      complexity > 10  OR  len(errors) > 0  OR  style_score < 70

    Returns:
      {"flagged": list, "clean": list, "gemini_targets": list (≤ max_gemini)}
    """
    flagged = []
    clean = []

    for item in file_analyses:
        complexity = item.get("ast_info", {}).get("complexity", 0)
        error_count = len(item.get("errors", []))
        style_score = item.get("style_score", 100)

        is_flagged = complexity > 10 or error_count > 0 or style_score < 70
        priority = (
            error_count * 3
            + max(0, complexity - 10) * 2
            + max(0, 70 - style_score) // 10
        )

        enriched = {
            **item,
            "flagged": is_flagged,
            "priority_score": priority,
            "complexity": complexity,
            "error_count": error_count,
            "style_score": style_score,
        }
        if is_flagged:
            flagged.append(enriched)
        else:
            clean.append(enriched)

    # Sort flagged by priority desc
    flagged.sort(key=lambda x: x["priority_score"], reverse=True)
    gemini_targets = flagged[:max_gemini]

    return {"flagged": flagged, "clean": clean, "gemini_targets": gemini_targets}


# ─── Convenience: build repo display name ─────────────────────────────────────

def repo_display_name(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


# ─── Whole-repo snapshot (one zipball request, any language) ─────────────────

SNAPSHOT_MAX_FILES = 300
SNAPSHOT_MAX_FILE_BYTES = 200_000
SNAPSHOT_MAX_ZIP_BYTES = 80 * 1024 * 1024

_SKIP_DIRS = (
    "node_modules/", ".git/", "vendor/", "__pycache__/", "dist/", "build/", "out/",
    "target/", ".venv/", "venv/", ".next/", ".nuxt/", "coverage/", ".idea/", ".vscode/",
    "bower_components/", "Pods/", ".gradle/", "third_party/", "site-packages/", ".web/",
)
_SKIP_SUFFIXES = (
    ".min.js", ".min.css", ".map", ".lock", "-lock.json", ".lockb", ".pb.go", "_pb2.py",
    ".generated.ts", ".d.ts",
)
_SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
               "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum"}


def get_default_branch(owner: str, repo: str, token: str | None = None) -> dict[str, Any]:
    res = _get(f"https://api.github.com/repos/{owner}/{repo}", token)
    if not res["ok"]:
        return res
    data = res["data"]
    return {"ok": True, "branch": data.get("default_branch", "main"),
            "description": data.get("description") or "", "private": data.get("private", False),
            "stars": data.get("stargazers_count", 0)}


def _file_rank(lang: str) -> int:
    """Analyze code first, then markup, then config/docs when over the file cap."""
    from codementor.services import languages
    kind = languages.get(lang).kind
    return {"code": 0, "markup": 1, "data": 2, "docs": 3}.get(kind, 4)


def fetch_repo_snapshot(owner: str, repo: str, branch: str | None = None,
                        subdir: str = "", token: str | None = None) -> dict[str, Any]:
    """
    Download a repository as a zipball and return its analyzable source files:
      {"ok", "files": [{"path", "filename", "content", "language", "size"}],
       "branch", "truncated", "skipped", "description"}
    """
    import io
    import zipfile
    from codementor.services import languages

    meta = {"description": ""}
    if not branch:
        info = get_default_branch(owner, repo, token)
        if not info["ok"]:
            return {"ok": False, "error": info.get("error", "Repository not found.")}
        branch = info["branch"]
        meta["description"] = info.get("description", "")

    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{urllib.parse.quote(branch, safe='')}"
    req = urllib.request.Request(url, headers=_make_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            blob = resp.read(SNAPSHOT_MAX_ZIP_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": f"Branch '{branch}' not found, or the repo is private (add a GitHub token)."}
        if e.code == 403:
            return {"ok": False, "error": "GitHub rate limit or access denied — add a GitHub token in Settings."}
        return {"ok": False, "error": f"GitHub returned HTTP {e.code}."}
    except Exception as e:
        return {"ok": False, "error": f"Download failed: {e}"}
    if len(blob) > SNAPSHOT_MAX_ZIP_BYTES:
        return {"ok": False, "error": "Repository archive is larger than 80 MB — scan a subfolder URL "
                                      "(github.com/owner/repo/tree/<branch>/<folder>) instead."}

    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return {"ok": False, "error": "GitHub returned an invalid archive."}

    subdir = subdir.strip("/")
    candidates, skipped = [], 0
    for entry in zf.infolist():
        if entry.is_dir():
            continue
        # strip the "<owner>-<repo>-<sha>/" prefix GitHub adds
        path = entry.filename.split("/", 1)[1] if "/" in entry.filename else entry.filename
        if subdir and not (path == subdir or path.startswith(subdir + "/")):
            continue
        name = path.rsplit("/", 1)[-1]
        lang = languages.from_filename(path)
        if (not lang or lang == "text" or name in _SKIP_NAMES or path.endswith(_SKIP_SUFFIXES)
                or any(f"/{d}" in f"/{path}" for d in _SKIP_DIRS)):
            continue
        if entry.file_size > SNAPSHOT_MAX_FILE_BYTES or entry.file_size == 0:
            skipped += 1
            continue
        candidates.append((entry, path, name, lang))

    candidates.sort(key=lambda c: (_file_rank(c[3]), c[1].count("/"), c[1]))
    truncated = len(candidates) > SNAPSHOT_MAX_FILES
    files = []
    for entry, path, name, lang in candidates[:SNAPSHOT_MAX_FILES]:
        raw = zf.read(entry)
        if b"\x00" in raw[:4096]:
            skipped += 1
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("latin-1")
        files.append({"path": path, "filename": name, "content": content,
                      "language": lang, "size": entry.file_size})

    files.sort(key=lambda f: f["path"])
    return {"ok": True, "files": files, "branch": branch, "truncated": truncated,
            "skipped": skipped, **meta}
