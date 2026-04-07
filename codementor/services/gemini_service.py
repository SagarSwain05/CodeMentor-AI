"""
AI service — 3-tier priority backend.

Priority (auto-detected, no config needed):
  1. Ollama  (localhost:11434)      — qwen2.5-coder:7b  [local, free, private]
  2. Groq    (api.groq.com)         — llama-3.1-8b-instant [cloud, FREE, fast]
  3. OpenAI  (api.openai.com)       — gpt-4o-mini       [cloud, paid fallback]

Groq is the cloud solution: free tier = 14,400 req/day, LLaMA 3.1 8B model.
"""

import os
import re
import json
import time
import urllib.request
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, AuthenticationError

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

OLLAMA_BASE    = "http://localhost:11434/v1"
OLLAMA_MODEL   = "qwen2.5-coder:7b"

GROQ_BASE      = "https://api.groq.com/openai/v1"
GROQ_MODEL     = "llama-3.1-8b-instant"   # free, 128k context

OPENAI_MODEL   = "gpt-4o-mini"

# Cache Ollama health-check for 30 s
_ollama_ok: bool | None = None
_ollama_checked_at: float = 0.0
_OLLAMA_TTL = 30.0


def _ollama_running() -> bool:
    global _ollama_ok, _ollama_checked_at
    now = time.monotonic()
    if _ollama_ok is not None and (now - _ollama_checked_at) < _OLLAMA_TTL:
        return _ollama_ok
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"Accept": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)
        _ollama_ok = True
    except Exception:
        _ollama_ok = False
    _ollama_checked_at = now
    return _ollama_ok


def _get_client() -> tuple["OpenAI | None", str, str]:
    """Return (client, backend_name, model_id) in priority order."""

    # 1 — Ollama (local)
    if _ollama_running():
        model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)
        return OpenAI(base_url=OLLAMA_BASE, api_key="ollama"), "ollama", model

    # 2 — Groq (cloud, FREE, LLaMA)
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        model = os.environ.get("GROQ_MODEL", GROQ_MODEL)
        return OpenAI(base_url=GROQ_BASE, api_key=groq_key), "groq", model

    # 3 — OpenAI (cloud, paid fallback)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        return OpenAI(api_key=openai_key), "openai", OPENAI_MODEL

    return None, "none", ""


# ─── System prompts ───────────────────────────────────────────────────────────

_ANALYZE_SYSTEM = """You are AI Code Reviewer, an expert code reviewer and educator.
Analyze the provided code and return a JSON object with this EXACT structure:
{
  "summary": "2-3 sentence overall assessment",
  "complexity_analysis": "Big-O analysis or logic complexity explanation",
  "optimizations": [
    {
      "title": "short title",
      "description": "what to change and why",
      "before": "original snippet (max 5 lines)",
      "after": "improved snippet (max 5 lines)",
      "impact": "performance|readability|maintainability"
    }
  ],
  "best_practices": ["actionable tip 1", "tip 2"],
  "positive_aspects": ["what was done well"]
}
Return ONLY valid JSON. No markdown fences, no extra text."""

_CHAT_SYSTEM = """You are AI Code Reviewer, a helpful and friendly code tutor.
You have access to the student's current code and relevant context from their project.
Support ALL programming languages. Be concise, practical, and educational.
Use code examples when helpful. Format code blocks with triple backticks."""

_BEGINNER_CHAT_SYSTEM = """You are AI Code Reviewer, a patient and encouraging coding tutor for beginners.
Explain concepts in simple terms using analogies and real-world examples.
Avoid jargon. Break down complex ideas into small, digestible steps.
Always be positive and supportive. Format code blocks with triple backticks."""


# ─── JSON extraction helper ───────────────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ─── Code Optimization Analysis ───────────────────────────────────────────────

