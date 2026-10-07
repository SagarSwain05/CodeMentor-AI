"""
AI service — multi-provider, async, with automatic failover.

Provider order (first one that works wins; failures fall through):
  0. Keys the user entered in Settings (per browser session — never global)
  1. Ollama   (OLLAMA_BASE_URL, default http://localhost:11434) — local/private
  2. Groq     (GROQ_API_KEY)    — free tier, Llama models
  3. Gemini   (GEMINI_API_KEY)  — via Google's OpenAI-compatible endpoint
  4. OpenAI   (OPENAI_API_KEY)  — paid fallback

All providers speak the OpenAI chat-completions protocol, so one async client
type serves them all. Models are configurable through env vars.

Module name kept as gemini_service for backwards compatibility.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import (
    AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError,
    AuthenticationError, BadRequestError, NotFoundError, PermissionDeniedError,
    RateLimitError,
)

from codementor.services import languages

load_dotenv()

# ─── Provider config ─────────────────────────────────────────────────────────

OLLAMA_MODEL = "qwen2.5-coder:7b"
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-flash-latest"   # Google-maintained alias → current Flash model
OPENAI_MODEL = "gpt-4o-mini"

# Providers retire model ids regularly. When a configured model is gone we list
# the provider's models and pick the best chat model by these preferences.
_MODEL_PREFS = {
    "groq": [r"gpt-oss-120b", r"gpt-oss-20b", r"qwen.*coder", r"qwen", r"llama.*70b",
             r"kimi", r"deepseek", r"llama"],
    "gemini": [r"^gemini-flash-latest$", r"^gemini-\d+(\.\d+)?-flash$", r"^gemini-pro-latest$",
               r"^gemini-\d+(\.\d+)?-pro$"],
    "openai": [r"^gpt-5(\.\d+)?-mini$", r"^gpt-4\.1-mini$", r"^gpt-4o-mini$", r"^gpt-5(\.\d+)?$", r"^gpt-4o$"],
}
_MODEL_EXCLUDE = re.compile(
    r"guard|whisper|orpheus|tts|audio|image|embed|live|transcrib|robotics|aqa|"
    r"veo|lyria|banana|computer-use|search|realtime|moderation|dall|safeguard|allam", re.I)
_discovered: dict[tuple[str, str], str] = {}   # (backend, key suffix) → model id
_REASONING_PREFIXES = ("openai/gpt-oss", "gemini-", "gpt-5", "o3", "o4")

REQUEST_DEADLINE = float(os.environ.get("AI_REQUEST_DEADLINE", "60"))  # seconds per attempt

_ollama_ok: bool | None = None
_ollama_checked_at = 0.0
_OLLAMA_TTL = 30.0


def _ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _ollama_running() -> bool:
    global _ollama_ok, _ollama_checked_at
    if os.environ.get("DISABLE_OLLAMA", "").lower() in ("1", "true", "yes"):
        return False
    now = time.monotonic()
    if _ollama_ok is not None and (now - _ollama_checked_at) < _OLLAMA_TTL:
        return _ollama_ok
    try:
        urllib.request.urlopen(f"{_ollama_base()}/api/tags", timeout=1.5)
        _ollama_ok = True
    except Exception:
        _ollama_ok = False
    _ollama_checked_at = now
    return _ollama_ok


@dataclass
class Provider:
    backend: str   # ollama | groq | gemini | openai
    model: str
    base_url: str | None
    api_key: str
    source: str    # "session" | "server"

    @property
    def label(self) -> str:
        return {"ollama": "Ollama", "groq": "Groq", "gemini": "Google Gemini",
                "openai": "OpenAI"}.get(self.backend, self.backend) + f" · {self.model}"

    def client(self) -> AsyncOpenAI:
        # No SDK retries: on 429 the SDK would sleep for Retry-After (up to a minute on
        # free tiers). _complete() fails over to the next provider instead.
        return AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=45.0, max_retries=0)


def detect_key_provider(key: str) -> str:
    """Guess which provider an API key belongs to from its prefix."""
    key = key.strip()
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-"):
        return "openai"
    return ""


def _providers_for(backend: str, key: str, source: str) -> list[Provider]:
    if backend == "groq":
        custom = os.environ.get("GROQ_MODEL")
        models = (custom,) + tuple(m for m in GROQ_MODELS if m != custom) if custom else GROQ_MODELS
        return [Provider("groq", m, GROQ_BASE, key, source) for m in models]
    if backend == "gemini":
        return [Provider("gemini", os.environ.get("GEMINI_MODEL", GEMINI_MODEL), GEMINI_BASE, key, source)]
    if backend == "openai":
        return [Provider("openai", os.environ.get("OPENAI_MODEL", OPENAI_MODEL), None, key, source)]
    return []


def providers(keys: dict | None = None) -> list[Provider]:
    """Ordered provider candidates for this request."""
    out: list[Provider] = []
    for backend in ("groq", "gemini", "openai"):
        k = (keys or {}).get(backend, "")
        if k:
            out += _providers_for(backend, k, "session")
    if _ollama_running():
        out.append(Provider("ollama", os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL),
                            f"{_ollama_base()}/v1", "ollama", "server"))
    for backend, env in (("groq", "GROQ_API_KEY"), ("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")):
        k = os.environ.get(env, "")
        if k and not (keys or {}).get(backend):
            out += _providers_for(backend, k, "server")
    return out


def get_ai_status(keys: dict | None = None) -> dict:
    cands = providers(keys)
    if not cands:
        return {"backend": "none", "model": "", "status": "no_ai", "label": "No AI configured"}
    p = cands[0]
    return {"backend": p.backend, "model": p.model, "status": "ready", "label": p.label,
            "source": p.source, "fallbacks": [c.label for c in cands[1:4]]}


class AIUnavailable(Exception):
    pass


def _pick_model(backend: str, ids: list[str]) -> str:
    ids = [i.removeprefix("models/") for i in ids if not _MODEL_EXCLUDE.search(i)]
    stable = [i for i in ids if "preview" not in i and "exp" not in i] or ids
    for pref in _MODEL_PREFS.get(backend, []):
        matches = sorted((i for i in stable if re.search(pref, i)), reverse=True)  # newest version first
        if matches:
            return matches[0]
    return ""


async def _discover_model(p: Provider) -> str:
    """List the provider's models and pick a working chat model ('' if none)."""
    cache_key = (p.backend, p.api_key[-6:])
    if cache_key in _discovered:
        return _discovered[cache_key]
    try:
        listing = await p.client().models.list()
        model = _pick_model(p.backend, [m.id for m in listing.data])
    except Exception:
        model = ""
    _discovered[cache_key] = model
    return model


