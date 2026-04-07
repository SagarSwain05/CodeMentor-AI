# CodeMentor AI — AI Code Reviewer

An intelligent, AI-powered code review platform for students, developers, and educators — built with Python and Reflex.

> **Phase 1:** Currently supports **Python** and several popular languages. Support for additional languages is actively in development and coming soon!

🌐 **Live Demo:** [https://codementor-silver-apple.reflex.run/](https://codementor-silver-apple.reflex.run/)

---

## Features

| Feature | Description |
|---|---|
| **Bug Detection** | AST + Pyflakes — catches syntax errors, undefined variables, unused imports |
| **PEP 8 / Style Analysis** | Pycodestyle — enforces Python style guide, gives a Style Score /100 |
| **Security Scanning** | Bandit — detects OWASP-equivalent vulnerabilities (eval, hardcoded secrets, SQL injection, etc.) |
| **Complexity Analysis** | Radon — cyclomatic complexity grade (A–F) + Maintainability Index |
| **AI Chat Assistant** | Context-aware AI chat powered by Groq LLaMA 3.1 8B (cloud) or Ollama (local) |
| **Control Flow Graph** | NetworkX + Matplotlib — visual graph of branches, loops, and function calls |
| **GitHub Repo Import** | PyGitHub + ChromaDB RAG — import and analyze entire GitHub repositories |
| **Live Code Execution** | Sandboxed Python subprocess with real terminal output |
| **Analysis History** | Every review session saved with full results and timestamps |
| **Responsive UI** | Dark-themed, mobile-friendly interface built with Reflex + Radix |

---

## Language Support

| Language | Status |
|---|---|
| Python | ✅ Full support (Phase 1) |
| JavaScript / TypeScript | 🚧 Coming soon |
| Java | 🚧 Coming soon |
| C / C++ | 🚧 Coming soon |
| Go, Rust, and more | 🚧 Planned |

> Phase 1 focuses on Python with deep static analysis. Multi-language support will be rolled out in upcoming phases.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | [Reflex](https://reflex.dev) 0.8 — Python full-stack, compiles to React |
| **AI (Cloud)** | [Groq API](https://console.groq.com) — LLaMA 3.1 8B Instant (free tier) |
| **AI (Local)** | [Ollama](https://ollama.ai) — qwen2.5-coder:7b (private, offline) |
| **Static Analysis** | Pyflakes, Pycodestyle, Bandit, Radon |
| **RAG / Search** | ChromaDB + BM25 (rank-bm25) |
| **Graph Visualization** | NetworkX, Matplotlib |
| **GitHub Integration** | PyGitHub |
| **Database** | SQLite (dev) / PostgreSQL (prod via SQLModel + Alembic) |
| **Deployment** | Reflex Cloud (frontend) + Fly.io (backend) |

---

## Project Structure

```
CodeMentor-AI/
├── codementor/
│   ├── components/
│   │   ├── navbar.py           # Top navigation bar with links & GitHub icons
│   │   ├── hero.py             # Landing page hero section
│   │   ├── footer.py           # Footer with nav columns & social links
│   │   ├── code_editor.py      # Monaco-style code input panel
│   │   ├── ai_chat.py          # AI chat sidebar with scroll fix
│   │   ├── results_panel.py    # Analysis results display
│   │   └── theme.py            # Color palette & shared styles
│   ├── pages/
│   │   ├── index.py            # Home page
│   │   ├── analyze.py          # Main code review page
│   │   ├── history.py          # Review history page
│   │   ├── about.py            # About page
│   │   └── settings.py         # Settings page (AI model, theme)
│   ├── services/
│   │   ├── gemini_service.py   # 3-tier AI: Ollama → Groq → OpenAI
│   │   ├── linting_service.py  # Pyflakes + Pycodestyle analysis
│   │   ├── security_service.py # Bandit security scanning
│   │   ├── complexity_service.py # Radon complexity metrics
│   │   ├── cfg_service.py      # Control flow graph generation
│   │   ├── rag_service.py      # ChromaDB + BM25 RAG pipeline
│   │   └── github_service.py   # GitHub repo import & indexing
│   └── state.py                # Unified Reflex application state
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
# Add your GROQ_API_KEY from https://console.groq.com (free)

# 4. (Optional) Run Ollama for fully local AI
ollama serve
ollama pull qwen2.5-coder:7b

# 5. Start the app
reflex run
```

Open [http://localhost:3000](http://localhost:3000)

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Recommended | Free cloud AI — get at [console.groq.com](https://console.groq.com) |
| `OPENAI_API_KEY` | Optional | Paid fallback if Groq unavailable |
| `DATABASE_URL` | Optional | PostgreSQL URL (SQLite used by default) |

---

## AI Architecture

The platform uses a **3-tier AI priority system**:

1. **Ollama (local)** — Fastest, fully private. Requires `ollama serve` running locally.
2. **Groq API (cloud)** — Free tier (14,400 req/day), LLaMA 3.1 8B Instant. Requires `GROQ_API_KEY`.
3. **OpenAI (cloud)** — Paid fallback. Requires `OPENAI_API_KEY`.

---

## Deployment

Deployed on **Reflex Cloud** — [https://ai-code-reviewer-red-orca.reflex.run](https://ai-code-reviewer-red-orca.reflex.run)

Backend: `https://be6df7dd-6c4d-4bb1-a59e-85c2dd171c63.fly.dev`

---

## Authors

**Saanvi Sahoo** — [github.com/saanvi-sahoo](https://github.com/saanvi-sahoo)

**Sagar Swain** — [github.com/SagarSwain05](https://github.com/SagarSwain05)

---

© 2026 CodeMentor AI — Built with [Reflex](https://reflex.dev) · Powered by [Groq](https://groq.com) · [Ollama](https://ollama.ai)