async def get_optimization_suggestions(
    code: str,
    errors: list[dict],
    style_issues: list[dict],
    ast_info: dict,
    language: str = "python",
    security_issues: list[dict] | None = None,
    complexity_report: list[dict] | None = None,
) -> str:
    client, backend, model = _get_client()
    if not client:
        return _no_client_message()

    error_summary  = _format_issues(errors, "Errors/Warnings")
    style_summary  = _format_issues(style_issues, "Style Issues")
    ast_summary    = _format_ast_info(ast_info)
    sec_summary    = _format_security(security_issues or [])
    cplx_summary   = _format_complexity(complexity_report or [])

    user_prompt = f"""Analyze this {language.upper()} code:

```{language}
{code[:6000]}
```

Static Analysis:
{error_summary}
{style_summary}
{sec_summary}
{cplx_summary}

Code Structure:
{ast_summary}

Return ONLY a JSON object matching the required schema."""

    kwargs: dict = dict(
        model=model,
        messages=[
            {"role": "system", "content": _ANALYZE_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=2500,
    )
    if backend in ("openai", "groq"):
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        raw  = resp.choices[0].message.content or ""
        data = _extract_json(raw)
        if data:
            return _format_optimization_response(data, backend, model)
        return raw
    except RateLimitError as e:
        return _handle_rate_limit(e, backend)
    except AuthenticationError:
        return _no_client_message()
    except Exception as e:
        return _handle_error(e, backend)


# ─── Conversational Chat ──────────────────────────────────────────────────────

async def chat_with_ai(
    messages: list[dict],
    user_message: str,
    code: str,
    beginner_mode: bool = False,
    language: str = "python",
    rag_context: str = "",
) -> str:
    client, backend, model = _get_client()
    if not client:
        return _no_client_message()

    system = _BEGINNER_CHAT_SYSTEM if beginner_mode else _CHAT_SYSTEM

    code_context = ""
    if code.strip():
        code_context = f"\n\n[Current {language} code in editor:]\n```{language}\n{code[:3000]}\n```"
    if rag_context:
        code_context += f"\n\n[Relevant code from project:]\n{rag_context}"

    openai_msgs = [{"role": "system", "content": system}]
    for msg in messages[-12:]:
        role = "user" if msg["role"] == "user" else "assistant"
        openai_msgs.append({"role": role, "content": msg["content"]})
    openai_msgs.append({"role": "user", "content": user_message + code_context})

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=openai_msgs,
            temperature=0.7,
            max_tokens=1500,
        )
        return resp.choices[0].message.content or "No response."
    except RateLimitError as e:
        return _handle_rate_limit(e, backend)
    except AuthenticationError:
        return _no_client_message()
    except Exception as e:
        return _handle_error(e, backend)


# ─── Repo batch analysis ──────────────────────────────────────────────────────

async def analyze_repo_files(file_blocks: list[dict]) -> str:
    client, backend, model = _get_client()
    if not client:
        return _no_client_message()

    if not file_blocks:
        return "No flagged files to analyze."

    sections = []
    for fb in file_blocks:
        lang = fb.get("language", "python")
        sections.append(
            f"### `{fb['path']}`\n"
            f"Language: {lang} | Errors: {fb['errors']} | "
            f"Complexity: {fb['complexity']} | Style: {fb['style']}/100"
            + (f" | Security: {fb.get('security', 0)} issues" if fb.get("security") else "")
            + f"\n```{lang}\n{fb['code'][:2000]}\n```"
        )

    prompt = (
        "You are AI Code Reviewer. Below are code files from a GitHub repository "
        "flagged by static analysis. For each file provide:\n"
        "1. One-line verdict (critical / needs work / minor issues)\n"
        "2. Top 2 specific improvements with before/after code\n\n"
        + "\n\n".join(sections)
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=3000,
        )
        return resp.choices[0].message.content or "No response."
    except RateLimitError as e:
        return _handle_rate_limit(e, backend)
    except Exception as e:
        return _handle_error(e, backend)


# ─── Status helper ────────────────────────────────────────────────────────────

def get_ai_status() -> dict:
    if _ollama_running():
        model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)
        return {"backend": "ollama", "model": model, "status": "running"}
    if os.environ.get("GROQ_API_KEY"):
        model = os.environ.get("GROQ_MODEL", GROQ_MODEL)
        return {"backend": "groq", "model": model, "status": "key_set"}
    if os.environ.get("OPENAI_API_KEY"):
        return {"backend": "openai", "model": OPENAI_MODEL, "status": "key_set"}
    return {"backend": "none", "model": "", "status": "no_ai"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _no_client_message() -> str:
    return (
        "## No AI Backend Available\n\n"
        "**Option 1 — Free Local AI:**\n"
        "1. Install [Ollama](https://ollama.com) → run `ollama serve`\n"
        "2. Pull model: `ollama pull qwen2.5-coder:7b`\n"
        "3. Reload — AI works automatically!\n\n"
        "**Option 2 — Free Cloud AI (Groq):**\n"
        "1. Get a free key at [console.groq.com](https://console.groq.com)\n"
        "2. Go to **Settings** and enter your Groq API key.\n\n"
        "**Option 3 — OpenAI:**\n"
        "Go to **Settings** and enter your OpenAI API key.\n\n"
        "> All static analysis (lint, security, complexity, CFG) works without any AI key."
    )


def _handle_rate_limit(e: RateLimitError, backend: str = "") -> str:
    msg = str(e)
    if backend == "groq":
        return (
            "## Groq Rate Limit\n\n"
            "Free tier limit reached (30 req/min or 14,400 req/day).\n"
            "Wait a moment and try again — limits reset quickly.\n\n"
            "> Tip: Use Ollama locally for unlimited free inference."
        )
    if "insufficient_quota" in msg:
        return (
            "## OpenAI Account Has No Credits\n\n"
            "Add credits at [platform.openai.com/settings/billing]"
            "(https://platform.openai.com/settings/billing)\n\n"
            "**Or use free Groq AI:** Get a key at [console.groq.com](https://console.groq.com)"
        )
    return "## Rate Limited\n\nToo many requests. Please wait a moment and try again."


def _handle_error(e: Exception, backend: str = "") -> str:
    msg = str(e)
    if "model" in msg.lower() and "not found" in msg.lower() and backend == "ollama":
        model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)
        return f"## Ollama Model Not Found\n\nRun: `ollama pull {model}`"
    if "quota" in msg.lower():
        return "## Quota Exceeded\n\nAccount out of credits."
    return f"## AI Error\n\n```\n{msg[:400]}\n```"


