"""
Tests for the multi-language analysis pipeline.

Run:  python -m pytest -q tests/
Tests that need tree-sitter / lizard are skipped automatically if missing.
"""

import os
import sys

import pytest

from codementor.services import languages, syntax_service
from codementor.services.analysis_pipeline import analyze_source, triage
from codementor.services.cfg_service import build_cfg
from codementor.services.code_runner import run_code
from codementor.services.complexity_service import HAS_LIZARD, function_metrics
from codementor.services.github_service import parse_github_url
from codementor.services.linter_service import check_errors, check_style, style_score
from codementor.services.security_service import check_security

needs_ts = pytest.mark.skipif(not syntax_service.HAS_TREE_SITTER, reason="tree-sitter not installed")
needs_lizard = pytest.mark.skipif(not HAS_LIZARD, reason="lizard not installed")

SAMPLES = {
    "python": "def f(x):\n    if x > 1:\n        return x\n    return 0\n",
    "javascript": "function f(x) {\n  if (x > 1) { return x; }\n  return 0;\n}\nconsole.log(f(2));\n",
    "typescript": "function f(x: number): number {\n  if (x > 1) { return x; }\n  return 0;\n}\n",
    "java": "public class Main {\n  public static void main(String[] a) {\n    for (int i = 0; i < 3; i++) {\n      System.out.println(i);\n    }\n  }\n}\n",
    "c": "#include <stdio.h>\nint main(void) {\n  int i;\n  for (i = 0; i < 3; i++) { printf(\"%d\\n\", i); }\n  return 0;\n}\n",
    "cpp": "#include <iostream>\nint main() {\n  for (int i = 0; i < 3; i++) std::cout << i << std::endl;\n  return 0;\n}\n",
    "go": "package main\n\nimport \"fmt\"\n\nfunc main() {\n\tfor i := 0; i < 3; i++ {\n\t\tfmt.Println(i)\n\t}\n}\n",
    "rust": "fn main() {\n    let mut x = 0;\n    while x < 3 {\n        println!(\"{}\", x);\n        x += 1;\n    }\n}\n",
    "ruby": "def f(x)\n  if x > 1\n    return x\n  end\n  0\nend\nputs f(2)\n",
    "php": "<?php\nfunction f($x) {\n  if ($x > 1) { return $x; }\n  return 0;\n}\necho f(2);\n",
    "csharp": "using System;\nclass P {\n  static void Main() {\n    if (DateTime.Now.Year > 2000) { Console.WriteLine(\"hi\"); }\n  }\n}\n",
    "kotlin": "fun main() {\n    val x = 3\n    if (x > 1) {\n        println(x)\n    }\n}\n",
}


# ─── Language detection ──────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", ["python", "javascript", "java", "cpp", "go", "rust", "php", "ruby", "csharp"])
def test_detect_from_content(lang):
    assert languages.detect_from_content(SAMPLES[lang]) == lang


def test_detect_short_python_snippet():
    assert languages.detect_from_content("name = input()\nprint(f'Hello, {name}!')\n") == "python"


@pytest.mark.parametrize("path,lang", [
    ("src/app.py", "python"), ("a/b.tsx", "typescript"), ("Main.java", "java"),
    ("x.cc", "cpp"), ("Dockerfile", "dockerfile"), ("main.go", "go"), ("lib.rs", "rust"),
    ("conf.yml", "yaml"), ("Makefile", "makefile"), ("README.md", "markdown"),
])
def test_detect_from_filename(path, lang):
    assert languages.from_filename(path) == lang


# ─── Errors ──────────────────────────────────────────────────────────────────

def test_python_errors_found():
    errs = check_errors("import os\nprint(undefined_name)\n", "python")
    codes = {e["code"] for e in errs}
    assert "UndefinedName" in codes and "UnusedImport" in codes


def test_python_syntax_error():
    errs = check_errors("def f(:\n  pass\n", "python")
    assert errs and errs[0]["code"] == "E999"


@pytest.mark.parametrize("lang,code,line", [
    ("json", '{"a": 1,\n "b": }\n', 2),
    ("yaml", "a: 1\nb: [1, 2\n", 3),
    ("toml", "a = 1\nb = \n", 2),
])
def test_data_format_errors(lang, code, line):
    errs = check_errors(code, lang)
    assert errs and errs[0]["severity"] == "error"
    assert errs[0]["line"] >= line - 1


def test_valid_json_has_no_errors():
    assert check_errors('{"ok": true}', "json") == []


@needs_ts
@pytest.mark.parametrize("lang", ["javascript", "java", "go", "rust", "c", "cpp", "ruby", "php"])
def test_valid_code_has_no_syntax_errors(lang):
    errs = check_errors(SAMPLES[lang], lang, allow_native=False)
    assert not [e for e in errs if e["severity"] == "error"], errs


