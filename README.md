# AI Code Reviewer

An intelligent, AI-powered code review platform for students, developers, and educators — built with Python and Reflex.

🌐 **Live Demo:** [https://ai-code-reviewer-red-orca.reflex.run](https://ai-code-reviewer-red-orca.reflex.run)

## Features

| Feature | Description |
|---|---|
| **Bug Detection** | AST + Pyflakes — catches syntax errors, undefined variables, unused imports |
| **PEP 8 Style Analysis** | Pycodestyle — enforces Python style guide, gives a Style Score /100 |
| **Security Scanning** | Bandit — detects OWASP-equivalent vulnerabilities (eval, hardcoded secrets, etc.) |
| **Complexity Analysis** | Radon — cyclomatic complexity (A–F grade) + Maintainability Index |
| **AI Chat Assistant** | Groq LLaMA 3.1 8B (cloud) / Ollama qwen2.5-coder:7b (local) |
| **Control Flow Graph** | NetworkX + Matplotlib — visualizes branches, loops, function calls |
| **GitHub Repo Import** | PyGitHub + ChromaDB RAG — analyze entire repos, chat about your codebase |
| **Live Code Execution** | Sandboxed Python subprocess with terminal output |
| **Analysis History** | Every session saved with timestamp |

## Tech Stack

- **Framework:** Reflex 0.8 (Python full-stack, compiles to React)
- **AI (Cloud):** Groq API — LLaMA 3.1 8B Instant (free tier)
- **AI (Local):** Ollama — qwen2.5-coder:7b (private, offline)
- **Static Analysis:** Pylint, Pyflakes, Pycodestyle, Bandit, Radon
- **RAG:** ChromaDB + BM25 (rank-bm25)
- **Graph:** NetworkX, Matplotlib
- **GitHub Integration:** PyGitHub
- **Database:** SQLite (dev) / PostgreSQL (prod)

## Project Structure

```
ai-code-reviewer/
├── codementor/
│   ├── components/         # UI components (navbar, hero, footer, editor, chat)
│   ├── pages/              # Page definitions (home, analyze, history, about, settings)
│   ├── services/           # Business logic (AI, linting, RAG, GitHub)
│   └── state.py            # Unified Reflex application state
├── assets/
│   └── styles/custom.css   # Global CSS overrides
├── agile_docs/             # Agile documentation (Sprint Backlog, Unit Tests, Defect Tracker)
├── rxconfig.py             # Reflex configuration with backend URL
├── requirements.txt        # All Python dependencies
└── README.md
```

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/saanvi-sahoo/ai-code-reviewer
cd ai-code-reviewer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Add your GROQ_API_KEY from https://console.groq.com (free)

# 4. (Optional) Run Ollama for local AI
ollama serve
ollama pull qwen2.5-coder:7b

# 5. Start the app
reflex run
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Recommended | Free cloud AI — get at [console.groq.com](https://console.groq.com) |
| `OPENAI_API_KEY` | Optional | Paid fallback if Groq unavailable |
| `DATABASE_URL` | Optional | PostgreSQL URL (SQLite used by default) |

## Agile Documents

Located in [`agile_docs/`](agile_docs/):
- `Agile_Template_v0.1.xlsx` — Sprint Backlog (10 User Stories across 7 Sprints)
- `Unit_Test_Plan_v0.1.xlsx` — Unit Test Plan (10 test cases)
- `Defect_Tracker_Template_v0.1.xlsx` — Defect Tracker (7 bugs logged and resolved)

## Deployment

Deployed on **Reflex Cloud** at [https://ai-code-reviewer-red-orca.reflex.run](https://ai-code-reviewer-red-orca.reflex.run)

Backend: `https://be6df7dd-6c4d-4bb1-a59e-85c2dd171c63.fly.dev`

## Author

**Saanvi Sahoo** — [github.com/saanvi-sahoo](https://github.com/saanvi-sahoo)

---

© 2026 AI Code Reviewer — Built with [Reflex](https://reflex.dev) · Powered by [Groq](https://groq.com)