def _format_issues(issues: list[dict], title: str) -> str:
    if not issues:
        return f"{title}: None"
    lines = [f"{title}:"]
    for issue in issues[:8]:
        lines.append(f"  Line {issue['line']}: [{issue['code']}] {issue['message']}")
    if len(issues) > 8:
        lines.append(f"  ... and {len(issues) - 8} more")
    return "\n".join(lines)


def _format_security(issues: list[dict]) -> str:
    if not issues:
        return ""
    lines = ["Security Issues (Bandit):"]
    for issue in issues[:5]:
        lines.append(
            f"  Line {issue['line']}: [{issue['severity'].upper()}] {issue['message']}"
        )
    return "\n".join(lines)


def _format_complexity(report: list[dict]) -> str:
    if not report:
        return ""
    lines = ["High Complexity Functions (Radon):"]
    for item in report[:5]:
        lines.append(
            f"  {item['name']}() — rank {item['rank']}, complexity {item['complexity']}"
        )
    return "\n".join(lines)


def _format_ast_info(ast_info: dict) -> str:
    if not ast_info:
        return "No static analysis available"
    return (
        f"Lines: {ast_info.get('line_count', 0)}, "
        f"Functions: {len(ast_info.get('functions', []))}, "
        f"Classes: {len(ast_info.get('classes', []))}"
    )


def _format_optimization_response(data: dict, backend: str = "", model: str = "") -> str:
    parts = []

    badge_map = {
        "ollama": f"🖥️ Powered by **Ollama · {model}** (local, free)",
        "groq":   f"⚡ Powered by **Groq · {model}** (cloud, free)",
        "openai": f"☁️ Powered by **OpenAI · {model}**",
    }
    if badge := badge_map.get(backend):
        parts.append(f"\n> {badge}\n")

    if summary := data.get("summary"):
        parts.append(f"## Summary\n{summary}\n")

    if complexity := data.get("complexity_analysis"):
        parts.append(f"## Complexity Analysis\n{complexity}\n")

    if positives := data.get("positive_aspects"):
        parts.append("## What You Did Well")
        for p in positives:
            parts.append(f"- {p}")
        parts.append("")

    if optimizations := data.get("optimizations"):
        parts.append("## Optimization Suggestions")
        for i, opt in enumerate(optimizations, 1):
            impact_emoji = {
                "performance":     "🚀",
                "readability":     "📖",
                "maintainability": "🛠️",
            }.get(opt.get("impact", ""), "💡")
            parts.append(f"\n### {i}. {impact_emoji} {opt.get('title', 'Suggestion')}")
            parts.append(opt.get("description", ""))
            if before := opt.get("before"):
                parts.append(f"\n**Before:**\n```\n{before}\n```")
            if after := opt.get("after"):
                parts.append(f"**After:**\n```\n{after}\n```")

    if best_practices := data.get("best_practices"):
        parts.append("\n## Best Practices")
        for bp in best_practices:
            parts.append(f"- {bp}")

    return "\n".join(parts)