@needs_ts
@pytest.mark.parametrize("lang,broken", [
    ("javascript", "function f( {\n  return 1;\n}\n"),
    ("java", "class A { void f() { int x = ; } }\n"),
    ("go", "package main\nfunc main() {\n  x := \n}\n"),
    ("rust", "fn main() { let x = ; }\n"),
    ("c", "int main( { return 0; }\n"),
])
def test_broken_code_has_syntax_errors(lang, broken):
    errs = check_errors(broken, lang, allow_native=False)
    assert any(e["severity"] == "error" for e in errs), errs


def test_repo_files_are_not_checked_with_pyflakes():
    # Regression: repo scan used to run pyflakes on every file regardless of language
    errs = check_errors(SAMPLES["javascript"], "javascript", allow_native=False)
    assert not any(e["code"] == "E999" for e in errs)


def test_apostrophe_in_comment_is_not_a_bracket_error():
    code = "// don't panic (really)\nint x = 1;\n"
    errs = check_errors(code, "zig", allow_native=False)  # zig may lack a grammar → fallback path
    assert not [e for e in errs if e["code"] == "UNBALANCED"]


# ─── Style ───────────────────────────────────────────────────────────────────

def test_style_rules_per_language():
    js = check_style("var x = 1;\nif (x == 1) { console.log(x); }\n", "javascript")["issues"]
    codes = {i["code"] for i in js}
    assert {"NO_VAR", "LOOSE_EQ", "CONSOLE"} <= codes


def test_style_rule_ignores_strings():
    js = check_style('const s = "a == b";\n', "javascript")["issues"]
    assert "LOOSE_EQ" not in {i["code"] for i in js}


def test_style_score_scales_with_length():
    issue = {"severity": "warning"}
    assert style_score([issue] * 5, 500) > style_score([issue] * 5, 20)
    assert style_score([], 10) == 100


# ─── Security ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang,code,rule", [
    ("c", "char b[8];\ngets(b);\n", "C001"),
    ("javascript", "el.innerHTML = userInput;\n", "JS002"),
    ("java", 'stmt.executeQuery("SELECT * FROM t WHERE id=" + id);\n', "JV002"),
    ("php", "echo $_GET['q'];\n", "PHP003"),
    ("go", 'tls.Config{InsecureSkipVerify: true}\n', "SEC007"),
    ("ruby", 'system("ls #{dir}")\n', "RB002"),
    ("typescript", 'const password = "hunter2hunter2";\n', "SEC001"),
])
def test_security_rules(lang, code, rule):
    assert rule in {i["code"] for i in check_security(code, lang)}


def test_security_skips_comments():
    assert not check_security("// gets(buf) is dangerous\nint x;\n", "c")


# ─── Complexity ──────────────────────────────────────────────────────────────

def test_python_complexity_metrics():
    m = function_metrics(SAMPLES["python"], "python")
    assert m and m[0]["name"] == "f" and m[0]["complexity"] >= 2


@needs_lizard
@pytest.mark.parametrize("lang", ["javascript", "java", "c", "cpp", "go", "rust", "ruby", "php", "csharp", "kotlin"])
def test_lizard_metrics(lang):
    assert function_metrics(SAMPLES[lang], lang), lang


# ─── CFG ─────────────────────────────────────────────────────────────────────

def test_python_cfg_all_functions():
    code = "def a(x):\n    if x:\n        return 1\n    return 2\n\ndef b(y):\n    for i in y:\n        if i:\n            break\n    return 0\n"
    res = build_cfg(code, "python")
    assert res["image"].startswith("data:image/png;base64,")
    assert res["functions"] == ["a()", "b()"]
    assert "flowchart TD" in res["mermaid"]


def test_cfg_syntax_error_message():
    assert "syntax" in build_cfg("def f(:\n", "python")["error"].lower()


@needs_ts
@pytest.mark.parametrize("lang", ["javascript", "java", "c", "go", "rust", "php", "ruby", "csharp"])
def test_tree_sitter_cfg(lang):
    res = build_cfg(SAMPLES[lang], lang)
    assert res["image"], res["error"]
    assert res["engine"] == "tree-sitter"


@needs_ts
def test_switch_with_default_has_no_fallthrough_edge():
    code = ("class A { int f(int n) { switch (n) { case 1: return 1; "
            "default: n++; } return n; } }\n")
    assert "no match" not in build_cfg(code, "java")["mermaid"]


def test_cfg_not_for_data():
    assert build_cfg('{"a": 1}', "json")["error"]


# ─── Pipeline ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", list(SAMPLES))
def test_pipeline_every_language(lang):
    rep = analyze_source(SAMPLES[lang], lang, native=False)
    assert rep["language"] == lang
    assert not rep["stage_errors"], rep["stage_errors"]
    assert 0 <= rep["style_score"] <= 100
    assert rep["ast_info"]["line_count"] > 0
    assert rep["tools"]


def test_pipeline_auto_detect():
    rep = analyze_source(SAMPLES["go"], "auto", native=False, include_cfg=False)
    assert rep["language"] == "go"


def test_triage_flags_errors():
    rep = analyze_source("print(undefined)\n", "python", include_cfg=False)
    t = triage(rep)
    assert t["flagged"] and t["error_count"] >= 1 and t["top_issue"]


