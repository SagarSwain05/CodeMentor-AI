"""
Security scanning for every language.

  • Python → bandit (AST-based, OWASP / CWE mapped)
  • All languages → a curated regex rule pack (hardcoded secrets, injection
    sinks, unsafe C functions, weak crypto, TLS bypass, XSS sinks …)

The rule pack is intentionally conservative (low false-positive patterns);
the AI review layer adds deeper, context-aware findings on top.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

from codementor.services import languages

try:
    import bandit  # noqa: F401
    HAS_BANDIT = True
except ImportError:  # pragma: no cover
    HAS_BANDIT = False


@dataclass(frozen=True)
class Rule:
    id: str
    langs: frozenset[str]  # empty = all languages
    pattern: re.Pattern
    message: str
    severity: str  # HIGH | MEDIUM | LOW
    cwe: str = ""


def _r(rule_id, langs, pattern, message, severity, cwe="", flags=0) -> Rule:
    return Rule(rule_id, frozenset(langs), re.compile(pattern, flags), message, severity, cwe)


_JS = ("javascript", "typescript", "vue", "svelte", "html")
_C = ("c", "cpp", "objectivec")
_SQL_CONCAT = r"""(?i)["'`]\s*(select|insert|update|delete)\b[^"'`\n]*["'`]\s*(\+|\.\s|%\s)"""

RULES: list[Rule] = [
    # ── Universal ────────────────────────────────────────────────────────────
    # value ≥ 8 chars and not an obvious placeholder (your-key, xxx, changeme, <…>, ${…}, ollama …)
    _r("SEC001", (), r"""(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key|client[_-]?secret)\b["']?\s*[:=]\s*["'](?!(?:your|my|xxx|changeme|example|placeholder|dummy|test|sample|ollama|none|null|<|\$\{|\{\{))[^"'\s]{8,}["']""",
       "Possible hardcoded secret — load it from an environment variable or secret manager", "HIGH", "798"),
    _r("SEC002", (), r"\bAKIA[0-9A-Z]{16}\b", "AWS access key ID committed in source", "HIGH", "798"),
    _r("SEC003", (), r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private key embedded in source", "HIGH", "321"),
    _r("SEC004", (), r"\b(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}\b|\bsk-[A-Za-z0-9]{20,}\b|\bgsk_[A-Za-z0-9]{20,}\b|\bAIza[0-9A-Za-z_-]{35}\b",
       "API token committed in source", "HIGH", "798"),
    _r("SEC005", (), _SQL_CONCAT, "SQL built by string concatenation — use parameterized queries", "HIGH", "89"),
    _r("SEC006", (), r"(?i)\b(md5|sha1)\s*\(|MessageDigest\.getInstance\(\s*\"(MD5|SHA-?1)\"|hashlib\.(md5|sha1)\(|(MD5|SHA1)\.Create\(|crypto\.createHash\(\s*['\"](md5|sha1)['\"]",
       "Weak hash algorithm (MD5/SHA-1) — use SHA-256+ or a password KDF (bcrypt/argon2)", "MEDIUM", "328"),
    _r("SEC007", (), r"(?i)verify\s*=\s*False|InsecureSkipVerify:\s*true|rejectUnauthorized:\s*false|CURLOPT_SSL_VERIFYPEER,\s*(0|false)|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0",
       "TLS certificate verification disabled", "HIGH", "295"),

    # ── JavaScript / TypeScript ──────────────────────────────────────────────
    _r("JS001", _JS, r"\beval\s*\(|\bnew\s+Function\s*\(", "eval()/new Function() executes arbitrary code", "HIGH", "95"),
    _r("JS002", _JS, r"\.innerHTML\s*[+]?=|\.outerHTML\s*=|document\.write(ln)?\s*\(|dangerouslySetInnerHTML",
       "Unsanitized HTML sink — risk of XSS; use textContent or sanitize (DOMPurify)", "MEDIUM", "79"),
    _r("JS003", _JS, r"""child_process['"]?\)?\.(exec|execSync)\s*\(|\bexec(Sync)?\s*\(\s*`[^`]*\$\{""",
       "Shell command execution with dynamic input — use execFile/spawn with an args array", "HIGH", "78"),
    _r("JS004", _JS, r"setTimeout\s*\(\s*['\"`]|setInterval\s*\(\s*['\"`]", "String passed to setTimeout/setInterval is evaluated as code", "MEDIUM", "95"),
    _r("JS005", _JS, r"Math\.random\(\).*(token|secret|password|key|id)", "Math.random() is not cryptographically secure — use crypto.randomUUID/getRandomValues", "LOW", "338", re.I),

    # ── C / C++ ──────────────────────────────────────────────────────────────
    _r("C001", _C, r"\bgets\s*\(", "gets() has no bounds checking (removed in C11) — use fgets()", "HIGH", "242"),
    _r("C002", _C, r"\b(strcpy|strcat|wcscpy|wcscat)\s*\(", "Unbounded string copy — use strncpy/strlcpy or std::string", "MEDIUM", "120"),
    _r("C003", _C, r"\bsprintf\s*\(|\bvsprintf\s*\(", "sprintf() can overflow — use snprintf()", "MEDIUM", "120"),
    _r("C004", _C, r"\bscanf\s*\(\s*\"[^\"]*%s", "scanf(\"%s\") without width can overflow the buffer", "HIGH", "120"),
    _r("C005", _C, r"\bprintf\s*\(\s*[A-Za-z_]\w*\s*\)", "Format string taken from a variable — use printf(\"%s\", var)", "HIGH", "134"),
    _r("C006", _C + ("python", "ruby", "php", "perl"), r"\bsystem\s*\(", "system() runs a shell — command injection risk", "MEDIUM", "78"),

    # ── Java / Kotlin / Scala ────────────────────────────────────────────────
    _r("JV001", ("java", "kotlin", "scala", "groovy"), r"Runtime\.getRuntime\(\)\.exec\s*\(|new\s+ProcessBuilder\s*\(",
       "OS command execution — validate input and avoid shells", "MEDIUM", "78"),
    _r("JV002", ("java", "kotlin", "scala"), r"\.(executeQuery|executeUpdate|execute)\s*\(\s*\"[^\"]*\"\s*\+",
       "JDBC query built by concatenation — use PreparedStatement", "HIGH", "89"),
    _r("JV003", ("java", "kotlin", "scala"), r"new\s+ObjectInputStream\s*\(|\.readObject\s*\(\s*\)",
       "Java deserialization of untrusted data can lead to RCE", "MEDIUM", "502"),
    _r("JV004", ("java", "kotlin"), r"new\s+Random\s*\(\s*\).*(token|password|secret|key)", "java.util.Random is predictable — use SecureRandom", "LOW", "338", re.I),

    # ── C# ───────────────────────────────────────────────────────────────────
    _r("CS001", ("csharp",), r"Process\.Start\s*\(", "Process.Start with external input — command injection risk", "MEDIUM", "78"),
    _r("CS002", ("csharp",), r"new\s+SqlCommand\s*\(\s*\$?\"[^\"]*\"\s*\+|new\s+SqlCommand\s*\(\s*\$\"[^\"]*\{",
       "SqlCommand built from strings — use SqlParameter", "HIGH", "89"),
    _r("CS003", ("csharp",), r"BinaryFormatter", "BinaryFormatter is unsafe for untrusted data", "HIGH", "502"),

    # ── Go ───────────────────────────────────────────────────────────────────
    _r("GO001", ("go",), r"exec\.Command\s*\(\s*\"(sh|bash|cmd)\"", "exec.Command through a shell — command injection risk", "MEDIUM", "78"),
    _r("GO002", ("go",), r"\.(Query|Exec|QueryRow)\s*\(\s*(fmt\.Sprintf|\"[^\"]*\"\s*\+)", "SQL built with Sprintf/concatenation — use placeholders", "HIGH", "89"),

    # ── Rust ─────────────────────────────────────────────────────────────────
    _r("RS001", ("rust",), r"\bunsafe\s*\{", "unsafe block — make sure invariants are documented and upheld", "LOW", "242"),
    _r("RS002", ("rust",), r"\.unwrap\(\)", "unwrap() panics on error — prefer ? or explicit handling in library code", "LOW", "248"),

    # ── PHP ──────────────────────────────────────────────────────────────────
    _r("PHP001", ("php",), r"\b(eval|assert|create_function)\s*\(", "Dynamic code execution", "HIGH", "95"),
    _r("PHP002", ("php",), r"\b(shell_exec|passthru|exec|popen|proc_open)\s*\(|`[^`]*\$", "Shell command execution", "HIGH", "78"),
    _r("PHP003", ("php",), r"\b(echo|print)\b[^;]*\$_(GET|POST|REQUEST|COOKIE)", "User input echoed without escaping — XSS; use htmlspecialchars()", "HIGH", "79"),
    _r("PHP004", ("php",), r"\b(mysql_query|mysqli_query|->query)\s*\([^)]*\$_(GET|POST|REQUEST)", "User input in SQL query — use prepared statements", "HIGH", "89"),
    _r("PHP005", ("php",), r"\b(include|require)(_once)?\s*\(?\s*\$_(GET|POST|REQUEST)", "File inclusion from user input (LFI/RFI)", "HIGH", "98"),
    _r("PHP006", ("php",), r"\bunserialize\s*\(\s*\$_", "unserialize() on user input — object injection", "HIGH", "502"),

    # ── Ruby ─────────────────────────────────────────────────────────────────
    _r("RB001", ("ruby",), r"\beval\s*[\( ]|\binstance_eval\b|\bclass_eval\b", "Dynamic code evaluation", "HIGH", "95"),
    _r("RB002", ("ruby",), r"(system|exec|spawn)\s*\(?\s*\"[^\"]*#\{|`[^`]*#\{", "Shell command with interpolated input", "HIGH", "78"),
    _r("RB003", ("ruby",), r"\.html_safe\b|\braw\s*\(", "Marks content as safe HTML — XSS risk", "MEDIUM", "79"),
    _r("RB004", ("ruby",), r"\.where\s*\(\s*\"[^\"]*#\{", "ActiveRecord where() with interpolation — SQL injection", "HIGH", "89"),

    # ── Shell ────────────────────────────────────────────────────────────────
    _r("SH001", ("bash", "dockerfile"), r"curl[^|\n]*\|\s*(sudo\s+)?(ba|z)?sh\b|wget[^|\n]*\|\s*(sudo\s+)?(ba)?sh\b", "Piping a download straight into a shell", "HIGH", "494"),
    _r("SH002", ("bash", "dockerfile"), r"chmod\s+(-R\s+)?777", "World-writable permissions (chmod 777)", "MEDIUM", "732"),
    _r("SH003", ("bash",), r"\beval\s+[\"']?\$", "eval of variable content", "HIGH", "95"),
    _r("DK001", ("dockerfile",), r"(?i)^\s*USER\s+root\s*$", "Container runs as root", "LOW", "250"),

    # ── Python extras bandit misses in snippets ──────────────────────────────
    _r("PY001", ("python",), r"\bpickle\.loads?\s*\(", "pickle can execute code when loading untrusted data", "MEDIUM", "502"),
    _r("PY002", ("python",), r"yaml\.load\s*\((?![^)]*Loader\s*=\s*yaml\.SafeLoader)", "yaml.load without SafeLoader", "MEDIUM", "502"),
]


def _strip_comment_lines(code: str, lang_id: str) -> list[tuple[int, str]]:
    """Lines that are not pure comments (keeps line numbers)."""
    prefixes = languages.get(lang_id).comment or ()
    out = []
    in_block = False
    for i, line in enumerate(code.splitlines(), 1):
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*") and "*/" not in s:
            in_block = True
            continue
        if s in ("*", "*/") or s.startswith("* ") or (prefixes and s.startswith(prefixes)):
            continue
        out.append((i, line))
    return out


def _sev_to_issue(sev: str) -> str:
    return "error" if sev in ("HIGH", "MEDIUM") else "warning"


def rule_scan(code: str, lang_id: str) -> list[dict]:
    lang_id = languages.normalize(lang_id)
    issues = []
    seen = set()
    for lineno, line in _strip_comment_lines(code, lang_id):
        if len(line) > 2000:
            continue  # minified line — skip
        for rule in RULES:
            if rule.langs and lang_id not in rule.langs:
                continue
            if (lineno, rule.id) in seen:
                continue
            m = rule.pattern.search(line)
            if m:
                seen.add((lineno, rule.id))
                issues.append({
                    "line": lineno, "col": m.start() + 1, "code": rule.id,
                    "message": rule.message,
                    "severity": _sev_to_issue(rule.severity),
                    "category": "security",
                    "bandit_severity": rule.severity,
                    "cwe": rule.cwe,
                })
    return issues


def bandit_scan(code: str) -> list[dict]:
    if not HAS_BANDIT or not code.strip():
        return []
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        result = subprocess.run(["bandit", "-f", "json", "-q", tmp],
                                capture_output=True, text=True, timeout=20)
        raw = result.stdout.strip()
        if not raw:
            return []
        data = json.loads(raw)
        issues = []
        for r in data.get("results", []):
            sev = r.get("issue_severity", "LOW").upper()
            cwe = r.get("issue_cwe", {}) or {}
            issues.append({
                "line": r.get("line_number", 0), "col": 1,
                "code": r.get("test_id", "B000"),
                "message": r.get("issue_text", "Security issue"),
                "severity": _sev_to_issue(sev),
                "category": "security",
                "bandit_severity": sev,
                "bandit_confidence": r.get("issue_confidence", "LOW").upper(),
                "cwe": str(cwe.get("id", "")),
            })
        return issues
    except Exception:
        return []
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def check_security(code: str, lang_id: str = "python") -> list[dict]:
    """Security findings for any language, deduplicated by line."""
    if not code.strip():
        return []
    lang_id = languages.normalize(lang_id)
    issues = bandit_scan(code) if lang_id == "python" else []
    bandit_lines = {i["line"] for i in issues}
    for issue in rule_scan(code, lang_id):
        # bandit already covers secrets/SQL/crypto on Python lines it flagged
        if lang_id == "python" and issue["line"] in bandit_lines:
            continue
        issues.append(issue)
    return sorted(issues, key=lambda x: x["line"])
