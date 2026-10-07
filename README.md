# CodeMentor AI — AI Code Reviewer

An intelligent, AI-powered code review platform for students, developers, and educators — built with Python and Reflex.

> Reviews code in **40+ languages**: Python, JavaScript/TypeScript, Java, C/C++, C#, Go, Rust, Kotlin, Swift, Ruby, PHP, Scala, Dart, Lua, Bash, SQL, HTML/CSS, JSON/YAML/TOML and more.

🌐 **Live Demo:** [https://codementor-ai-lime-ring.reflex.run/](https://codementor-ai-lime-ring.reflex.run/) · 📐 [System design](docs/SYSTEM_DESIGN.md)

---

## Features

| Feature | Description |
|---|---|
| **Error Detection** | pyflakes (Python) · native compilers when installed · tree-sitter syntax analysis for every other language · exact parsers for JSON/YAML/TOML/XML |
| **Style Analysis** | pycodestyle (PEP 8) plus universal and per-language rules; density-based Style Score /100 |
| **Security Scanning** | bandit plus a CWE-tagged rule pack: secrets, SQL/command injection, XSS sinks, unsafe C functions, weak crypto, TLS bypass |
| **Complexity** | radon and lizard: cyclomatic complexity (rank A–F), long functions, parameter counts, Maintainability Index |
| **Control Flow Graph** | Every function, every language (Python AST or tree-sitter, AI fallback); layered layout, PNG plus Mermaid export |
| **AI Review & Optimization** | Line-level findings, Big-O analysis, before/after suggestions, and one-click **Apply optimized code** |
| **GitHub Repo Scan** | Whole repo or `/tree/<branch>/<folder>` in one download; triage, AI repository overview, deep reviews; chat learns the repo (RAG) |
| **AI Chat** | Context-aware tutor (beginner mode) that sees your code, its analysis, and the imported repo |
| **Live Execution** | 40 languages with stdin in isolated sandboxes (Compiler Explorer, Wandbox, Paiza.IO, TIO), no keys needed, with per-language routing and failover |
| **AI Providers** | Your own key, then Ollama, Groq, Gemini, OpenAI, with automatic failover, multi-key rotation and auto-discovery of retired models; users can paste a key inline whenever AI is unavailable |
| **History** | Every analysis saved (SQLite / PostgreSQL) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | [Reflex](https://reflex.dev) 0.8 — Python full-stack, compiles to React |
| **AI** | Groq · Google Gemini · OpenAI · Ollama (OpenAI-compatible async client, automatic failover) |
| **Parsing** | [tree-sitter-language-pack](https://pypi.org/project/tree-sitter-language-pack/) (100+ grammars), Python `ast` |
| **Static Analysis** | pyflakes, pycodestyle, bandit, radon, lizard, multi-language rule packs, native compilers |
| **RAG / Search** | BM25 (built in), ChromaDB optional |
| **Graph Visualization** | Matplotlib (custom layered layout) + Mermaid export |
| **Database** | SQLite (dev) / PostgreSQL (prod via SQLModel + Alembic) |
| **Deployment** | Reflex Cloud (frontend) + Fly.io (backend) |

---

## Project Structure

```
CodeMentor-AI/
├── codementor/
│   ├── components/             # navbar, sidebar, code_editor, ai_chat, bottom_panel, …
│   ├── pages/                  # home, analyze, history, about, settings
│   ├── services/
│   │   ├── languages.py        # Language registry + detection (40+ languages)
│   │   ├── analysis_pipeline.py# ONE pipeline for single files and repo scans
│   │   ├── syntax_service.py   # tree-sitter: syntax errors, structure
│   │   ├── linter_service.py   # errors + style for every language
│   │   ├── complexity_service.py # radon / lizard / maintainability index
│   │   ├── security_service.py # bandit + multi-language security rules
│   │   ├── cfg_service.py      # control flow graphs (ast / tree-sitter / AI)
│   │   ├── gemini_service.py   # AI providers, review, chat, repo overview
│   │   ├── github_service.py   # URL parsing, zipball snapshot, single files
│   │   ├── rag_service.py      # repo chunking + retrieval for chat
│   │   ├── code_runner.py      # local toolchains → Piston → Judge0
│   │   └── db_service.py       # history persistence
│   └── state.py                # Reflex state (background events)
├── tests/test_analysis.py      # pytest suite for the pipeline
├── docs/SYSTEM_DESIGN.md       # architecture & design decisions
├── assets/
│   ├── styles/custom.css       # Global CSS (chat scroll, animations)
│   └── chat_scroll.js          # MutationObserver auto-scroll for chat
├── rxconfig.py                 # Reflex config with backend API URL
├── requirements.txt            # All Python dependencies
├── .env.example                # Environment variable template
└── README.md
```

---

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/SagarSwain05/CodeMentor-AI
cd CodeMentor-AI

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Add any AI key (GROQ_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY)


# 4. (Optional) Run Ollama for fully local AI
ollama serve
ollama pull qwen2.5-coder:7b

# 5. Run the tests, then start the app
python -m pytest -q tests/
reflex run
```

Open [http://localhost:3000](http://localhost:3000)

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Everything is optional; static analysis works with no keys.

| Variable | Description |
|---|---|
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` | AI providers (any one; several give automatic failover; comma-separate multiple keys to rotate them) |
| `GITHUB_TOKEN` | GitHub rate limit 60 → 5,000 req/hr; enables private repos |
| `RUN_REMOTE_ONLY=1` | Never execute user code on the app server (free sandboxes handle all languages) |
| `RUN_PREFER_LOCAL=1` | Development: run with local toolchains first |
| `PISTON_URL` / `JUDGE0_URL` (+`JUDGE0_KEY`) | Optional self-hosted sandboxes, tried after the free ones |
| `DATABASE_URL` | PostgreSQL URL (SQLite by default) |
| `API_URL` | Only to point the frontend at a different backend (Reflex Cloud sets it automatically) |

---

## AI Architecture

Providers are tried in order, and failures fall through automatically:
**your session key → Ollama → Groq → Gemini → OpenAI.** Details are in [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).

---

## Deployment

Deployed on **Reflex Cloud** —  [https://codementor-ai-lime-ring.reflex.run/](https://codementor-ai-lime-ring.reflex.run/)


---

## Authors

**Saanvi Sahoo** — [github.com/saanvi-sahoo](https://github.com/saanvi-sahoo)

**Sagar Swain** — [github.com/SagarSwain05](https://github.com/SagarSwain05)

---

© 2026 CodeMentor AI — Built with [Reflex](https://reflex.dev) · Powered by [Groq](https://groq.com) · [Ollama](https://ollama.ai)
