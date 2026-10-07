"""
Multi-language code runner.

Strategy (first available wins):
  1. Local toolchain on the server — Python, JavaScript, TypeScript (node ≥22
     type-stripping / tsx), Java (single-file launch), C, C++, Go, Rust, Ruby,
     PHP, Bash, Perl, Lua, R, Kotlin script, Swift, Dart, Julia, Scala-cli …
  2. Remote sandbox, if configured:
       PISTON_URL   e.g. https://your-piston-host/api/v2   (self-hosted, free)
       JUDGE0_URL   e.g. https://judge0-ce.p.rapidapi.com  (+ JUDGE0_KEY)
  3. A clear message explaining how to enable the language.

Every local run happens in a fresh temp directory with a scrubbed environment
(no API keys), a wall-clock timeout, and POSIX CPU / file-size limits.
NOTE: subprocess limits are not a security boundary — for a public deployment
configure PISTON_URL / JUDGE0_URL so untrusted code runs in an isolated sandbox
(set RUN_REMOTE_ONLY=1 to disable local execution entirely).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from functools import lru_cache

from codementor.services import languages

TIMEOUT = 10          # seconds for running user code
COMPILE_TIMEOUT = 40  # seconds for compilers (javac/rustc/g++ are slow on first run)
MAX_STDOUT = 10_000
MAX_STDERR = 5_000


# ─── Process helpers ─────────────────────────────────────────────────────────

def _limits():  # pragma: no cover — runs in the child process
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT + 5, TIMEOUT + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:
        pass


def _env(workdir: str) -> dict:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "GOCACHE": os.path.join(workdir, ".gocache"),
        "GOPATH": os.path.join(workdir, ".gopath"),
        "GOFLAGS": "-mod=mod",
        "CARGO_HOME": os.path.join(workdir, ".cargo"),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "NODE_OPTIONS": "--max-old-space-size=256",
    }


def _run(cmd: list[str], cwd: str, stdin: str = "", timeout: int = TIMEOUT) -> dict:
    try:
        res = subprocess.run(
            cmd, cwd=cwd, input=stdin or None, capture_output=True, text=True,
            timeout=timeout, env=_env(cwd),
            preexec_fn=_limits if os.name == "posix" else None,
        )
        return {"stdout": res.stdout[:MAX_STDOUT], "stderr": res.stderr[:MAX_STDERR],
                "returncode": res.returncode, "timed_out": False}
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return {"stdout": out[:MAX_STDOUT], "stderr": f"⏰ Timed out after {timeout}s (infinite loop or waiting for stdin?)",
                "returncode": -1, "timed_out": True}
    except FileNotFoundError as e:
        return {"stdout": "", "stderr": f"Runner not found: {e}", "returncode": -1, "timed_out": False}
    except Exception as e:
        return {"stdout": "", "stderr": f"Runner error: {e}", "returncode": -1, "timed_out": False}


def _which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


@lru_cache(maxsize=1)
def _node_major() -> int:
    node = _which("node")
    if not node:
        return 0
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5).stdout
        return int(out.strip().lstrip("v").split(".")[0])
    except Exception:
        return 0


def _java_class(code: str) -> str:
    m = re.search(r"\bpublic\s+(?:final\s+|abstract\s+)*class\s+(\w+)", code) or \
        re.search(r"\bclass\s+(\w+)[^{]*\{[\s\S]*?static\s+void\s+main\s*\(", code)
    return m.group(1) if m else "Main"


def _strip_ts_types(code: str) -> str:
    """Very rough TS→JS fallback when no TS-capable runtime exists."""
    js = re.sub(r"^\s*(export\s+)?(interface|type)\s+\w+[\s\S]*?^\}\s*$", "", code, flags=re.M)
    js = re.sub(r"^\s*(export\s+)?type\s+\w+\s*=[^;]+;", "", js, flags=re.M)
    js = re.sub(r"(\w)\s*:\s*[A-Za-z_][\w<>\[\]|&., ]*(?=\s*[,)=;{])", r"\1", js)
    js = re.sub(r"\)\s*:\s*[A-Za-z_][\w<>\[\]|&. ]*\s*\{", ") {", js)
    js = re.sub(r"\bas\s+[A-Za-z_][\w<>\[\]]*", "", js)
    js = re.sub(r"\b(public|private|protected|readonly)\s+", "", js)
    return js


# ─── Local runners ───────────────────────────────────────────────────────────
# Each returns a list of (cmd, timeout) steps given (tool, workdir, filename, code)

def _plan(lang: str, code: str):
    """Return (filename, [steps]) where each step is (argv, timeout), or None."""
    py = sys.executable
    if lang == "python":
        return "main.py", [([py, "main.py"], TIMEOUT)]
    if lang == "javascript":
        node = _which("node", "bun", "deno")
        if not node:
            return None
        if node.endswith("deno"):
            return "main.js", [([node, "run", "--quiet", "main.js"], TIMEOUT)]
        ext = "main.mjs" if re.search(r"^\s*(import|export)\s", code, re.M) else "main.js"
        return ext, [([node, ext], TIMEOUT)]
    if lang == "typescript":
        if tsx := _which("tsx", "bun", "deno"):
            if tsx.endswith("deno"):
                return "main.ts", [([tsx, "run", "--quiet", "main.ts"], TIMEOUT)]
            return "main.ts", [([tsx, "main.ts"], TIMEOUT)]
        node = _which("node")
        if node and _node_major() >= 22:
            flags = [] if _node_major() >= 23 else ["--experimental-strip-types", "--no-warnings"]
            return "main.ts", [([node, *flags, "main.ts"], TIMEOUT)]
        if node:
            return ("__ts_strip__", [([node, "main.mjs"], TIMEOUT)])
        return None
    if lang == "java":
        java = _which("java")
        if not java:
            return None
        name = _java_class(code)
        return f"{name}.java", [([java, f"{name}.java"], COMPILE_TIMEOUT)]
    if lang in ("c", "cpp"):
        cc = _which("gcc", "clang", "cc") if lang == "c" else _which("g++", "clang++", "c++")
        if not cc:
            return None
        src = "main.c" if lang == "c" else "main.cpp"
        std = "-std=c17" if lang == "c" else "-std=c++20"
        return src, [([cc, std, "-O1", "-o", "main", src, "-lm"], COMPILE_TIMEOUT), (["./main"], TIMEOUT)]
    if lang == "go":
        go = _which("go")
        return ("main.go", [([go, "run", "main.go"], COMPILE_TIMEOUT)]) if go else None
    if lang == "rust":
        rustc = _which("rustc")
        if not rustc:
            return None
        return "main.rs", [([rustc, "--edition", "2021", "-O", "-o", "main", "main.rs"], COMPILE_TIMEOUT),
                           (["./main"], TIMEOUT)]
    if lang == "csharp":
        script = _which("dotnet-script")
        return ("main.csx", [([script, "main.csx"], COMPILE_TIMEOUT)]) if script else None
    if lang == "kotlin":
        kotlinc = _which("kotlinc")
        return ("main.kts", [([kotlinc, "-script", "main.kts"], COMPILE_TIMEOUT)]) if kotlinc else None
    if lang == "swift":
        swift = _which("swift")
        return ("main.swift", [([swift, "main.swift"], COMPILE_TIMEOUT)]) if swift else None
    if lang == "scala":
        sc = _which("scala-cli", "scala")
        if not sc:
            return None
        return "main.sc", [([sc, "run", "main.sc"] if sc.endswith("scala-cli") else [sc, "main.sc"], COMPILE_TIMEOUT)]
    simple = {
        "ruby": (("ruby",), "main.rb"), "php": (("php",), "main.php"),
        "bash": (("bash", "sh"), "main.sh"), "perl": (("perl",), "main.pl"),
        "lua": (("lua", "luajit", "lua5.4"), "main.lua"), "r": (("Rscript",), "main.R"),
        "julia": (("julia",), "main.jl"), "dart": (("dart",), "main.dart"),
        "elixir": (("elixir",), "main.exs"), "powershell": (("pwsh",), "main.ps1"),
        "haskell": (("runghc", "runhaskell"), "main.hs"),
    }
    if lang in simple:
        tools, fname = simple[lang]
        tool = _which(*tools)
        if not tool:
            return None
        argv = [tool, "run", fname] if lang == "dart" else [tool, fname]
        return fname, [(argv, COMPILE_TIMEOUT if lang in ("haskell", "julia", "dart") else TIMEOUT)]
    return None


def _run_local(code: str, lang: str, stdin: str) -> dict | None:
    plan = _plan(lang, code)
    if plan is None:
        return None
    fname, steps = plan
    with tempfile.TemporaryDirectory(prefix="cm-run-") as work:
        if fname == "__ts_strip__":
            fname, code = "main.mjs", _strip_ts_types(code)
        with open(os.path.join(work, fname), "w", encoding="utf-8") as f:
            f.write(code)
        result = {"stdout": "", "stderr": "", "returncode": 0, "timed_out": False}
        for i, (argv, timeout) in enumerate(steps):
            is_last = i == len(steps) - 1
            result = _run(argv, work, stdin if is_last else "", timeout)
            if result["returncode"] != 0 and not is_last:
                result["stderr"] = "❌ Compilation failed:\n" + result["stderr"]
                break
        result["runner"] = f"local · {os.path.basename(steps[0][0][0])}"  # compiler/interpreter name
        return result


# ─── Remote sandboxes ────────────────────────────────────────────────────────

_PISTON_NAMES = {
    "python": "python", "javascript": "javascript", "typescript": "typescript", "java": "java",
    "c": "c", "cpp": "c++", "csharp": "csharp", "go": "go", "rust": "rust", "kotlin": "kotlin",
    "swift": "swift", "ruby": "ruby", "php": "php", "scala": "scala", "dart": "dart", "lua": "lua",
    "perl": "perl", "r": "r", "julia": "julia", "haskell": "haskell", "elixir": "elixir",
    "erlang": "erlang", "clojure": "clojure", "ocaml": "ocaml", "bash": "bash",
    "powershell": "powershell", "sql": "sqlite3", "fortran": "fortran", "groovy": "groovy",
    "zig": "zig", "objectivec": "objective-c",
}
# Judge0 CE language ids
_JUDGE0_IDS = {
    "python": 71, "javascript": 63, "typescript": 74, "java": 62, "c": 50, "cpp": 54,
    "csharp": 51, "go": 60, "rust": 73, "kotlin": 78, "swift": 83, "ruby": 72, "php": 68,
    "scala": 81, "lua": 64, "perl": 85, "r": 80, "haskell": 61, "elixir": 57, "erlang": 58,
    "clojure": 86, "ocaml": 65, "bash": 46, "sql": 82, "fortran": 59, "groovy": 88,
    "objectivec": 79, "dart": 90,
}


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _run_piston(code: str, lang: str, stdin: str) -> dict | None:
    base = os.environ.get("PISTON_URL", "").rstrip("/")
    name = _PISTON_NAMES.get(lang)
    if not base or not name:
        return None
    headers = {"Authorization": os.environ["PISTON_KEY"]} if os.environ.get("PISTON_KEY") else {}
    try:
        data = _post_json(f"{base}/execute", {
            "language": name, "version": "*",
            "files": [{"name": f"main{languages.default_extension(lang)}", "content": code}],
            "stdin": stdin, "run_timeout": TIMEOUT * 1000, "compile_timeout": COMPILE_TIMEOUT * 1000,
        }, headers, timeout=COMPILE_TIMEOUT + TIMEOUT + 10)
    except urllib.error.HTTPError as e:
        return {"stdout": "", "stderr": f"Piston error HTTP {e.code}: {e.read()[:300].decode(errors='replace')}",
                "returncode": -1, "timed_out": False, "runner": "piston"}
    except Exception as e:
        return {"stdout": "", "stderr": f"Piston unreachable: {e}", "returncode": -1,
                "timed_out": False, "runner": "piston"}
    compile_ = data.get("compile") or {}
    if compile_.get("code"):
        return {"stdout": "", "stderr": "❌ Compilation failed:\n" + (compile_.get("output") or "")[:MAX_STDERR],
                "returncode": compile_.get("code", 1), "timed_out": False, "runner": "piston"}
    run = data.get("run") or {}
    return {"stdout": (run.get("stdout") or "")[:MAX_STDOUT], "stderr": (run.get("stderr") or "")[:MAX_STDERR],
            "returncode": run.get("code") if run.get("code") is not None else (1 if run.get("signal") else 0),
            "timed_out": run.get("signal") == "SIGKILL", "runner": f"piston · {data.get('language', name)} {data.get('version', '')}"}


def _run_judge0(code: str, lang: str, stdin: str) -> dict | None:
    base = os.environ.get("JUDGE0_URL", "").rstrip("/")
    lang_id = _JUDGE0_IDS.get(lang)
    if not base or not lang_id:
        return None
    headers = {}
    if key := os.environ.get("JUDGE0_KEY"):
        if "rapidapi" in base:
            headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": base.split("//", 1)[-1].split("/")[0]}
        else:
            headers = {"X-Auth-Token": key}
    try:
        data = _post_json(f"{base}/submissions?base64_encoded=false&wait=true", {
            "source_code": code, "language_id": lang_id, "stdin": stdin,
            "cpu_time_limit": TIMEOUT, "wall_time_limit": TIMEOUT + 5,
        }, headers, timeout=COMPILE_TIMEOUT + TIMEOUT + 10)
    except Exception as e:
        return {"stdout": "", "stderr": f"Judge0 unreachable: {e}", "returncode": -1,
                "timed_out": False, "runner": "judge0"}
    status = (data.get("status") or {}).get("description", "")
    stderr = (data.get("compile_output") or "") + (data.get("stderr") or "")
    ok = status == "Accepted"
    return {"stdout": (data.get("stdout") or "")[:MAX_STDOUT],
            "stderr": (stderr if ok else f"{status}\n{stderr}")[:MAX_STDERR],
            "returncode": 0 if ok else (data.get("exit_code") or 1),
            "timed_out": "Time Limit" in status, "runner": "judge0"}


# ─── Public API ──────────────────────────────────────────────────────────────

_INSTALL_HINTS = {
    "java": "a JDK (java 11+)", "c": "gcc or clang", "cpp": "g++ or clang++", "go": "Go",
    "rust": "rustc", "csharp": "dotnet-script", "kotlin": "kotlinc", "swift": "Swift",
    "typescript": "Node.js 22+ or tsx", "javascript": "Node.js",
}


def available_runtimes() -> dict[str, str]:
    """Which languages can run right now and how (for the UI/docs)."""
    out = {}
    for lang in languages.LANGUAGE_IDS:
        if os.environ.get("RUN_REMOTE_ONLY") != "1" and _plan(lang, "") is not None:
            out[lang] = "local"
        elif os.environ.get("PISTON_URL") and lang in _PISTON_NAMES:
            out[lang] = "piston"
        elif os.environ.get("JUDGE0_URL") and lang in _JUDGE0_IDS:
            out[lang] = "judge0"
    return out


def run_code(code: str, language: str = "python", timeout: int = TIMEOUT, stdin: str = "") -> dict:
    lang = languages.normalize(language)
    if not code.strip():
        return {"stdout": "", "stderr": "Nothing to run — the editor is empty.", "returncode": 0, "timed_out": False}
    if not languages.is_code(lang) or lang in ("dockerfile", "makefile"):
        return {"stdout": "", "stderr": f"{languages.label(lang)} isn't an executable language. Use 🔍 Analyze to review it.",
                "returncode": 0, "timed_out": False}

    if os.environ.get("RUN_REMOTE_ONLY") != "1":
        local = _run_local(code, lang, stdin)
        if local is not None:
            return local
    for remote in (_run_piston, _run_judge0):
        res = remote(code, lang, stdin)
        if res is not None:
            return res

    need = _INSTALL_HINTS.get(lang, f"a {languages.label(lang)} toolchain")
    return {
        "stdout": "",
        "stderr": (
            f"⚡ {languages.label(lang)} can't be executed on this server yet.\n\n"
            f"Enable it by either:\n"
            f"  • installing {need} on the server, or\n"
            f"  • setting PISTON_URL (self-hosted Piston) or JUDGE0_URL (+ JUDGE0_KEY) for a remote sandbox.\n\n"
            f"🔍 Analyze still gives you a full review, CFG and AI suggestions for this language."
        ),
        "returncode": 0, "timed_out": False,
    }


# Backwards-compatible helpers
def run_python_code(code: str, timeout: int = TIMEOUT, stdin: str = "") -> dict:
    return run_code(code, "python", timeout, stdin)


def run_javascript_code(code: str, timeout: int = TIMEOUT, stdin: str = "") -> dict:
    return run_code(code, "javascript", timeout, stdin)


def run_typescript_code(code: str, timeout: int = TIMEOUT, stdin: str = "") -> dict:
    return run_code(code, "typescript", timeout, stdin)


def format_terminal_output(result: dict) -> str:
    parts = []
    if result.get("runner"):
        parts.append(f"▶ {result['runner']}\n")
    if result["stdout"]:
        parts.append(result["stdout"])
    if result["returncode"] != 0:
        if result["stderr"]:
            parts.append(f"\n--- stderr ---\n{result['stderr']}")
        if not result["timed_out"]:
            parts.append(f"\n[Process exited with code {result['returncode']}]")
    elif result["stderr"]:
        parts.append(("\n--- stderr ---\n" if result["stdout"] else "") + result["stderr"])
    elif not result["stdout"]:
        parts.append("(no output)")
    return "".join(parts)