def _effective_model(p: Provider) -> str:
    return _discovered.get((p.backend, p.api_key[-6:])) or p.model


async def _complete(messages: list[dict], keys: dict | None, *, temperature: float = 0.3,
                    max_tokens: int = 2000, json_mode: bool = False) -> tuple[str, Provider]:
    """Run a chat completion with failover across providers (and retired-model recovery)."""
    cands = providers(keys)
    if not cands:
        raise AIUnavailable(_no_client_message())
    errors: list[str] = []
    tried: set[tuple[str, str]] = set()
    for p in cands:
        p.model = _effective_model(p)
        if (p.backend, p.model) in tried:
            continue
        tried.add((p.backend, p.model))
        use_json = json_mode and p.backend in ("groq", "openai", "gemini")
        simple = False          # True → retry without optional params (JSON mode, reasoning effort)
        rediscovered = False
        transient_retried = False
        while True:
            kwargs = dict(model=p.model, messages=messages, temperature=temperature, max_tokens=max_tokens)
            if not simple:
                if use_json:
                    kwargs["response_format"] = {"type": "json_object"}
                if p.model.startswith(_REASONING_PREFIXES):
                    kwargs["reasoning_effort"] = "low"  # faster; leaves tokens for the answer
            try:
                # Hard wall-clock deadline: httpx timeouts are per socket read and
                # can't catch every stall, so one provider can never hang a review.
                resp = await asyncio.wait_for(p.client().chat.completions.create(**kwargs),
                                              timeout=REQUEST_DEADLINE)
                text = resp.choices[0].message.content or ""
                if text.strip():
                    return text, p
                if not simple:
                    simple = True
                    continue
                errors.append(f"{p.label}: empty response")
                break
            except BadRequestError as e:
                if not simple:
                    simple = True
                    continue  # retry once without JSON mode / reasoning params
                errors.append(f"{p.label}: {_short(e)}")
                break
            except RateLimitError as e:
                errors.append(f"{p.label}: rate limited ({_short(e)})")
                break
            except (AuthenticationError, PermissionDeniedError):
                errors.append(f"{p.label}: invalid or unauthorized API key")
                break
            except NotFoundError:
                new_model = "" if rediscovered else await _discover_model(p)
                rediscovered = True
                if new_model and new_model != p.model and (p.backend, new_model) not in tried:
                    p.model = new_model
                    tried.add((p.backend, new_model))
                    continue  # retry with a model the provider actually serves
                errors.append(f"{p.label}: model not available")
                break
            except asyncio.TimeoutError:
                errors.append(f"{p.label}: no response within {REQUEST_DEADLINE:.0f}s")
                break
            except (APIConnectionError, APITimeoutError) as e:
                if not transient_retried:
                    transient_retried = True
                    await asyncio.sleep(1.5)
                    continue
                errors.append(f"{p.label}: connection failed ({_short(e)})")
                break
            except APIStatusError as e:
                if e.status_code >= 500 and not transient_retried:  # overloaded → brief backoff
                    transient_retried = True
                    await asyncio.sleep(2.0)
                    continue
                errors.append(f"{p.label}: HTTP {e.status_code}")
                break
            except Exception as e:  # pragma: no cover — defensive
                errors.append(f"{p.label}: {_short(e)}")
                break
    raise AIUnavailable(
        "## AI providers unavailable\n\nEvery configured provider failed:\n\n"
        + "\n".join(f"- {e}" for e in errors)
        + "\n\n> Static analysis results above are still complete. Add another key in **Settings** for failover."
    )


