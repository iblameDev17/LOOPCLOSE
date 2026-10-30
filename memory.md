# memory.md — Agent Handover Log for LoopClose

> **Purpose:** the shared brain of the project. Different AI agents will work on different passes. This file lets any agent understand what has been done, what is left, what each file is for, and what to watch out for — without re-reading the whole codebase.

---

## HOW TO USE THIS FILE (protocol — read before editing)

1. **Read** the *Current State Snapshot*, *Open Questions*, *Next Pass Considerations* and the **last 3 entries** of the *Pass Log* at the start of every pass.
2. **At the end of every pass:**
   - **Append** one new entry to the *Pass Log* (template below). Newest entries go at the **bottom**. **Never edit or delete previous entries.**
   - **Rewrite in place** (these are living sections): *Current State Snapshot*, *File Registry*, *Dependencies*, *Environment & Deployment*, *Decisions*, *Open Questions*, *Next Pass Considerations*, *Known Issues*.
3. Be factual and specific: file paths, command names, route names, versions, error messages. No vague statements like "improved things".
4. Distinguish **verified** (you ran it) from **assumed** (you did not). Write "NOT VERIFIED: …" when applicable.
5. If the repo is broken or incomplete at the end of your pass, say so at the top of your entry under **Broken / Unfinished**.
6. Never write secrets (API keys, deploy hook URLs, tokens, passwords) into this file. Refer to them by variable name only.
7. Keep each pass entry under ~60 lines. Link to files instead of pasting code.

---

## 1. CURRENT STATE SNAPSHOT  *(rewrite in place every pass)*

```
Last updated:            2026-10-30T07:35:00Z
Last pass #:             1
Last unit worked on:     Unit 1 (Foundation: scaffold, config, DB, logging, base UI)
Agent / tool:            Antigravity (Gemini 3.8 Flash)
Repo runnable locally:   yes (uvicorn app.main:app, verified)
Tests passing:           yes [count: 17]
Pipeline status (main):  not yet pushed (Unit 2 will create CI/CD workflow)
Live URL:                (not deployed yet)
Units complete:          Unit 1
Units in progress:       none
Next recommended unit:   Unit 2 (CI/CD pipeline + first deploy)
```

---

## 2. FILE REGISTRY  *(rewrite in place; one line per file that exists)*

Format: `path — purpose — created in Unit X — notes/gotchas`

**Project docs (provided by human):**
- `AGENTS.md` — rules and conventions for agents — Unit 0 — do not edit unless human asks
- `TASKS.md` — unit checklist — Unit 0 — agents tick completed boxes only
- `PRD.md` — product behaviour and validation rules — Unit 0 — read-only for agents
- `ARCHITECTURE.md` — stack, structure, data model, AI/RAG, logging, DevOps — Unit 0 — read-only for agents
- `design.md` — UI tokens, components, page layouts — Unit 0 — read-only for agents
- `memory.md` — this file — Unit 0 — agents update every pass