# ─── GitHub URL parsing ──────────────────────────────────────────────────────

def test_parse_github_urls():
    assert parse_github_url("https://github.com/a/b")["type"] == "repo"
    assert parse_github_url("github.com/a/b.git")["repo"] == "b"
    tree = parse_github_url("https://github.com/a/b/tree/dev/src/lib")
    assert tree["type"] == "repo" and tree["branch"] == "dev" and tree["subdir"] == "src/lib"
    blob = parse_github_url("https://github.com/a/b/blob/main/x/y.go")
    assert blob["type"] == "single_file" and blob["path"] == "x/y.go"


# ─── AI model discovery (offline) ────────────────────────────────────────────

def test_pick_model_skips_non_chat_and_previews():
    from codementor.services.gemini_service import _pick_model, detect_key_provider
    groq = ["whisper-large-v3", "meta-llama/llama-prompt-guard-2-22m", "openai/gpt-oss-20b",
            "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
    assert _pick_model("groq", groq) == "openai/gpt-oss-120b"
    gemini = ["models/gemini-3.5-flash", "models/gemini-3.8-flash-tts", "models/gemini-3-flash-preview",
              "models/gemini-embedding-2", "models/gemini-flash-latest"]
    assert _pick_model("gemini", gemini) == "gemini-flash-latest"
    assert _pick_model("gemini", ["models/gemini-3.5-flash", "models/gemini-3.7-flash"]) == "gemini-3.7-flash"
    assert detect_key_provider("gsk_x") == "groq" and detect_key_provider("AIzaX") == "gemini"


# ─── Runner ──────────────────────────────────────────────────────────────────

@pytest.fixture
def local_runner(monkeypatch):
    """Force the local toolchain path (offline, deterministic)."""
    monkeypatch.setenv("RUN_PREFER_LOCAL", "1")
    monkeypatch.delenv("RUN_REMOTE_ONLY", raising=False)


def test_run_python_with_stdin(local_runner):
    res = run_code("print(input()[::-1])", "python", stdin="abc\n")
    assert res["stdout"].strip() == "cba"


def test_run_python_timeout(local_runner):
    res = run_code("while True: pass", "python")  # hits the 10 s runner timeout
    assert res["timed_out"] or res["returncode"] != 0


def test_run_python_has_no_secrets_in_env(local_runner, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret")
    res = run_code("import os; print(sorted(k for k in os.environ if 'KEY' in k))", "python")
    assert res["stdout"].strip() == "[]"


def test_every_runnable_language_has_a_route():
    from codementor.services.remote_runner import ROUTES, LANG_MAP, _PAIZA_NAMES, _TIO_NAMES
    sys.path.insert(0, os.path.dirname(__file__))
    from run_samples import RUN_SAMPLES
    for lang in RUN_SAMPLES:
        assert lang in ROUTES, lang
        for provider in ROUTES[lang]:
            if provider == "paiza":
                assert lang in _PAIZA_NAMES, (lang, provider)
            elif provider == "tio":
                assert lang in _TIO_NAMES, (lang, provider)
            else:
                idx = 0 if provider == "wandbox" else 1
                assert LANG_MAP[lang][idx], (lang, provider)


def test_java_public_class_is_adapted_for_compiler_explorer():
    from codementor.services.remote_runner import _prepare
    code, _ = _prepare("public class Main { public static void main(String[] a) {} }", "java", "godbolt")
    assert code.startswith("class Main")
    _, extra = _prepare("let x: number = 1;", "typescript", "wandbox")
    assert extra == {"compiler-option-raw": "--noCheck"}


def test_server_keys_rotate_per_model(monkeypatch):
    from codementor.services import gemini_service as ai
    monkeypatch.setenv("DISABLE_OLLAMA", "1")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_aaaaaa1, gsk_bbbbbb2")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    order = [(p.model, p.api_key[-1]) for p in ai.providers()]
    assert order[:2] == [(ai.GROQ_MODELS[0], "1"), (ai.GROQ_MODELS[0], "2")]
    assert ai.detect_key_provider("AQ.fake-key-for-tests") == "gemini"


@pytest.mark.skipif(os.environ.get("NETWORK_TESTS") != "1", reason="set NETWORK_TESTS=1 to hit the sandboxes")
def test_remote_sandboxes_run_every_language(monkeypatch):
    monkeypatch.setenv("RUN_REMOTE_ONLY", "1")
    sys.path.insert(0, os.path.dirname(__file__))
    from run_samples import RUN_SAMPLES, FIXED_OUTPUT
    failures = {}
    for lang, code in RUN_SAMPLES.items():
        res = run_code(code, lang, stdin="Tester\n")
        if FIXED_OUTPUT.get(lang, "Hello, Tester!") not in res["stdout"] + res["stderr"]:
            failures[lang] = (res.get("runner"), res["stderr"][:200])
    assert not failures, failures


def test_run_markdown_is_rejected_politely():
    assert "isn't an executable language" in run_code("# hi", "markdown")["stderr"]
