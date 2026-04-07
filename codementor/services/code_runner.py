"""
Multi-language code runner.
Supports: Python, JavaScript, TypeScript (via Node.js).
Others: returns a helpful message explaining how to run locally.
"""

import subprocess
import sys
import shutil
import tempfile
import os

TIMEOUT = 10  # seconds

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _run(cmd: list[str], input_code: str | None = None,
         cwd: str | None = None, timeout: int = TIMEOUT) -> dict:
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "NODE_PATH": "",
    }
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=safe_env,
            cwd=cwd,
            input=input_code,
        )
        return {
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
            "returncode": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"⏰ Timed out after {timeout}s.", "returncode": -1, "timed_out": True}
    except FileNotFoundError as e:
        return {"stdout": "", "stderr": f"Runner not found: {e}", "returncode": -1, "timed_out": False}
    except Exception as e:
        return {"stdout": "", "stderr": f"Runner error: {e}", "returncode": -1, "timed_out": False}


# ─── Per-language runners ─────────────────────────────────────────────────────

def run_python_code(code: str, timeout: int = TIMEOUT, stdin: str = "") -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                    delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        return _run([sys.executable, path], input_code=stdin or None, timeout=timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_javascript_code(code: str, timeout: int = TIMEOUT, stdin: str = "") -> dict:
    node = shutil.which("node")
    if not node:
        return {"stdout": "", "stderr": "Node.js not installed on this server.",
                "returncode": -1, "timed_out": False}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mjs",
                                    delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        return _run([node, path], input_code=stdin or None, timeout=timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_typescript_code(code: str, timeout: int = TIMEOUT, stdin: str = "") -> dict:
    """Run TS by stripping type annotations and running as JS."""
    import re
    js = re.sub(r":\s*[A-Za-z<>\[\]|&]+(?=[\s,)=;{])", "", code)
    js = re.sub(r"<[A-Za-z,\s]+>(?=\()", "", js)
    js = re.sub(r"\binterface\s+\w+\s*\{[^}]*\}", "", js, flags=re.DOTALL)
    js = re.sub(r"\btype\s+\w+\s*=\s*[^;]+;", "", js)
    return run_javascript_code(js, timeout, stdin=stdin)


def _not_supported(language: str) -> dict:
    tips = {
        "java":   "javac MyFile.java && java MyFile",
        "c":      "gcc file.c -o file && ./file",
        "cpp":    "g++ file.cpp -o file && ./file",
        "go":     "go run file.go",
        "rust":   "rustc file.rs && ./file",
    }
    tip = tips.get(language, f"Use your local {language} toolchain")
    return {
        "stdout": "",
        "stderr": (
            f"⚡ Live execution for {language.upper()} isn't available in the browser sandbox.\n\n"
            f"To run locally:  {tip}\n\n"
            f"Tip: Use 'Analyze' to get AI code review without running."
        ),
        "returncode": 0,
        "timed_out": False,
    }


# ─── Unified entry point ──────────────────────────────────────────────────────

def run_code(code: str, language: str = "python",
             timeout: int = TIMEOUT, stdin: str = "") -> dict:
    if language == "python":
        return run_python_code(code, timeout, stdin=stdin)
    elif language == "javascript":
        return run_javascript_code(code, timeout, stdin=stdin)
    elif language == "typescript":
        return run_typescript_code(code, timeout, stdin=stdin)
    else:
        return _not_supported(language)


def format_terminal_output(result: dict) -> str:
    parts = []
    if result["stdout"]:
        parts.append(result["stdout"])
    if result["returncode"] != 0:
        if result["stderr"]:
            parts.append(f"\n--- stderr ---\n{result['stderr']}")
        if not result["timed_out"]:
            parts.append(f"\n[Process exited with code {result['returncode']}]")
    elif not result["stdout"] and result["stderr"]:
        parts.append(result["stderr"])
    elif not result["stdout"]:
        parts.append("(no output)")
    return "".join(parts)
