"""
Free, key-less remote sandboxes for running code in any language.

  • Wandbox            (wandbox.org)  — ~35 languages
  • Compiler Explorer  (godbolt.org)  — ~60 languages with execution

Both run code in isolated containers on their own infrastructure, so untrusted
user code never touches this server (and can't read its environment or keys).
Compilers are discovered from each service's catalogue and cached, so new
compiler versions are picked up automatically and retired ones never break us.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

_UA = {"User-Agent": "CodeMentor-AI/2.0 (+https://github.com/SagarSwain05/CodeMentor-AI)"}
_CATALOG_TTL = 6 * 3600
MAX_STDOUT = 10_000
MAX_STDERR = 5_000

# language id → (Wandbox language name, Compiler Explorer language id)
LANG_MAP: dict[str, tuple[str | None, str | None]] = {
    "python": ("Python", "python"),
    "javascript": ("JavaScript", None),
    "typescript": ("TypeScript", "typescript"),
    "java": ("Java", "java"),
    "c": ("C", "c"),
    "cpp": ("C++", "c++"),
    "csharp": ("C#", "csharp"),
    "go": ("Go", "go"),
    "rust": ("Rust", "rust"),
    "kotlin": (None, "kotlin"),
    "swift": ("Swift", "swift"),
    "ruby": ("Ruby", "ruby"),
    "php": ("PHP", None),
    "scala": ("Scala", "scala"),
    "dart": (None, "dart"),
    "lua": ("Lua", "lua"),
    "perl": ("Perl", "perl"),
    "r": ("R", None),
    "julia": ("Julia", "julia"),
    "haskell": ("Haskell", "haskell"),
    "elixir": ("Elixir", None),
    "erlang": ("Erlang", None),
    "clojure": (None, "clojure"),
    "ocaml": ("OCaml", "ocaml"),
    "objectivec": (None, "objc"),
    "zig": ("Zig", "zig"),
    "fortran": (None, "fortran"),
    "groovy": ("Groovy", None),
    "bash": ("Bash script", None),
    "sql": ("SQL", None),
    "d": ("D", "d"),
    "nim": ("Nim", None),
    "crystal": ("Crystal", "crystal"),
    "pascal": ("Pascal", "pascal"),
    "commonlisp": ("Lisp", None),
    "fsharp": (None, "fsharp"),
    "cobol": (None, "cobol"),
    "ada": (None, "ada"),
}

# Wandbox compiler preferences per language (regex, in order); first match wins
_WANDBOX_PREFS = {
    "C": [r"^gcc-\d[\d.]*-c$", r"^gcc-head-c$"],
    "C++": [r"^gcc-\d[\d.]*$", r"^gcc-head$", r"^clang-\d"],
    "Python": [r"^cpython-3\.\d+\.\d+$"],
    "C#": [r"^dotnetcore-", r"^mono-"],
    "Ruby": [r"^ruby-\d"],
    "Lisp": [r"^sbcl-", r"^clisp-"],
    "D": [r"^ldc-", r"^dmd-"],
}

# Compiler Explorer preferences when a language's default compiler can't execute
_GODBOLT_PREFS = {
    "go": [r"^gl\d", r"^gccgo"],
    "rust": [r"^r\d{3,}$"],
    "python": [r"^python3\d+$"],
    "csharp": [r"dotnet.*csharpcoreclr", r"dotnet.*csharp"],
    "fsharp": [r"dotnet.*fsharpcoreclr", r"dotnet.*fsharp"],
    "java": [r"^java\d{3,}$"],
    "c++": [r"^g\d{2,}$"],
    "c": [r"^cg\d{2,}$"],
}

_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


def _http(url: str, payload: dict | None = None, timeout: int = 60) -> object:
    headers = {**_UA, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _cached(key: str, loader):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < _CATALOG_TTL:
            return hit[1]
    value = loader()
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def _version_key(name: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", name)[:4]) or (0,)


# ─── Wandbox ─────────────────────────────────────────────────────────────────

def _wandbox_compilers() -> dict[str, str]:
    """Wandbox language name → chosen compiler id."""
    def load():
        catalog = _http("https://wandbox.org/api/list.json", timeout=20)
        by_lang: dict[str, list[str]] = {}
        for c in catalog:
            by_lang.setdefault(c["language"], []).append(c["name"])
        chosen = {}
        for lang, names in by_lang.items():
            pick = None
            for pref in _WANDBOX_PREFS.get(lang, []):
                matches = [n for n in names if re.search(pref, n)]
                if matches:
                    pick = max(matches, key=_version_key)
                    break
            if not pick:
                stable = [n for n in names if "head" not in n and "dev" not in n] or names
                pick = stable[0]  # Wandbox lists newest first
            chosen[lang] = pick
        return chosen
    return _cached("wandbox", load)


def run_wandbox(code: str, lang_id: str, stdin: str = "", timeout: int = 60,
                extra: dict | None = None) -> dict | None:
    name = LANG_MAP.get(lang_id, (None, None))[0]
    if not name:
        return None
    try:
        compiler = _wandbox_compilers().get(name)
    except Exception:
        return None  # catalogue unreachable → let the next provider try
    if not compiler:
        return None
    payload = {"compiler": compiler, "code": code, "stdin": stdin, "save": False, **(extra or {})}
    if lang_id == "java":
        # Wandbox compiles prog.java; a `public class X` must live in X.java
        m = re.search(r"\bpublic\s+(?:final\s+)?class\s+(\w+)", code)
        if m and m.group(1) != "prog":
            payload["code"] = re.sub(r"\bpublic\s+((?:final\s+)?class\s+" + m.group(1) + r")\b", r"\1", code, count=1)
    try:
        r = _http("https://wandbox.org/api/compile.json", payload, timeout=timeout)
    except Exception as e:
        return {"stdout": "", "stderr": f"Wandbox unavailable: {e}", "returncode": -1,
                "timed_out": False, "runner": "wandbox", "unavailable": True}
    status = str(r.get("status", "0"))
    signal = r.get("signal", "")
    compile_err = (r.get("compiler_error", "") or "") or (r.get("compiler_message", "") or "")
    stderr = (r.get("program_error", "") or "")
    rc = int(status) if status.lstrip("-").isdigit() else 1
    if compile_err and not r.get("program_output") and rc != 0:
        stderr = "❌ Compilation failed:\n" + compile_err + stderr
    return {
        "stdout": (r.get("program_output", "") or "")[:MAX_STDOUT],
        "stderr": stderr[:MAX_STDERR],
        "returncode": rc if not signal else 1,
        "timed_out": signal in ("Killed", "SIGKILL", "SIGXCPU"),
        "runner": f"Wandbox · {compiler}",
    }


# ─── Compiler Explorer ───────────────────────────────────────────────────────

def _godbolt_compilers() -> dict[str, str]:
    """Compiler Explorer language id → chosen executable compiler id."""
    def load():
        langs = _http("https://godbolt.org/api/languages?fields=id,defaultCompiler", timeout=30)
        comps = _http("https://godbolt.org/api/compilers?fields=id,lang,supportsExecute,semver", timeout=40)
        execs: dict[str, list[dict]] = {}
        for c in comps:
            if c.get("supportsExecute"):
                execs.setdefault(c["lang"], []).append(c)
        chosen = {}
        for lang in langs:
            options = execs.get(lang["id"], [])
            if not options:
                continue
            ids = [c["id"] for c in options]
            default = lang.get("defaultCompiler")
            pick = default if default in ids else None
            if not pick:
                for pref in _GODBOLT_PREFS.get(lang["id"], []):
                    matches = [c for c in options if re.search(pref, c["id"])]
                    if matches:
                        pick = max(matches, key=lambda c: _version_key(c.get("semver") or c["id"]))["id"]
                        break
            if not pick:
                numbered = [c for c in options if re.search(r"\d", c.get("semver") or "")]
                pick = max(numbered or options, key=lambda c: _version_key(c.get("semver") or c["id"]))["id"]
            chosen[lang["id"]] = pick
        return chosen
    return _cached("godbolt", load)


def run_godbolt(code: str, lang_id: str, stdin: str = "", timeout: int = 90) -> dict | None:
    gb_lang = LANG_MAP.get(lang_id, (None, None))[1]
    if not gb_lang:
        return None
    try:
        compiler = _godbolt_compilers().get(gb_lang)
    except Exception:
        return None
    if not compiler:
        return None
    payload = {
        "source": code,
        "options": {
            "userArguments": "",
            "executeParameters": {"args": [], "stdin": stdin},
            "compilerOptions": {"executorRequest": True, "skipAsm": True},
            "filters": {"execute": True},
            "tools": [], "libraries": [],
        },
        "lang": gb_lang,
        "allowStoreCodeDebug": False,
    }
    try:
        r = _http(f"https://godbolt.org/api/compiler/{compiler}/compile", payload, timeout=timeout)
    except Exception as e:
        return {"stdout": "", "stderr": f"Compiler Explorer unavailable: {e}", "returncode": -1,
                "timed_out": False, "runner": "compiler-explorer", "unavailable": True}

    def text(lines):
        return "\n".join(item.get("text", "") for item in (lines or []))

    build = r.get("buildResult") or {}
    if build.get("code", 0) != 0 or (not r.get("didExecute", True) and build):
        msg = text(build.get("stderr")) or text(build.get("stdout")) or "Build failed"
        return {"stdout": "", "stderr": "❌ Compilation failed:\n" + msg[:MAX_STDERR],
                "returncode": build.get("code", 1) or 1, "timed_out": False,
                "runner": f"Compiler Explorer · {compiler}"}
    stdout = text(r.get("stdout"))
    if stdout:
        stdout += "\n"
    return {
        "stdout": stdout[:MAX_STDOUT],
        "stderr": text(r.get("stderr"))[:MAX_STDERR],
        "returncode": r.get("code", 0) if r.get("code") is not None else 0,
        "timed_out": bool(r.get("timedOut")),
        "runner": f"Compiler Explorer · {compiler}",
    }


# ─── Paiza.IO (public "guest" key) ───────────────────────────────────────────

_PAIZA_NAMES = {
    "python": "python3", "javascript": "javascript", "typescript": "typescript", "java": "java",
    "c": "c", "cpp": "cpp", "csharp": "csharp", "go": "go", "rust": "rust", "kotlin": "kotlin",
    "swift": "swift", "ruby": "ruby", "php": "php", "scala": "scala", "perl": "perl", "r": "r",
    "haskell": "haskell", "elixir": "elixir", "erlang": "erlang", "clojure": "clojure",
    "bash": "bash", "objectivec": "objective-c", "fsharp": "fsharp", "cobol": "cobol", "d": "d",
    "commonlisp": "commonlisp", "sql": "mysql", "dart": "dart",
}


def _paiza(method: str, path: str, params: dict, timeout: int = 30) -> dict:
    import urllib.parse
    data = urllib.parse.urlencode(params)
    url = f"https://api.paiza.io/runners/{path}"
    req = urllib.request.Request(
        url if method == "POST" else f"{url}?{data}",
        data=data.encode() if method == "POST" else None, headers=_UA, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def run_paiza(code: str, lang_id: str, stdin: str = "", timeout: int = 60) -> dict | None:
    name = _PAIZA_NAMES.get(lang_id)
    if not name:
        return None
    if lang_id == "erlang":
        code = re.sub(r"-module\(\s*\w+\s*\)", "-module(main)", code, count=1)
    try:
        created = _paiza("POST", "create", {
            "source_code": code, "language": name, "input": stdin,
            "longpoll": "true", "longpoll_timeout": "20", "api_key": "guest"})
        if created.get("error"):
            raise RuntimeError(created["error"])
        deadline = time.time() + timeout
        details = {}
        while time.time() < deadline:
            details = _paiza("GET", "get_details", {"id": created["id"], "api_key": "guest"})
            if details.get("status") == "completed":
                break
            time.sleep(1)
        else:
            raise TimeoutError("no result")
    except Exception as e:
        return {"stdout": "", "stderr": f"Paiza.IO unavailable: {e}", "returncode": -1,
                "timed_out": False, "runner": "paiza", "unavailable": True}

    if details.get("build_result") == "failure":
        msg = details.get("build_stderr") or details.get("build_stdout") or "Build failed"
        return {"stdout": "", "stderr": "❌ Compilation failed:\n" + msg[:MAX_STDERR],
                "returncode": details.get("build_exit_code") or 1, "timed_out": False, "runner": f"Paiza.IO · {name}"}
    stdout = details.get("stdout") or ""
    result = details.get("result")
    timed_out = result == "timeout" and not stdout  # e.g. Erlang keeps its VM alive after printing
    return {
        "stdout": stdout[:MAX_STDOUT],
        "stderr": (details.get("stderr") or "")[:MAX_STDERR],
        "returncode": 0 if (result == "success" or (result == "timeout" and stdout)) else (details.get("exit_code") or 1),
        "timed_out": timed_out,
        "runner": f"Paiza.IO · {name}",
    }


# ─── TIO — Try It Online (last-resort fallback, ~680 languages) ──────────────

_TIO_NAMES = {
    "python": "python3", "javascript": "javascript-node", "typescript": "typescript", "java": "java-openjdk",
    "c": "c-gcc", "cpp": "cpp-gcc", "csharp": "cs-core", "go": "go", "rust": "rust", "kotlin": "kotlin",
    "swift": "swift4", "ruby": "ruby", "php": "php", "scala": "scala", "lua": "lua", "perl": "perl5",
    "r": "r", "julia": "julia1x", "haskell": "haskell", "elixir": "elixir", "erlang": "erlang-escript",
    "bash": "bash", "ocaml": "ocaml", "clojure": "clojure", "fortran": "fortran-gfortran",
    "groovy": "groovy", "sql": "sqlite", "objectivec": "objective-c-gcc", "fsharp": "fs-core",
    "cobol": "cobol-gnu", "d": "d", "nim": "nim", "crystal": "crystal", "pascal": "pascal-fpc",
    "commonlisp": "clisp", "ada": "ada-gnat", "powershell": "powershell", "zig": "zig",
}


def run_tio(code: str, lang_id: str, stdin: str = "", timeout: int = 60) -> dict | None:
    import zlib
    name = _TIO_NAMES.get(lang_id)
    if not name:
        return None

    def var(key, values):
        return f"V{key}\0{len(values)}\0".encode() + b"".join(v.encode() + b"\0" for v in values)

    def file(key, content):
        data = content.encode()
        return f"F{key}\0{len(data)}\0".encode() + data

    payload = var("lang", [name]) + file(".code.tio", code) + file(".input.tio", stdin) + var("args", []) + b"R"
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    body = compressor.compress(payload) + compressor.flush()
    try:
        req = urllib.request.Request("https://tio.run/cgi-bin/run/api/", data=body, headers=_UA, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        try:
            raw = zlib.decompress(raw, 31)
        except zlib.error:
            pass
        text = raw.decode("utf-8", "replace")
        delim, rest = text[:16], text[16:]
        parts = rest.split(delim)
    except Exception as e:
        return {"stdout": "", "stderr": f"TIO unavailable: {e}", "returncode": -1,
                "timed_out": False, "runner": "tio", "unavailable": True}
    stdout = parts[0] if parts else ""
    debug = parts[1] if len(parts) > 1 else ""
    m = re.search(r"Exit code: (-?\d+)", debug)
    stderr = re.split(r"\n?Real time:", debug)[0].strip()
    rc = int(m.group(1)) if m else (0 if stdout else 1)
    return {
        "stdout": stdout[:MAX_STDOUT],
        "stderr": stderr[:MAX_STDERR],
        "returncode": rc,
        "timed_out": "timed out" in debug.lower() or "killed" in debug.lower(),
        "runner": f"TIO · {name}",
    }


# ─── Routing ─────────────────────────────────────────────────────────────────
# Ordered providers per language, chosen from a verified matrix (tests/run_samples.py):
# the first entry is the fastest provider that runs the language correctly.

_G, _W, _P, _T = "godbolt", "wandbox", "paiza", "tio"
ROUTES: dict[str, list[str]] = {
    "python": [_G, _W, _P], "javascript": [_W, _P], "typescript": [_W],
    "java": [_G, _W, _P], "c": [_G, _W, _P], "cpp": [_G, _W, _P], "csharp": [_G, _P],
    "go": [_G, _W, _P], "rust": [_G, _W, _P], "kotlin": [_G, _P], "swift": [_G, _P],
    "ruby": [_G, _W, _P], "php": [_W, _P], "scala": [_P], "dart": [_G],
    "lua": [_G, _W], "perl": [_G, _W, _P], "r": [_W, _P], "julia": [_W, _G],
    "haskell": [_G, _W, _P], "elixir": [_P], "erlang": [_P], "bash": [_W, _P],
    "zig": [_G, _W], "ocaml": [_G, _W], "clojure": [_T, _P], "fortran": [_G],
    "groovy": [_W], "sql": [_W, _P], "objectivec": [_G, _P], "fsharp": [_G, _P],
    "cobol": [_G, _P], "d": [_G, _W, _P], "nim": [_W], "crystal": [_G, _W],
    "pascal": [_G, _W], "commonlisp": [_W, _P], "ada": [_G], "powershell": [_T],
}
# TIO is the universal last resort wherever it supports the language
for _lang, _order in ROUTES.items():
    if _lang in _TIO_NAMES and _T not in _order:
        _order.append(_T)

# Signatures of provider-side toolchain breakage (not the user's bug) → try the next provider
_INFRA_ERRORS = re.compile(
    r"unavailable|NoClassDefFoundError: scala|run-\w+\.sh|setlocale|UNREACHABLE executed|"
    r"Could not find or load main class|HTTP Error 5\d\d|Too Many Requests|internal error", re.I)


def _prepare(code: str, lang_id: str, provider: str) -> tuple[str, dict]:
    extra: dict = {}
    if lang_id == "java" and provider == _G:
        # Compiler Explorer compiles example.java: a public class must not be named otherwise
        code = re.sub(r"\bpublic\s+((?:final\s+)?class\s+\w+)", r"\1", code, count=1)
    if lang_id == "typescript" and provider == _W:
        extra["compiler-option-raw"] = "--noCheck"  # run like ts-node --transpile-only; types are checked by Analyze
    return code, extra


def run_remote(code: str, lang_id: str, stdin: str = "") -> dict | None:
    """Run code on the best remote sandbox for the language, failing over between providers."""
    order = ROUTES.get(lang_id)
    if not order:
        return None
    last = None
    for provider in order:
        src, extra = _prepare(code, lang_id, provider)
        if provider == _W:
            result = run_wandbox(src, lang_id, stdin, extra=extra)
        elif provider == _G:
            result = run_godbolt(src, lang_id, stdin)
        elif provider == _T:
            result = run_tio(src, lang_id, stdin)
        else:
            result = run_paiza(src, lang_id, stdin)
            if result and result["timed_out"] and not result["stdout"]:
                # JVM languages (Clojure, Scala) can exceed Paiza's limit on a cold start; retry warm
                result = run_paiza(src, lang_id, stdin)
        if result is None:
            continue
        last = result
        infra = result.get("unavailable") or (
            not result["stdout"] and _INFRA_ERRORS.search(result["stderr"] or ""))
        if not infra:
            return result
    return last


def supported_languages() -> set[str]:
    return set(ROUTES)
