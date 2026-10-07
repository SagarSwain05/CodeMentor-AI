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

- **Multiple keys.** Each env var may hold several comma-separated keys. They are interleaved per model, so a rate-limited key fails over to the next key before moving to a weaker model.
- **Retired models.** On "model not found", the service lists the provider's models, picks the best current chat model by preference rules, caches it and retries.
- **Bounded latency.** SDK retries are disabled, because they sleep for `Retry-After`. Each attempt has a hard `asyncio.wait_for` deadline (`AI_REQUEST_DEADLINE`, default 60 s), and 5xx responses get one 2-second backoff.
- **User keys.** When no provider can answer, the AI tab and the chat show an inline key box. The key is stored for the browser session only, and the review or question re-runs immediately.

## 6. Code execution

User code never runs on the app server in production. A local subprocess could read the server's environment, and with it the API keys, through `/proc`. Instead, `remote_runner` sends code to free, key-less, isolated sandboxes:

| Provider | Role |
|---|---|
| Compiler Explorer (godbolt.org) | Primary for most compiled languages; fastest (0.5–3 s) |
| Wandbox | Primary for JS, TS (`--noCheck`), PHP, R, Bash, Groovy, SQL, Julia, Nim |
| Paiza.IO (guest key) | Scala, Elixir, Erlang; fallback for many others |
| TIO (tio.run) | Clojure and PowerShell; universal last resort |

- **Routing.** `ROUTES` lists, for each language, the providers that passed the verification matrix (`tests/run_samples.py`: a stdin-echo program in 32 languages), fastest first.
- **Failover.** The next provider is tried when one is unavailable, rate-limited (HTTP 429), or hits a known toolchain breakage. Compilation errors in the user's code are returned as they are.
- **Discovery.** Compiler catalogues are fetched and cached for 6 hours, so new versions are picked up and retired ones never break a language.
- **Optional sandboxes.** Piston (`PISTON_URL`) and Judge0 (`JUDGE0_URL`) are tried after the free providers, and local toolchains after those. In production, `RUN_REMOTE_ONLY=1` disables local execution.

## 7. State & concurrency

- `analyze_code`, `start_repo_scan`, `send_chat_message` and `run_code` are `@rx.event(background=True)`. They copy inputs under `async with self`, work without holding the lock, and write results back in short locked sections.
- tree-sitter parsers are cached per thread, because they aren't thread-safe.
- The editor is an uncontrolled `<textarea>` keyed by `editor_key = path::version`. Every programmatic change (upload, history load, apply fix, clear) bumps the version so the editor remounts with the new content.

## 8. Configuration

All settings are in `.env.example`. The app runs with **zero** keys (full static analysis, CFG, and Python execution). Each key you add unlocks more: AI, private repos and higher GitHub limits, remote execution.

## 9. Known limits / next steps

- Native compiler checks in Analyze depend on the host image. On Reflex Cloud, other languages get syntax errors from tree-sitter, plus semantic findings from the AI review. Execution is unaffected, because it runs in the remote sandboxes.
- The free sandboxes are community services with fair-use limits. For very high traffic, add a self-hosted Piston (`PISTON_URL`); it's already wired in as a further fallback.
- The RAG index is in-process memory. With multiple backend workers, use Chroma or an external vector DB.
- A Monaco editor (syntax highlighting, inline issue markers) would be the next UX upgrade.