def _short(e: Exception) -> str:
    return str(e).replace("\n", " ")[:160]


# ─── Prompts ─────────────────────────────────────────────────────────────────

_REVIEW_SYSTEM = """You are CodeMentor AI, a senior software engineer doing a rigorous code review.
You review code in ANY programming language, markup or config format, applying that language's idioms,
standard library, performance characteristics and security pitfalls.

Return ONE JSON object with exactly these keys:
{
  "summary": "2-3 sentence overall assessment",
  "verdict": "excellent | good | needs_work | critical",
  "score": 0-100 integer overall quality,
  "time_complexity": "Big-O of the dominant path, e.g. O(n log n), or 'n/a'",
  "space_complexity": "Big-O memory, or 'n/a'",
  "complexity_analysis": "short explanation of the algorithmic complexity and hot spots",
  "issues": [
    {"line": <1-based line number or 0>, "severity": "error|warning|info",
     "category": "bug|security|performance|style|maintainability",
     "message": "what is wrong", "fix": "how to fix it"}
  ],
  "optimizations": [
    {"title": "short title", "description": "what to change and why",
     "before": "original snippet (<= 6 lines)", "after": "improved snippet (<= 6 lines)",
     "impact": "performance|readability|maintainability|security"}
  ],
  "best_practices": ["actionable tip"],
  "positive_aspects": ["what was done well"],
  "optimized_code": "the COMPLETE improved file, or empty string if not requested"
}
Rules: only report real problems (no invented line numbers); prefer 3-8 high-value issues;
static-analysis findings are already shown to the user — confirm, explain or add to them, don't just repeat them.
Return ONLY the JSON object."""

_CHAT_SYSTEM = """You are CodeMentor AI, an expert, friendly programming tutor and code reviewer.
You know every programming language, framework, build tool and config format.
Be concise, accurate and practical. Reference line numbers when discussing the user's code.
Use fenced code blocks with the correct language tag."""

_BEGINNER_CHAT_SYSTEM = """You are CodeMentor AI, a patient and encouraging coding tutor for beginners.
Explain concepts in simple terms with analogies and small steps. Avoid jargon (or define it).
Always be positive. Use fenced code blocks with the correct language tag."""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _format_issues(issues: list[dict], title: str, limit: int = 8) -> str:
    if not issues:
        return f"{title}: none"
    lines = [f"{title}:"]
    for issue in issues[:limit]:
        lines.append(f"  L{issue.get('line', 0)} [{issue.get('code', '')}] {issue.get('message', '')}")
    if len(issues) > limit:
        lines.append(f"  … and {len(issues) - limit} more")
    return "\n".join(lines)