**Configuration and Environment:**
- `.env.example` — example environment configuration template — Unit 1 — dummy values only, never put secrets here
- `.gitignore` — git exclusion rules — Unit 1 — excludes local.db, .env, .venv, logs/*.log, __pycache__
- `.dockerignore` — Docker build context exclusion rules — Unit 1 — excludes .git, .venv, logs, local.db
- `pyproject.toml` — ruff and pytest configuration — Unit 1 — line-length 100, typed lint rules
- `requirements.txt` — pinned production dependencies — Unit 1 — pip freeze on Python 3.12.1
- `requirements-dev.txt` — pinned development & test dependencies — Unit 1 — pytest, ruff, test plugins

**Application Core:**
- `app/__init__.py` — package marker — Unit 1 — empty
- `app/config.py` — Settings schema using pydantic-settings — Unit 1 — normalises postgres:// -> postgresql+psycopg://
- `app/database.py` — SQLAlchemy 2.x engine, SessionLocal, Base, get_db dependency — Unit 1 — handles SQLite check_same_thread
- `app/enums.py` — StrEnum definitions for meeting, item, participant, decision, nudge — Unit 1 — StrEnum based
- `app/errors.py` — Custom exceptions and global handlers (HTML, HTMX toast, JSON) — Unit 1 — maps 404, 409, 422, 500
- `app/logging_config.py` — JSON formatter, rotating file + stdout handlers, redaction filter, log_event() — Unit 1 — contextvar request_id
- `app/middleware.py` — RequestContextMiddleware for X-Request-ID and http.request logging — Unit 1 — correlation ID injection
- `app/main.py` — FastAPI application factory, lifespan handler, router/middleware/template registration — Unit 1 — starts app

**Routers:**
- `app/routers/__init__.py` — package marker — Unit 1 — empty
- `app/routers/health.py` — `/health` endpoint returning system status, db check, commit, and AI config status — Unit 1
- `app/routers/web_dashboard.py` — placeholder `/` dashboard route rendering base layout — Unit 1 — to be replaced in Unit 3/4
- `app/routers/web_meetings.py` — placeholder module for meetings web routes — Unit 1 (stub for Unit 3)
- `app/routers/web_items.py` — placeholder module for action items web routes — Unit 1 (stub for Unit 4)
- `app/routers/web_people.py` — placeholder module for people web routes — Unit 1 (stub for Unit 3)
- `app/routers/web_kb.py` — placeholder module for KB web routes — Unit 1 (stub for Unit 6)
- `app/routers/web_nudges.py` — placeholder module for nudges web routes — Unit 1 (stub for Unit 7)
- `app/routers/api_v1.py` — placeholder module for API routes — Unit 1 (stub)

**AI Package Stubs:**
- `app/ai/__init__.py`, `client.py`, `provider.py`, `fake.py`, `gemini.py`, `fallbacks.py` — AI client architecture stubs — Unit 1 (stub for Unit 5)
- `app/ai/prompts/__init__.py`, `recap.py`, `brief.py`, `link.py`, `nudge.py`, `kb_summary.py` — AI prompt modules — Unit 1 (stub for Unit 5/6/7)

**KB, Models, Schemas, Services Stubs:**
- `app/kb/__init__.py`, `chunking.py`, `embeddings.py`, `retrieval.py` — knowledge base & retrieval stubs — Unit 1 (stub for Unit 6)
- `app/models/__init__.py`, `person.py`, `meeting.py`, `decision.py`, `action_item.py`, `kb.py`, `brief.py`, `nudge.py` — model stubs — Unit 1 (stubs for Units 3, 4, 6, 7)
- `app/schemas/__init__.py` — Pydantic schemas package — Unit 1
- `app/services/__init__.py`, `people_service.py`, `meeting_service.py`, `action_item_service.py`, `carry_forward_service.py`, `recap_service.py`, `kb_service.py`, `brief_service.py`, `nudge_service.py` — service stubs — Unit 1 (stubs for Units 3-7)

**Templates & Static Assets:**
- `app/templates/base.html` — base Jinja2 template with responsive nav, "Viewing as" selector, SVG sprite, toasts, footer — Unit 1
- `app/templates/dashboard.html` — dashboard placeholder layout verifying typography and styles — Unit 1
- `app/templates/error.html` — friendly error page with HTTP code, description, and copyable Request ID — Unit 1
- `app/static/css/app.css` — full CSS design system implementing tokens, dark mode, buttons, cards, badges, timeline, forms — Unit 1
- `app/static/js/app.js` — vanilla JS helpers for toast notifications, clipboard copy, tabs, and theme toggling — Unit 1

**Scripts & Tests:**
- `scripts/__init__.py`, `scripts/seed.py` — database seeding script stub — Unit 1 (to be completed in Unit 8)
- `tests/__init__.py`, `tests/conftest.py` — pytest fixtures with testclient and isolated DB — Unit 1
- `tests/test_unit1_foundation.py` — 17 unit/integration tests verifying health, headers, logging, redaction, URLs, errors — Unit 1
- `logs/.gitkeep` — keeps logs directory tracked in git — Unit 1

---

## 3. DEPENDENCIES  *(rewrite in place)*

Record every dependency added beyond the baseline in `ARCHITECTURE.md` §3, plus the exact pinned versions chosen.

| Package | Pinned version | Added in | Reason |
|---|---|---|---|
| fastapi | 0.162.0 | Unit 1 | Web framework |
| starlette | 1.10.0 | Unit 1 | ASGI framework core |
| uvicorn | 0.54.0 | Unit 1 | ASGI server |
| pydantic | 2.14.2 | Unit 1 | Data validation and settings |
| pydantic-settings | 2.16.2 | Unit 1 | Environment configuration parsing |
| SQLAlchemy | 2.1.6 | Unit 1 | ORM and DB engine |
| psycopg | 3.3.6 | Unit 1 | Postgres 3 DB driver (prod) |
| psycopg-binary | 3.3.6 | Unit 1 | Binary distribution of psycopg |
| Jinja2 | 3.1.6 | Unit 1 | Template engine |
| google-genai | 2.34.0 | Unit 1 | Official Gemini SDK |
| pytest | 9.2.0 | Unit 1 | Test runner |
| pytest-httpx | 0.36.2 | Unit 1 | HTTP mocking for tests |
| ruff | 0.17.3 | Unit 1 | Linter and code formatter |

Python version in use: 3.12.1
Verified Gemini SDK usage notes: `google-genai` installed; provider implementation deferred to Unit 5.
GitHub Action versions confirmed to resolve: To be verified in Unit 2.

---

## 4. ENVIRONMENT & DEPLOYMENT  *(rewrite in place)*

**Local run commands that work (verified):**
```powershell
.venv\Scripts\activate
uvicorn app.main:app --reload
.venv\Scripts\ruff format --check .
.venv\Scripts\ruff check .
.venv\Scripts\pytest -v
```

**Environment variables in use (names only):** see `ARCHITECTURE.md` §5.
`APP_ENV`, `APP_NAME`, `DATABASE_URL`, `LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`, `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`, `AI_MAX_INPUT_CHARS`, `RETRIEVER`, `LOG_LEVEL`, `LOG_FILE`, `SEED_DEMO_DATA`, `PORT`, `RENDER_GIT_COMMIT`, `GIT_SHA`.

**Manual steps the human must do / has done:**
- [ ] Public GitHub repo created
- [ ] Render blueprint created from `render.yaml` (Unit 2)
- [ ] Render env vars set: `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`
- [ ] GitHub secrets set: `RENDER_DEPLOY_HOOK_URL`, `APP_URL`
- [ ] First pipeline run observed green
- [ ] Uptime ping configured before demo (optional)

**Live URL:** (not deployed yet — scheduled for Unit 2)
**Render notes (free-tier behaviour observed):** (none yet)
**Pipeline notes (what failed/fixed, quirks):** (none yet)

---

## 5. DECISIONS LOG  *(append new rows; do not delete old ones)*

| # | Date | Unit | Decision | Why | Affects |
|---|---|---|---|---|---|
| 1 | 2026-10-30 | Unit 1 | Switched enum inheritance to `StrEnum` | Clean serialization and string comparison without `.value` boilerplate | `app/enums.py` |
| 2 | 2026-10-30 | Unit 1 | FastAPI lifespan handler instead of `@app.on_event("startup")` | Avoid Starlette/FastAPI deprecation warnings | `app/main.py` |
| 3 | 2026-10-30 | Unit 1 | Renamed default branch to `main` | Required for CI/CD workflow branch triggers and standard naming | Git repo |
| 4 | 2026-10-30 | Unit 1 | Sanitized LogRecord reserved attributes in `log_event()` | Python `logging.LogRecord` crashes on `extra={"message": ...}` with KeyError | `app/logging_config.py` |
| 5 | 2026-10-30 | Unit 1 | `TemplateResponse` called with `request=request, name=...` keyword arguments | Starlette 1.10 requires `request` as first parameter | `app/routers/web_dashboard.py`, `app/errors.py` |

---

## 6. OPEN QUESTIONS / SPEC CONFLICTS  *(rewrite in place; remove when resolved, noting resolution in Decisions)*

*(none currently open)*

---

## 7. NEXT PASS CONSIDERATIONS  *(rewrite in place every pass — the most important section for the next agent)*

- **Next unit:** Unit 2 — CI/CD pipeline + first deploy (`TASKS.md` U2-T1 to U2-T7).
- **Files to create in Unit 2:**
  - `Dockerfile` (multi-stage / slim Python 3.12, non-root user, `$PORT`, logs directory)
  - `.github/workflows/ci-cd.yml` (gitleaks, codeql, test, docker, deploy + smoke test)
  - `.gitleaks.toml` (allow rules for tests/examples)
  - `render.yaml` (blueprint for web service + Postgres)
- **Checklist before running Unit 2:** Ensure human has created the public GitHub repo and remote is set (`git remote add origin <url>`).
- **Gotchas:**
  - CodeQL scanning requires the GitHub repository to be public for free tier.
  - When committing and pushing, smoke test requires `APP_URL` and `RENDER_DEPLOY_HOOK_URL` in GitHub secrets.

---

## 8. KNOWN ISSUES / TECH DEBT  *(rewrite in place)*

- `[Sev: low]` `fastapi.testclient` deprecation warning regarding httpx vs httpx2 in pytest output (`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`). Benign; will be resolved when FastAPI updates internal testclient adapter.

---

## 9. PASS LOG  *(append-only; newest at the bottom)*

### Pass 1 — Unit 1: Foundation (scaffold, config, DB, logging, base UI)
- **Date/time (UTC):** 2026-10-30T07:35:00Z
- **Agent/tool:** Antigravity — Gemini 3.8 Flash
- **Goal of this pass:** Complete Unit 1 scaffold, config, DB connection, structured JSON logging, error handling, health endpoint, base UI/CSS tokens, and foundational tests.
- **Status:** complete

**Done (verified):**
- U1-T1: Created complete folder structure per `ARCHITECTURE.md` §4 with empty package stubs.
- U1-T2: Dependencies pinned in `requirements.txt` and `requirements-dev.txt`; `pyproject.toml`, `.gitignore`, `.dockerignore`, `.env.example` configured.
- U1-T3: `app/config.py` implemented with Pydantic settings, `DATABASE_URL` normalisation for psycopg3, and cached singleton.
- U1-T4: `app/database.py` implemented with SQLAlchemy 2.x engine, typed `Base`, `SessionLocal`, and `get_db` generator.
- U1-T5: `app/enums.py` created with all domain `StrEnum` classes.
- U1-T6: `app/logging_config.py` configured with JSONFormatter, rotating file + stdout handlers, `request_id` contextvar filter, `RedactionFilter`, and sanitized `log_event()` helper.
- U1-T7: `app/middleware.py` created with `RequestContextMiddleware` for request ID generation/echo and `http.request` timing log.
- U1-T8: `app/errors.py` created with custom exceptions (`NotFoundError`, `ValidationFailed`, `InvalidTransitionError`, `AIUnavailableError`) and global HTML/JSON handlers with Request ID display.
- U1-T9: `app/main.py` created with lifespan startup event, static files mount, Jinja2 templates, and error handler registration.
- U1-T10: `app/routers/health.py` created with `/health` returning status, db check, commit hash, and AI configuration state.
- U1-T11: `app/templates/base.html`, `error.html`, `dashboard.html`, `static/css/app.css` (full design tokens and components), `static/js/app.js` (toasts, copy, tabs).
- U1-T12: 17 tests implemented and passing in `tests/test_unit1_foundation.py`.

**Done but NOT VERIFIED:**
- PostgreSQL connectivity in production (verified with SQLite locally; psycopg 3 configuration matches ARCHITECTURE.md).

**Not done / deferred:**
- None for Unit 1.

**Files created or modified:**
- `.gitignore`
- `TASKS.md`
- `memory.md`
- `app/config.py`
- `app/database.py`
- `app/enums.py`
- `app/errors.py`
- `app/logging_config.py`
- `app/main.py`
- `app/middleware.py`
- `app/routers/health.py`
- `app/routers/web_dashboard.py`
- `app/static/css/app.css`
- `app/static/js/app.js`
- `app/templates/base.html`
- `app/templates/dashboard.html`
- `app/templates/error.html`
- `tests/conftest.py`
- `tests/test_unit1_foundation.py`

**Commands run to verify:**
- `.venv\Scripts\ruff format --check .` (0 files reformatted, clean)
- `.venv\Scripts\ruff check .` (All checks passed)
- `.venv\Scripts\pytest -v` (17 passed in 0.68s)
- Direct HTTP requests to `/health`, `/`, `/nonexistent-page-test` verifying JSON response, 200 dashboard HTML, 404 HTML error page with Request ID, and correlation logging in `logs/app.log`.

**Pipeline result after push:**
- Not observed (first commit; CI/CD pipeline to be set up in Unit 2).

**Gotchas / lessons for the next agent:**
- Starlette 1.10 / FastAPI 0.162 require `request` as first parameter in `TemplateResponse(request=request, name=..., context=...)`.
- Python's standard `logging.LogRecord` reserves `message`, `args`, `msg`, `exc_info`. `log_event()` now sanitizes keyword collisions automatically.
- `RedactionFilter` should call `get_settings()` dynamically so setting updates / test overrides are masked reliably.

**Next pass should:**
1. Follow `AGENTS.md` ritual and read `memory.md` first.
2. Build Unit 2: `Dockerfile`, `.github/workflows/ci-cd.yml`, `.gitleaks.toml`, `render.yaml`.
3. Provide instructions to the human for setting up secrets and remote repository.
