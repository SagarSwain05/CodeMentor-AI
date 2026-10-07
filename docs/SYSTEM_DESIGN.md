# CodeMentor AI — System Design

## 1. Goals

| Goal | How it's met |
|---|---|
| Review code in **any** language | Language registry + tree-sitter (100+ grammars) + lizard + rule packs + AI layer |
| Same quality for single files and whole repos | One pipeline (`analysis_pipeline.analyze_source`) used by both paths |
| Never block the UI | Long work runs as Reflex background events; CPU work runs in worker threads |
| Degrade gracefully | Every stage is optional and isolated; missing tools fall back, never crash |
| Safe multi-user deployment | Per-session API keys, scrubbed execution env, optional remote sandbox |

## 2. Architecture

```
Browser (Reflex/React)
   │  websocket events
   ▼
State (codementor/state.py) ── background events ──┐
   │                                               │
   ├─ analyze_code ──► analysis_pipeline ──► worker thread
   │                     ├─ languages        (detect / registry)
   │                     ├─ syntax_service   (tree-sitter: syntax errors, structure)
   │                     ├─ linter_service   (pyflakes · pycodestyle · native compilers ·
   │                     │                    JSON/YAML/TOML/XML parsers · style rules)
   │                     ├─ complexity_service (radon · lizard · MI)
   │                     ├─ security_service (bandit · multi-language rule pack)
   │                     └─ cfg_service      (python-ast / tree-sitter → layered PNG + Mermaid)
   │                 └─► gemini_service.ai_review  (async, provider failover)
   │                 └─► gemini_service.ai_cfg_spec (only when no parser exists)
   │
   ├─ start_repo_scan ─► github_service.fetch_repo_snapshot (1 zipball request)
   │                    ─► analysis_pipeline (per file, 4 threads) ─► triage
   │                    ─► rag_service.index_repo (BM25; Chroma optional)
   │                    ─► AI repo overview + top-3 deep reviews
   │
   ├─ send_chat_message ─► rag_service.retrieve_context ─► chat_with_ai
   ├─ run_code ─► code_runner (local toolchain → Piston → Judge0)
   └─ history ─► db_service (SQLModel: SQLite / PostgreSQL)
```

## 3. Analysis pipeline

`analyze_source(code, language, filename, native=True, include_cfg=True)` runs these stages, each wrapped so one failure never hides the others:

1. **Resolve language.** Explicit choice, else filename, else content heuristics (`languages.detect`).
2. **Structure.** Python uses `ast`. Other languages use tree-sitter node types (functions, classes, imports), with lizard providing per-function metrics.
3. **Errors** (priority order):
   - Python → pyflakes.
   - JSON/YAML/TOML/XML → real parsers.
   - Native toolchain if installed (gcc/clang, g++, javac, node, tsc, gofmt, rustc, php, ruby, bash). Single-file Analyze only, because repo files lack their dependencies.
   - tree-sitter `ERROR`/`MISSING` nodes.
   - Comment- and string-aware bracket check as a last resort.
4. **Style.** pycodestyle for Python. For other languages: universal rules (line length, trailing whitespace, mixed indentation, TODO markers) plus per-language rules. Scoring is density-based: `100·e^(−weighted issues per 100 lines / 40)`.
5. **Complexity.** radon for Python and lizard for about 20 languages. Flags functions with cyclomatic complexity above 5, more than 80 lines, or more than 6 parameters.
6. **Security.** bandit for Python plus about 50 conservative regex rules across languages, CWE-tagged. Pure comment lines are skipped.
7. **Maintainability index.** radon for Python; elsewhere the classic MI formula with a token-based Halstead volume.
8. **CFG.** One graph per function (up to 6), with basic-block merging, back-edge detection and layered layout. Output is a PNG plus Mermaid source.

The AI layer then gets the code, with line numbers, plus all static findings. It returns strict JSON: summary, verdict, score, Big-O, line-level `issues`, optimizations, and the full `optimized_code` for files of 150 lines or fewer. AI issues appear in the Errors tab as **AI Review Findings**, and **Apply optimized code** swaps them into the editor.

## 4. Repository scan

1. `GET /repos/{o}/{r}` resolves the real default branch (no more main/master guessing).
2. `GET /repos/{o}/{r}/zipball/{branch}` is a single request instead of one per file. That avoids the 60 requests/hour anonymous limit and covers every language.
3. Filters drop vendored and build directories, lock files, minified files, binaries, and files over 200 KB. The cap is 300 files, ranked code > markup > config > docs. `/tree/<branch>/<dir>` URLs scan only that folder.
4. The pipeline runs per file in batches of 8 threads, without native compilers or CFG.
5. `triage()` flags a file on any error, a high-severity security finding, max complexity above 10, or a style score below 60. Files are ranked by a weighted priority.
6. Results stream into the UI as they arrive. File contents stay server-side (`_file_store`, 4 MB budget per session); files outside the budget are re-fetched when opened.
7. Files are indexed for RAG, so the chat can answer questions about the repo.
8. AI writes one repository overview (health score, risks, action plan) and deep-reviews the top 3 flagged code files.

## 5. AI providers

Candidates are tried in order, and any rate-limit, auth, model-not-found, connection or 5xx error falls through to the next:

1. Keys the user pasted in Settings. These are per session and never written to `os.environ`.
2. Ollama (`OLLAMA_BASE_URL`).
3. Groq: `GROQ_MODEL`, then `llama-3.3-70b-versatile`, then `llama-3.1-8b-instant`.
4. Gemini, via its OpenAI-compatible endpoint (`GEMINI_MODEL`, default `gemini-2.5-flash`).
5. OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`).

JSON mode is requested where supported and retried without it if a provider rejects the request.

## 6. Code execution

The runner tries options in this order:

1. **Local toolchain** if present: Python, Node/Bun/Deno (JS, and TS via tsx or Node 22+), Java single-file launch, gcc/g++, Go, Rust, Ruby, PHP, Bash, Perl, Lua, R, Julia, Dart, Elixir, Haskell, Kotlin script, Swift, Scala.
2. **Piston** (`PISTON_URL`) for about 30 languages.
3. **Judge0** (`JUDGE0_URL` + `JUDGE0_KEY`).

Local runs use a fresh temp directory and an environment with no secrets, plus CPU, file-size and core rlimits and a 10 s wall clock (40 s for compiles). **Subprocess limits are not isolation.** For a public deployment, set `RUN_REMOTE_ONLY=1` and use a Piston or Judge0 sandbox.

## 7. State & concurrency

- `analyze_code`, `start_repo_scan`, `send_chat_message` and `run_code` are `@rx.event(background=True)`. They copy inputs under `async with self`, work without holding the lock, and write results back in short locked sections.
- tree-sitter parsers are cached per thread, because they aren't thread-safe.
- The editor is an uncontrolled `<textarea>` keyed by `editor_key = path::version`. Every programmatic change (upload, history load, apply fix, clear) bumps the version so the editor remounts with the new content.

## 8. Configuration

All settings are in `.env.example`. The app runs with **zero** keys (full static analysis, CFG, and Python execution). Each key you add unlocks more: AI, private repos and higher GitHub limits, remote execution.

## 9. Known limits / next steps

- Native compilers depend on the host image. Reflex Cloud only guarantees Python, so other languages use tree-sitter for errors and Piston/Judge0 for execution.
- The RAG index is in-process memory. With multiple backend workers, use Chroma or an external vector DB.
- A Monaco editor (syntax highlighting, inline issue markers) would be the next UX upgrade.