def _format_ast_info(ast_info: dict) -> str:
    if not ast_info:
        return "Structure: unknown"
    fns = [f.get("name", "") for f in ast_info.get("functions", [])][:15]
    return (f"Lines: {ast_info.get('line_count', 0)} · Functions ({len(ast_info.get('functions', []))}): "
            f"{', '.join(fns) or '-'} · Classes: {len(ast_info.get('classes', []))} · "
            f"Max function complexity: {ast_info.get('max_complexity', ast_info.get('complexity', 0))}")


def _numbered(code: str, limit_chars: int) -> tuple[str, bool]:
    truncated = len(code) > limit_chars
    body = code[:limit_chars]
    numbered = "\n".join(f"{i:>4} | {line}" for i, line in enumerate(body.splitlines(), 1))
    return numbered, truncated


_SEV = {"error", "warning", "info"}


def _normalize_ai_issues(raw: list, line_count: int) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict) or not item.get("message"):
            continue
        try:
            line = int(item.get("line") or 0)
        except (TypeError, ValueError):
            line = 0
        if line < 0 or line > line_count:
            line = 0
        sev = str(item.get("severity", "warning")).lower()
        cat = str(item.get("category", "bug")).lower()
        msg = str(item["message"]).strip()
        if item.get("fix"):
            msg += f" → {str(item['fix']).strip()}"
        out.append({
            "line": line, "col": 1, "code": f"AI-{cat[:4].upper()}",
            "message": msg[:400], "severity": sev if sev in _SEV else "warning",
            "category": "ai", "ai_category": cat,
        })
    return out[:20]


def _strip_fences(code: str) -> str:
    m = re.match(r"^\s*```[\w+-]*\n([\s\S]*?)\n```\s*$", code)
    return m.group(1) if m else code


# ─── Code review ─────────────────────────────────────────────────────────────

async def ai_review(
    code: str,
    language: str = "python",
    *,
    errors: list[dict] | None = None,
    style_issues: list[dict] | None = None,
    security_issues: list[dict] | None = None,
    complexity_report: list[dict] | None = None,
    ast_info: dict | None = None,
    filename: str = "",
    keys: dict | None = None,
    want_optimized_code: bool = True,
) -> dict:
    """
    Structured AI review. Returns
      {"ok", "markdown", "issues", "optimized_code", "provider", "score", "verdict"}
    """
    lang_label = languages.label(language)
    numbered, truncated = _numbered(code, 10_000)
    line_count = len(code.splitlines())
    # Full rewrites double the output size — keep them for files that fit free-tier token limits
    ask_full = want_optimized_code and line_count <= 150 and not truncated

    user_prompt = f"""Review this {lang_label} file{f' `{filename}`' if filename else ''}.
Line numbers are prefixed as `NNNN | ` (they are not part of the code).
{'NOTE: the file was truncated for length; review what is shown.' if truncated else ''}

{numbered}

Static analysis already found:
{_format_issues(errors or [], "Errors/warnings")}
{_format_issues(security_issues or [], "Security", 6)}
{_format_issues(complexity_report or [], "Complexity", 5)}
{_format_issues(style_issues or [], "Style", 5)}
{_format_ast_info(ast_info or {})}

{"Include the complete improved file in optimized_code (same language, runnable, no line-number prefixes)." if ask_full else 'Set optimized_code to "".'}"""

    try:
        raw, provider = await _complete(
            [{"role": "system", "content": _REVIEW_SYSTEM}, {"role": "user", "content": user_prompt}],
            keys, temperature=0.2, max_tokens=4000 if ask_full else 2200, json_mode=True,
        )
    except AIUnavailable as e:
        return {"ok": False, "markdown": str(e), "issues": [], "optimized_code": "",
                "provider": "", "score": None, "verdict": ""}

    data = _extract_json(raw)
    if not data:
        return {"ok": True, "markdown": f"> {provider.label}\n\n{raw}", "issues": [],
                "optimized_code": "", "provider": provider.label, "score": None, "verdict": ""}

    optimized = _strip_fences(str(data.get("optimized_code") or "")).strip("\n")
    if optimized.strip() == code.strip():
        optimized = ""
    return {
        "ok": True,
        "markdown": _format_review(data, provider, language),
        "issues": _normalize_ai_issues(data.get("issues"), line_count),
        "optimized_code": optimized if ask_full else "",
        "provider": provider.label,
        "score": data.get("score"),
        "verdict": str(data.get("verdict", "")),
    }


_VERDICT = {"excellent": "🟢 Excellent", "good": "🟢 Good", "needs_work": "🟡 Needs work",
            "critical": "🔴 Critical issues"}
_IMPACT = {"performance": "🚀", "readability": "📖", "maintainability": "🛠️", "security": "🔒"}


def _format_review(data: dict, provider: Provider, language: str) -> str:
    fence = language if language not in ("text",) else ""
    parts = [f"> 🤖 Reviewed by **{provider.label}**" + (" (your key)" if provider.source == "session" else "")]

    head = []
    if verdict := _VERDICT.get(str(data.get("verdict", "")).lower()):
        head.append(f"**Verdict:** {verdict}")
    if isinstance(data.get("score"), (int, float)):
        head.append(f"**AI score:** {int(data['score'])}/100")
    if data.get("time_complexity"):
        head.append(f"**Time:** `{data['time_complexity']}`")
    if data.get("space_complexity"):
        head.append(f"**Space:** `{data['space_complexity']}`")
    if head:
        parts.append(" · ".join(head))

    if summary := data.get("summary"):
        parts.append(f"## Summary\n{summary}")
    if cx := data.get("complexity_analysis"):
        parts.append(f"## Complexity Analysis\n{cx}")

    issues = [i for i in data.get("issues") or [] if isinstance(i, dict)]
    if issues:
        rows = ["## Findings"]
        icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}
        for i in issues:
            line = f"L{i.get('line')}" if i.get("line") else "general"
            rows.append(f"- {icon.get(str(i.get('severity')).lower(), '🟡')} **{line}** "
                        f"_{i.get('category', '')}_ — {i.get('message', '')}"
                        + (f"  \n  ↳ {i['fix']}" if i.get("fix") else ""))
        parts.append("\n".join(rows))

    if positives := data.get("positive_aspects"):
        parts.append("## What You Did Well\n" + "\n".join(f"- {p}" for p in positives))

    if opts := data.get("optimizations"):
        rows = ["## Optimization Suggestions"]
        for n, opt in enumerate([o for o in opts if isinstance(o, dict)], 1):
            rows.append(f"\n### {n}. {_IMPACT.get(opt.get('impact', ''), '💡')} {opt.get('title', 'Suggestion')}")
            rows.append(str(opt.get("description", "")))
            if opt.get("before"):
                rows.append(f"\n**Before:**\n```{fence}\n{opt['before']}\n```")
            if opt.get("after"):
                rows.append(f"**After:**\n```{fence}\n{opt['after']}\n```")
        parts.append("\n".join(rows))

    if bp := data.get("best_practices"):
        parts.append("## Best Practices\n" + "\n".join(f"- {b}" for b in bp))
    if data.get("optimized_code"):
        parts.append("> ✨ A complete optimized version is available — click **Apply optimized code** above.")
    return "\n\n".join(parts)


async def get_optimization_suggestions(
    code: str,
    errors: list[dict],
    style_issues: list[dict],
    ast_info: dict,
    language: str = "python",
    security_issues: list[dict] | None = None,
    complexity_report: list[dict] | None = None,
    keys: dict | None = None,
    filename: str = "",
) -> str:
    """Backwards-compatible wrapper returning only the markdown report."""
    result = await ai_review(
        code, language, errors=errors, style_issues=style_issues,
        security_issues=security_issues, complexity_report=complexity_report,
        ast_info=ast_info, filename=filename, keys=keys, want_optimized_code=False,
    )
    return result["markdown"]


# ─── Chat ────────────────────────────────────────────────────────────────────

async def chat_with_ai(
    messages: list[dict],
    user_message: str,
    code: str,
    beginner_mode: bool = False,
    language: str = "python",
    rag_context: str = "",
    analysis_context: str = "",
    keys: dict | None = None,
) -> str:
    system = _BEGINNER_CHAT_SYSTEM if beginner_mode else _CHAT_SYSTEM
    context = ""
    if code.strip():
        numbered, truncated = _numbered(code, 8000)
        context += (f"\n\n[Current {languages.label(language)} code in the editor"
                    f"{' (truncated)' if truncated else ''}, with line numbers:]\n{numbered}")
    if analysis_context:
        context += f"\n\n[Latest static analysis:]\n{analysis_context}"
    if rag_context:
        context += f"\n\n[Relevant code retrieved from the imported repository:]\n{rag_context}"

    msgs = [{"role": "system", "content": system + context}]
    for msg in messages[-12:]:
        msgs.append({"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]})
    msgs.append({"role": "user", "content": user_message})
    try:
        text, _ = await _complete(msgs, keys, temperature=0.5, max_tokens=2000)
        return text
    except AIUnavailable as e:
        return str(e)


# ─── Repository-level review ─────────────────────────────────────────────────

async def analyze_repo_overview(repo_name: str, stats: dict, file_rows: list[dict],
                                keys: dict | None = None) -> str:
    """One AI call summarizing a whole repository scan."""
    table = "\n".join(
        f"- {r['path']} [{r['language']}] errors={r['error_count']} security={r['security_count']} "
        f"maxCC={r['complexity']} style={r['style_score']} :: {r.get('top_issue', '')}"
        for r in file_rows[:60]
    )
    prompt = f"""Repository: {repo_name}
Languages: {stats.get('languages')}
Files analyzed: {stats.get('files')} · flagged: {stats.get('flagged')} · total errors: {stats.get('errors')} · security findings: {stats.get('security')}

Per-file static analysis (most problematic first):
{table}

Write a concise markdown repository review with these sections:
## Overview (what the project appears to be, architecture in 2-4 bullets)
## Health Score (0-100 with one-line justification)
## Top Risks (max 5 bullets, cite file paths)
## Prioritized Action Plan (numbered, max 6, concrete)
## Strengths (max 3 bullets)"""
    try:
        text, provider = await _complete(
            [{"role": "system", "content": _CHAT_SYSTEM}, {"role": "user", "content": prompt}],
            keys, temperature=0.3, max_tokens=1800,
        )
        return f"> 🤖 Repository review by **{provider.label}**\n\n{text}"
    except AIUnavailable as e:
        return str(e)


async def analyze_repo_files(file_blocks: list[dict], keys: dict | None = None) -> str:
    """Kept for compatibility: brief verdicts for several flagged files in one call."""
    if not file_blocks:
        return "No flagged files to analyze."
    sections = []
    for fb in file_blocks:
        lang = fb.get("language", "text")
        sections.append(f"### `{fb['path']}` ({languages.label(lang)})\n```{lang}\n{fb['code'][:2000]}\n```")
    prompt = ("For each file give a one-line verdict (critical / needs work / minor) and the top 2 "
              "improvements with before/after code.\n\n" + "\n\n".join(sections))
    try:
        text, _ = await _complete([{"role": "user", "content": prompt}], keys, max_tokens=3000)
        return text
    except AIUnavailable as e:
        return str(e)


# ─── AI control-flow graph (for languages without a parser) ─────────────────

async def ai_cfg_spec(code: str, language: str, keys: dict | None = None) -> dict | None:
    prompt = f"""Build control flow graphs for the main functions (max 4) of this {languages.label(language)} code.
Return JSON: {{"graphs": [{{"title": "name()", "nodes": [{{"id": "n1", "label": "short text <= 35 chars",
"kind": "func|stmt|branch|loop|case|exception|return|end"}}], "edges": [{{"from": "n1", "to": "n2",
"label": "True|False|loop|done|''"}}]}}]}}
Each graph starts with one "func" node and ends with one "end" node. Merge straight-line statements.

```{language}
{code[:6000]}
```"""
    try:
        raw, _ = await _complete([{"role": "user", "content": prompt}], keys,
                                 temperature=0.1, max_tokens=2500, json_mode=True)
    except AIUnavailable:
        return None
    return _extract_json(raw)


# ─── Messages ────────────────────────────────────────────────────────────────

def _no_client_message() -> str:
    return (
        "## No AI provider configured\n\n"
        "Static analysis (errors, style, security, complexity, CFG) works without AI.\n"
        "To enable AI reviews, chat and optimized code, add **any one** key in **Settings**:\n\n"
        "- **Groq** (free) — [console.groq.com](https://console.groq.com) → key starts with `gsk_`\n"
        "- **Google Gemini** (free tier) — [aistudio.google.com](https://aistudio.google.com/app/apikey) → `AIza…`\n"
        "- **OpenAI** — [platform.openai.com](https://platform.openai.com/api-keys) → `sk-…`\n"
        "- Or run **Ollama** locally: `ollama serve` + `ollama pull qwen2.5-coder:7b`"
    )
