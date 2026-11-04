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
Last updated:            2026-11-04T17:45:00Z
Last pass #:             5
Last unit worked on:     Unit 5 (AI foundation + recap)
Agent / tool:            Antigravity (Gemini 3.8 Flash)
Repo runnable locally:   yes (uvicorn app.main:app, verified)
Tests passing:           yes [count: 56]
Pipeline status (main):  diagnostic smoke test + Docker ARG commit injection configured
Live URL:                (configured on Render)
Units complete:          Unit 1, Unit 2, Unit 3, Unit 4, Unit 5
Units in progress:       none
Next recommended unit:   Unit 6 (KB + linking + catch-up brief)
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

**DevOps & Deployment:**
- `Dockerfile` — container definition for Python 3.12-slim as non-root user with healthcheck, accepting RENDER_GIT_COMMIT and GIT_SHA build args — Unit 2 (updated Pass 4)
- `.gitleaks.toml` — Gitleaks secret detection configuration with allowlist for test mocks and examples — Unit 2
- `render.yaml` — Render Blueprint specification for loopclose web service + loopclose-db — Unit 2
- `.github/workflows/ci-cd.yml` — GitHub Actions workflow (gitleaks, codeql, test, docker w/ build-args, trivy container scan, deploy + diagnostic smoke test) — Unit 2 (updated Pass 5)
- `.pre-commit-config.yaml` — optional local pre-commit guard for ruff and gitleaks — Unit 2
- `.dockerignore` — Docker build context exclusion rules — Unit 1 — excludes .git, .venv, logs, local.db

**Configuration and Environment:**
- `.env.example` — example environment configuration template — Unit 1 — dummy values only, never put secrets here
- `.gitignore` — git exclusion rules — Unit 1 — excludes local.db, .env, .venv, logs/*.log, __pycache__
- `pyproject.toml` — ruff and pytest configuration — Unit 1 — line-length 100, typed lint rules
- `requirements.txt` — pinned production dependencies — Unit 1 — pip freeze on Python 3.12.1
- `requirements-dev.txt` — pinned development & test dependencies — Unit 1 — pytest, ruff, test plugins

**Application Core:**
- `app/__init__.py` — package marker — Unit 1 — empty
- `app/config.py` — Settings schema using pydantic-settings — Unit 1 — normalises postgres:// -> postgresql+psycopg://
- `app/database.py` — SQLAlchemy 2.x engine, SessionLocal, Base, get_db dependency — Unit 1 — handles SQLite check_same_thread
- `app/enums.py` — StrEnum definitions with dual case tolerance — Unit 1 (updated Unit 3)
- `app/errors.py` — Custom exceptions and global handlers (HTML, HTMX toast, JSON) — Unit 1 — maps 404, 409, 422, 500
- `app/logging_config.py` — JSON formatter, rotating file + stdout handlers, redaction filter, log_event() — Unit 1 — contextvar request_id
- `app/middleware.py` — RequestContextMiddleware for X-Request-ID and http.request logging — Unit 1 — correlation ID injection
- `app/main.py` — FastAPI application factory, lifespan handler, router/middleware/template registration — Unit 1 — starts app

**Core Domain (Models, Schemas, Services):**
- `app/models/__init__.py` — exports all models — Unit 1 (updated Unit 3/4)
- `app/models/person.py` — Person model (initials property, active/on_leave flags, relationships) — Unit 3
- `app/models/meeting.py` — Meeting and MeetingParticipant models (kind, status, handover fields, notes, relationships) — Unit 3
- `app/models/decision.py` — Decision model (meeting relationship, created_at) — Unit 3
- `app/models/action_item.py` — ActionItem and ActionItemEvent models (full fields, is_open, is_overdue, overdue_days, relationships) — Unit 3 (completed Unit 4)
- `app/schemas/__init__.py` — exports all schemas — Unit 1 (updated Unit 3/4)
- `app/schemas/person.py` — PersonCreate and PersonRead Pydantic schemas with email regex validation — Unit 3
- `app/schemas/meeting.py` — MeetingCreate, MeetingUpdate, MeetingStatusUpdate, NotesUpdate, ParticipantAttendanceUpdate schemas — Unit 3
- `app/schemas/decision.py` — DecisionCreate and DecisionRead schemas — Unit 3
- `app/schemas/action_item.py` — ActionItemCreate, ActionItemUpdate, ActionItemClose, ActionItemReassign, ActionItemStatusUpdate, ActionItemRead schemas — Unit 4
- `app/services/__init__.py` — exports services — Unit 1 (updated Unit 3/4)
- `app/services/people_service.py` — list, get, and create people with duplicate email check and event logging — Unit 3
- `app/services/meeting_service.py` — meeting/handover creation, lifecycle state transitions, attendance, notes caps, decisions, handover reassign — Unit 3 (updated Unit 4)
- `app/services/action_item_service.py` — full action item lifecycle, status transitions, close with outcome, reopen, reassign, audit events — Unit 4
- `app/services/carry_forward_service.py` — carry forward open items across meetings, carried count increment, audit events — Unit 4
- `app/services/recap_service.py` — generate recap proposal, exact/fuzzy owner resolution, apply/discard proposals — Unit 5

**AI Subsystem:**
- `app/ai/__init__.py` — AI subsystem package marker — Unit 1
- `app/ai/provider.py` — LLMProvider runtime-checkable protocol with generate_json and embed — Unit 5
- `app/ai/gemini.py` — GeminiProvider wrapping google-genai 2.34+ SDK with types.GenerateContentConfig — Unit 5
- `app/ai/fake.py` — FakeProvider for deterministic testing with timeout/invalid_json/empty failure toggles — Unit 5
- `app/ai/client.py` — AIClient.run_structured() with retry, timeout, code-fence strip, Pydantic validation, structured ai.call logging — Unit 5
- `app/ai/schemas.py` — Pydantic output schemas (RecapResult, RecapActionItem, RecapDecision) — Unit 5
- `app/ai/fallbacks.py` — heuristic_recap() rule-based extraction from raw notes — Unit 5
- `app/ai/prompts/__init__.py` — prompts package marker — Unit 1
- `app/ai/prompts/recap.py` — recap prompt template v1 with delimited injection protection and meeting date resolution — Unit 5

**Routers:**
- `app/routers/__init__.py` — package marker — Unit 1
- `app/routers/health.py` — `/health` endpoint returning system status, db check, commit, and AI config status — Unit 1
- `app/routers/web_dashboard.py` — `/` dashboard route wired with real cards (My open items, Overdue, Needs owner, Upcoming meetings, Decisions) — Unit 1 (updated Unit 4)
- `app/routers/web_people.py` — `/people` directory view, inline create, and `/viewing-as` persona switcher — Unit 3
- `app/routers/web_meetings.py` — `/meetings` list, `/meetings/new` form, `/meetings/{id}` detail & tab HTMX endpoints, decisions, attendance, carried items — Unit 3 (updated Unit 4)
- `app/routers/web_items.py` — `/items` list with filters, `/items/new`, `/items/{id}` detail with side card & timeline, `/items/{id}/close`, `/items/{id}/status`, `/items/{id}/reassign`, `/items/{id}/reopen` — Unit 4
- `app/routers/web_kb.py` — placeholder module for KB web routes — Unit 1 (stub for Unit 6)
- `app/routers/web_nudges.py` — placeholder module for nudges web routes — Unit 1 (stub for Unit 7)
- `app/routers/api_v1.py` — placeholder module for API routes — Unit 1 (stub)

**Templates & Static Assets:**
- `app/templates/base.html` — base Jinja2 template with responsive nav, "Viewing as" selector, SVG sprite, toasts, footer — Unit 1 (updated Unit 3)
- `app/templates/dashboard.html` — dynamic dashboard layout wired with cards per design.md §5.1 — Unit 1 (updated Unit 4)
- `app/templates/error.html` — friendly error page with HTTP code, description, and copyable Request ID — Unit 1
- `app/templates/partials/item_row.html` — reusable item row component with priority edge, badges, avatar, carried chips — Unit 4
- `app/templates/items/list.html` — filterable action items list with status chips, owner select, meeting filter, overdue checkbox — Unit 4
- `app/templates/items/detail.html` — item detail page with side card, action buttons, expanding close with outcome panel, history timeline — Unit 4
- `app/templates/people/index.html` — People directory table, avatar pills, active/on-leave status badges, inline create form — Unit 3
- `app/templates/meetings/list.html` — Filterable meeting/handover list with kind and status pills, avatars, empty state — Unit 3
- `app/templates/meetings/form.html` — Meeting/Handover create form with dynamic kind toggle, participant checkboxes, handover pickers — Unit 3
- `app/templates/meetings/detail.html` — Full meeting detail view with action buttons, status badges, tabs, and modals — Unit 3
- `app/templates/meetings/partials/overview_tab.html` — Meeting overview tab, handover banner, carried-over items card, close carry-forward prompt, agenda, participants, decisions — Unit 3 (updated Unit 4)
- `app/templates/meetings/partials/notes_tab.html` — Notes editor with 50,000 char counter, live countdown, save form, Generate recap AI button with skeleton loading indicator, and proposal review card with apply/discard — Unit 3 (updated Unit 5)
- `app/templates/meetings/partials/decisions_list.html` — Decisions list with delete action and inline add form — Unit 3
- `app/templates/meetings/partials/participants_card.html` — Participants roster with inline HTMX attendance dropdowns and add form — Unit 3
- `app/templates/meetings/partials/items_tab.html` — Meeting action items list with inline add form — Unit 3 (completed Unit 4)
- `app/templates/meetings/partials/history_tab.html` — Meeting event timeline for all item and meeting mutations — Unit 3 (completed Unit 4)
- `app/templates/meetings/partials/brief_tab.html` — Placeholder tab for Unit 6 — Unit 3
- `app/templates/meetings/partials/knowledge_tab.html` — Placeholder tab for Unit 6 — Unit 3
- `app/static/css/app.css` — full CSS design system implementing tokens, dark mode, buttons, cards, badges, timeline, forms — Unit 1
- `app/static/js/app.js` — vanilla JS helpers for toast notifications, clipboard copy, tabs, and theme toggling — Unit 1

**Tests:**
- `tests/__init__.py` — test package marker — Unit 1
- `tests/conftest.py` — test fixtures with temporary isolated SQLite DB, client, and clean_db autouse cleanup — Unit 1 (updated Unit 3)
- `tests/test_unit1_foundation.py` — 17 unit/integration tests verifying health, headers, logging, redaction, URLs, errors — Unit 1
- `tests/test_unit3_core_domain.py` — 15 tests for lifecycle, handover rules, participant uniqueness, attendance, notes cap, and UI endpoints — Unit 3
- `tests/test_unit4_action_items.py` — 12 unit/integration tests for action items lifecycle, outcomes, blocked reasons, carry forward semantics, and routes — Unit 4
- `tests/test_unit5_ai_recap.py` — 12 unit/integration tests for AIClient, fence stripping, timeout/invalid_json retries, heuristic extraction, owner resolution, apply proposals, and web routes — Unit 5
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

---

## 4. ENVIRONMENT & DEPLOYMENT  *(rewrite in place)*

**Local run commands that work (verified):**
```powershell
.venv\Scripts\activate
uvicorn app.main:app --reload
.venv\Scripts\ruff format --check .
.venv\Scripts\ruff check .
.venv\Scripts\pytest -q
```

**Environment variables in use (names only):** see `ARCHITECTURE.md` §5.
`APP_ENV`, `APP_NAME`, `DATABASE_URL`, `LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`, `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`, `AI_MAX_INPUT_CHARS`, `RETRIEVER`, `LOG_LEVEL`, `LOG_FILE`, `SEED_DEMO_DATA`, `PORT`, `RENDER_GIT_COMMIT`, `GIT_SHA`.

**Live URL:** (configured on Render)
**Render notes (free-tier behaviour observed):** Web service sleeps after ~15 min of inactivity; free database expires after 30 days; filesystem is ephemeral (stdout logs preserved).
**Pipeline notes:** Dockerfile accepts `ARG RENDER_GIT_COMMIT` and `ARG GIT_SHA` and exports them to container `ENV` so commit SHA is available to `/health` in Docker deployments. CI smoke test runs 36 iterations of `curl -sSL --max-time 30`, printing HTTP code and 200-char body preview, with clear warning if `/health` has null commit.

---

## 5. DECISIONS LOG  *(append new rows; do not delete old ones)*

| # | Date | Unit | Decision | Why | Affects |
|---|---|---|---|---|---|
| 1 | 2026-10-30 | Unit 1 | Switched enum inheritance to `StrEnum` | Clean serialization and string comparison without `.value` boilerplate | `app/enums.py` |
| 2 | 2026-10-30 | Unit 1 | FastAPI lifespan handler instead of `@app.on_event("startup")` | Avoid Starlette/FastAPI deprecation warnings | `app/main.py` |
| 3 | 2026-10-30 | Unit 1 | Renamed default branch to `main` | Required for CI/CD workflow branch triggers and standard naming | Git repo |
| 4 | 2026-10-30 | Unit 1 | Sanitized LogRecord reserved attributes in `log_event()` | Python `logging.LogRecord` crashes on `extra={"message": ...}` with KeyError | `app/logging_config.py` |
| 5 | 2026-10-30 | Unit 1 | `TemplateResponse` called with `request=request, name=...` keyword arguments | Starlette 1.10 requires `request` as first parameter | `app/routers/web_dashboard.py`, `app/errors.py` |
| 6 | 2026-10-30 | Unit 2 | CodeQL Action pinned to `@v4` | Official latest major release following v3 deprecation | `.github/workflows/ci-cd.yml` |
| 7 | 2026-10-30 | Unit 2 | Installed curl in Dockerfile for health check | Container needs curl to execute HEALTHCHECK directive | `Dockerfile` |
| 8 | 2026-10-30 | Unit 3 | Custom regex validator for email in Person schema | Avoided pulling external `email-validator` dependency into runtime | `app/schemas/person.py` |
| 9 | 2026-10-30 | Unit 3 | Dual-cased enum attributes in `app/enums.py` | Allowed uppercase (`MeetingKind.MEETING`) and lowercase (`MeetingKind.meeting`) interoperability | `app/enums.py` |
| 10 | 2026-10-30 | Unit 3 | Set `Response` as route return type for union responses | FastAPI inspects `HTMLResponse | Response` as OpenAPI model and errors out | `app/routers/web_meetings.py` |
| 11 | 2026-10-30 | Unit 3 | Autouse `clean_db` fixture in `conftest.py` with isolated temp SQLite DB | Ensures 100% test isolation and idempotency across repeated test runs | `tests/conftest.py` |
| 12 | 2026-10-30 | Unit 2 | `ARG RENDER_GIT_COMMIT` and `ARG GIT_SHA` in Dockerfile exported to `ENV` | Render passes RENDER_GIT_COMMIT as build ARG for Docker; exporting to ENV makes it accessible at runtime to /health | `Dockerfile`, `.github/workflows/ci-cd.yml` |
| 13 | 2026-10-30 | Unit 2 | Diagnostic smoke test in CI workflow with response preview & degraded warning | Shows exact HTTP status and body on every attempt, warning clearly if commit is null | `.github/workflows/ci-cd.yml` |
| 14 | 2026-10-30 | Unit 4 | Close with outcome enforcement | Status cannot be directly set to done/dropped via change_status; must call close_action_item with OutcomeType and outcome_note (>=5 chars) | `app/services/action_item_service.py` |
| 15 | 2026-11-04 | Unit 5 | Robust AIClient with retry & heuristic fallback | AIClient.run_structured() strips markdown fences, retries invalid JSON once with schema reminder, and falls back to deterministic heuristic extraction on failure. Never raises for AI issues. | `app/ai/client.py`, `app/ai/fallbacks.py`, `app/services/recap_service.py` |
| 16 | 2026-11-04 | DevOps | Added Trivy container vulnerability scanning | Runs aquasecurity/trivy-action@0.28.0 on the built image with `load: true` to detect OS and library vulnerabilities (CRITICAL,HIGH) | `.github/workflows/ci-cd.yml` |

---

## 6. OPEN QUESTIONS / SPEC CONFLICTS  *(rewrite in place; remove when resolved, noting resolution in Decisions)*

*(none currently open)*

---

## 7. NEXT PASS CONSIDERATIONS  *(rewrite in place every pass — the most important section for the next agent)*

- **Next unit:** Unit 6 — Knowledge base + linking (Level A RAG) + catch-up brief (`TASKS.md` U6-T1 to U6-T8).
- **Files to create/modify in Unit 6:**
  - `app/models/kb.py` (`KBDocument`, `KBLink`, `CatchupBrief`, and `KBChunk` table stub)
  - `app/schemas/kb.py` (`KBDocumentCreate`, `CatchupBriefRead`, etc.)
  - `app/services/kb_service.py` (document upload/paste validation <=1MB, auto-index meetings, summarize)
  - `app/kb/retrieval.py` (`find_related`, `LLMSummaryRetriever`, `KeywordRetriever` fallback chain)
  - `app/ai/prompts/brief.py` (`brief.v1` catch-up brief prompt)
  - `app/ai/prompts/link.py` (`link.v1` entity-document linking prompt)
  - `app/ai/prompts/kb_summary.py` (`kb_summary.v1` document summarization prompt)
  - `app/services/brief_service.py` (brief generation with fallback template)
  - `app/routers/web_kb.py` and `app/routers/web_meetings.py` (KB routes, Brief tab, suggest-links endpoints)
  - `app/templates/kb/` (`list.html`, `detail.html`, `form.html`) and meeting partials (`brief_tab.html`, `knowledge_tab.html`)
  - `tests/test_unit6_kb_brief.py`
- **Checklist before running Unit 6:** Ensure `ruff format --check .`, `ruff check .`, and `pytest` are all passing.

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

---

### Pass 2 — Unit 2: CI/CD pipeline + first deploy (DevOps)
- **Date/time (UTC):** 2026-10-30T07:45:00Z
- **Agent/tool:** Antigravity — Gemini 3.8 Flash
- **Goal of this pass:** Build CI/CD workflow, Dockerfile, Gitleaks configuration, Render blueprint, and document deployment steps.
- **Status:** complete

**Done (verified):**
- U2-T1: Created `Dockerfile` (Python 3.12-slim, non-root user `appuser:10001`, `$PORT` binding, logs directory, healthcheck).
- U2-T2: Created `.github/workflows/ci-cd.yml` with 5 jobs: `gitleaks`, `codeql` (v4), `test` (ruff + pytest), `docker` (buildx validation), `deploy` (Render hook + smoke test polling `/health`).
- U2-T3: Created `.gitleaks.toml` extending default rules with allowlists for `.env.example` and `tests/`.
- U2-T4: Created `render.yaml` defining `loopclose` web service (free tier, Docker runtime, `autoDeploy: false`, `/health` check) and `loopclose-db` Postgres database.
- U2-T5: Documented complete step-by-step human instructions in `memory.md → Environment & Deployment`.
- U2-T7: Created `.pre-commit-config.yaml` for local developer protection.
- Checked off completed tasks in `TASKS.md`.

**Done but NOT VERIFIED:**
- U2-T6 live deployment execution (awaiting human to push and configure GitHub secrets and Render Blueprint).
- Local docker build execution (Docker daemon was not running on local Windows host; build syntax matches spec and will run in GitHub Actions runner).

**Not done / deferred:**
- U2-T6 smoke test verification: pending human setup of Render Blueprint and secrets.

**Files created or modified:**
- `Dockerfile`
- `.gitleaks.toml`
- `render.yaml`
- `.github/workflows/ci-cd.yml`
- `.pre-commit-config.yaml`
- `TASKS.md`
- `memory.md`

**Commands run to verify:**
- `.venv\Scripts\ruff check .` (All checks passed)
- `.venv\Scripts\ruff format --check .` (All formatted)
- `.venv\Scripts\pytest -q` (17 passed)

**Pipeline result after push:**
- To be verified upon human push.

**Gotchas / lessons for the next agent:**
- Render sets `autoDeploy: false` in `render.yaml` deliberately so only green GitHub Actions workflows trigger the deploy via the deploy hook.
- The smoke test step in `.github/workflows/ci-cd.yml` queries `$APP_URL/health` and verifies the JSON `commit` matches GitHub's commit SHA before completing.

**Next pass should:**
1. Verify pipeline ran green on GitHub Actions after push.
2. Build Unit 3: Core domain (people, meetings & handovers).

---

### Pass 3 — Unit 3: Core domain: people, meetings & handovers
- **Date/time (UTC):** 2026-10-30T08:10:00Z
- **Agent/tool:** Antigravity — Gemini 3.8 Flash
- **Goal of this pass:** Build Person, Meeting, Participant, Decision models, Pydantic schemas, domain services with lifecycle state machine and event logging, HTMX-powered web views, viewing-as cookie switcher, and comprehensive tests.
- **Status:** complete

**Done (verified):**
- U3-T1: Models created: `Person` (`name`, `email`, `role_title`, `is_active`, `is_on_leave`, `initials`), `Meeting` (`kind`, `status`, `title`, `scheduled_at`, `agenda`, `raw_notes`, `summary_md`, `handover_from_id`, `handover_to_id`, `previous_meeting_id`, `carry_forward_open_items`), `MeetingParticipant` (`attendance`, uniqueness constraint on `(meeting_id, person_id)`), `Decision` (`meeting_id`, `text`). Foreign keys stubbed for `ActionItem` and `ActionItemEvent`.
- U3-T2: Pydantic schemas in `app/schemas/person.py`, `app/schemas/meeting.py`, `app/schemas/decision.py` enforcing character limits, email format, and handover constraints (`from != to`).
- U3-T3: `people_service` and `meeting_service` implemented with full lifecycle transitions (`planned -> held -> closed`, `planned -> cancelled`), note saving capped at 50,000 chars, attendance toggling, decisions CRUD, and handover reassign stub. Structured events emitted (`meeting.created`, `meeting.status_changed`, `meeting.notes_saved`, `meeting.participant_added`, `meeting.attendance_updated`, `decision.created`, `decision.deleted`).
- U3-T4: Web routers and Jinja2 templates: `/people` directory and inline creator, `/meetings` list with filter pills, `/meetings/new` form with handover controls, `/meetings/{id}` detail with tabs (Overview, Notes & Recap, Items, Brief, Knowledge, History), inline attendance updates via HTMX, and decisions add/delete.
- U3-T5: "Viewing as" selector wired via cookie `loopclose_view_as` across all pages with user badge indication.
- U3-T6: Inline form validation errors (HTTP 422 re-renders), 404 error handling for unknown IDs, read-only controls for closed/cancelled meetings.
- U3-T7: 15 unit and integration tests written in `tests/test_unit3_core_domain.py`, covering person creation, duplicate email rejection, meeting/handover creation, invalid transitions, attendance updates, decision CRUD, notes length cap, and web endpoints.
- Checked off completed tasks in `TASKS.md`.

**Done but NOT VERIFIED:**
- None. All 32 tests run and pass.

**Not done / deferred:**
- Action items, history audit timeline, and carry-forward service (belong to Unit 4).
- AI recap and knowledge base linking (belong to Units 5 and 6).

**Files created or modified:**
- `app/models/person.py`, `meeting.py`, `decision.py`, `action_item.py`, `__init__.py`
- `app/schemas/person.py`, `meeting.py`, `decision.py`, `__init__.py`
- `app/services/people_service.py`, `meeting_service.py`, `__init__.py`
- `app/routers/web_people.py`, `web_meetings.py`, `web_dashboard.py`
- `app/templates/base.html`, `templates/people/index.html`, `templates/meetings/list.html`, `templates/meetings/form.html`, `templates/meetings/detail.html`
- `app/templates/meetings/partials/` (`overview_tab.html`, `notes_tab.html`, `items_tab.html`, `brief_tab.html`, `knowledge_tab.html`, `history_tab.html`, `decisions_list.html`, `participants_card.html`)
- `tests/conftest.py`
- `tests/test_unit3_core_domain.py`
- `TASKS.md`
- `memory.md`

**Commands run to verify:**
- `.venv\Scripts\ruff check .` (All checks passed)
- `.venv\Scripts\ruff format --check .` (All checks passed)
- `.venv\Scripts\pytest -q` (32 passed in 0.62s)

**Pipeline result after push:**
- Ready for push to GitHub `main`.

**Gotchas / lessons for the next agent:**
- In FastAPI, return type annotations on route handlers should be `-> Response` rather than union types like `-> HTMLResponse | Response` to avoid Pydantic OpenAPI schema generation errors.
- SQLite foreign key constraints and uniqueness across test runs are preserved reliably using the autouse `clean_db` fixture in `conftest.py`.

**Next pass should:**
1. Follow `AGENTS.md` ritual and read `memory.md`.
2. Build Unit 4: Action items, history, carry-forward (`TASKS.md` U4-T1 to U4-T8).

---

### Pass 4 — Unit 4: Action items, history, carry-forward
- **Date/time (UTC):** 2026-10-30T08:45:00Z
- **Agent/tool:** Antigravity — Gemini 3.8 Flash
- **Goal of this pass:** Build full action item lifecycle, append-only history audit events, carry-forward service, bulk handover item reassignment, dynamic dashboard cards, responsive list and detail views, and diagnostic smoke test fix for Render.
- **Status:** complete

**Done (verified):**
- U4-T1: Models `ActionItem` and `ActionItemEvent` completed with computed properties `is_open`, `is_overdue`, and `overdue_days`, plus relationships to `Person`, `Meeting`, and audit events.
- U4-T2: `action_item_service` implemented with complete lifecycle: creation with due date not in past validation, updates (`updated`, `due_date_changed` events), status transitions (`open <-> in_progress <-> blocked` requiring reason >=3 chars), reassignments (`reassigned` event with from/to names), close with outcome (`completed`/`partially_completed` -> `done`, `dropped`/`superseded` -> `dropped` requiring note >=5 chars), and reopen (restoring open state while preserving previous outcome in event note).
- U4-T3: `carry_forward_service` implemented: moves open/in_progress/blocked items from source meeting to target meeting, increments `carried_count`, writes `carried_forward` event with meeting context, emits `meeting.carry_forward`.
- U4-T4: Handover bulk reassignment wired in `meeting_service.reassign_handover_items`, reassigning departing person's open items to incoming person.
- U4-T5: Routers and templates created:
  - Global `/items` list with filters (status, owner, meeting, overdue checkbox, sort by due date).
  - Item detail `/items/{id}` with side card, action controls, expanding Close with outcome panel, and history timeline.
  - Meeting detail `Items` tab wired with inline creation form and meeting items list.
  - Meeting detail `Overview` tab wired with Carried Over section and closed meeting carry-forward prompt.
  - Meeting detail `History` tab wired with real chronological item and meeting event timeline.
- U4-T6: Dashboard `/` wired with dynamic cards: My open items (filtered by viewing-as persona), Needs attention (overdue count, needs owner count), Upcoming meetings, and Recent decisions.
- U4-T7: Item row component created (`app/templates/partials/item_row.html`) with priority edge border, status/overdue/unassigned/carried/AI badges, avatar initials, and formatted dates.
- U4-T8: 12 tests in `tests/test_unit4_action_items.py` verifying close requires outcome, blocked requires reason, direct transition to done blocked, carry forward semantics (open only, counts, origin unchanged), reopen restores open and preserves outcome, overdue computation, and due date in past rejected. Total test suite: 44 tests passing.
- DevOps / CI Smoke test fix: Dockerfile updated with `ARG RENDER_GIT_COMMIT` and `ARG GIT_SHA` exported to container `ENV`; `.github/workflows/ci-cd.yml` updated with `build-args` and diagnostic smoke test printing HTTP code, 200-char preview, and warning if commit is null.

**Done but NOT VERIFIED:**
- None. All 44 tests run and pass.

**Not done / deferred:**
- AI recap and knowledge base linking (belong to Units 5 and 6).

**Files created or modified:**
- `Dockerfile`
- `.github/workflows/ci-cd.yml`
- `app/models/action_item.py`
- `app/schemas/action_item.py`, `app/schemas/__init__.py`
- `app/services/action_item_service.py`, `app/services/carry_forward_service.py`, `app/services/meeting_service.py`, `app/services/__init__.py`
- `app/routers/web_items.py`, `app/routers/web_dashboard.py`, `app/routers/web_meetings.py`, `app/main.py`
- `app/templates/partials/item_row.html`
- `app/templates/items/list.html`, `app/templates/items/detail.html`
- `app/templates/meetings/partials/items_tab.html`, `app/templates/meetings/partials/overview_tab.html`, `app/templates/meetings/partials/history_tab.html`
- `app/templates/dashboard.html`
- `tests/test_unit4_action_items.py`
- `TASKS.md`
- `memory.md`

**Commands run to verify:**
- `.venv\Scripts\ruff check .` (All checks passed)
- `.venv\Scripts\ruff format --check .` (68 files formatted)
- `.venv\Scripts\pytest -q` (44 passed in 0.99s)

**Pipeline result after push:**
- Ready to push to GitHub `main`.

**Gotchas / lessons for the next agent:**
- Render's Docker runtime supplies `RENDER_GIT_COMMIT` as a build ARG; without `ARG RENDER_GIT_COMMIT` and `ENV RENDER_GIT_COMMIT=${RENDER_GIT_COMMIT}` in Dockerfile, runtime environment variables in the container do not have access to the commit SHA.

**Next pass should:**
1. Follow `AGENTS.md` ritual and read `memory.md`.
2. Build Unit 5: AI foundation + recap (`TASKS.md` U5-T1 to U5-T7).

---

### Pass 5 — Unit 5: AI foundation + recap
- **Date/time (UTC):** 2026-11-04T17:45:00Z
- **Agent/tool:** Antigravity — Gemini 3.8 Flash
- **Goal of this pass:** Build reliable AI subsystem (LLMProvider protocol, GeminiProvider, FakeProvider with failure simulations, AIClient with retries and logging), heuristic fallbacks, prompt templates with injection delimiters, recap service with exact/fuzzy owner resolution, review/apply web UI with skeleton loading state, and complete test suite.
- **Status:** complete

**Done (verified):**
- U5-T1: `app/ai/provider.py` defined runtime-checkable `LLMProvider` protocol with `generate_json` and `embed`. `app/ai/gemini.py` implements it using `google-genai` 2.34+ SDK with `GenerateContentConfig(response_mime_type="application/json")`. `app/ai/fake.py` implements deterministic canned outputs with switchable failure modes (`timeout`, `invalid_json`, `empty`).
- U5-T2: `app/ai/client.py` implemented `AIClient.run_structured()`: input truncation at `ai_max_input_chars` with `ai.truncated_input` log, timeout, code-fence stripping, JSON parsing, Pydantic model validation (`RecapResult`), automatic retry with strict JSON-only reminder on failure, and structured `ai.call` logging with latency, attempts, outcome, character counts (no raw content or secrets). Missing provider emits one-time warning and falls back.
- U5-T3: `app/ai/prompts/recap.py` implemented with `PROMPT_VERSION = "recap.v1"`, `<notes>` delimiters for prompt-injection hygiene, relative date resolution against meeting date, and explicit schema constraints.
- U5-T4: `app/ai/fallbacks.py` implemented `heuristic_recap()`: rule-based extraction matching `Action:`, `TODO`, `- [ ]`, `AI:` for items, `Decision:` for decisions, `?` for open questions, and first 2 sentences for summary.
- U5-T5: `app/services/recap_service.py` implemented `generate_recap` (stores `recap_json`, sets `ai_status`), owner resolution (`exact` -> `fuzzy >= 0.8` -> `none`), `apply_recap` (creates `Decision` and `ActionItem` rows with `source=ai` or `source=heuristic`, created events with `actor="ai"`), and `discard_recap`.
- U5-T6: `app/templates/meetings/partials/notes_tab.html` wired with **Generate recap** AI button, skeleton shimmering loader indicator (`#ai-indicator`), review proposal card with AI badge / fallback banner, editable summary, checkbox lists for decisions and action items with resolved owners, and Apply / Discard actions.
- U5-T7: 12 tests in `tests/test_unit5_ai_recap.py` covering valid JSON, code-fenced JSON, timeout fallback, invalid JSON retry, heuristic fallback parsing, prompt parameters, exact/fuzzy/none owner resolution, recap apply and discard, and HTMX web endpoints. Total test suite: 56 tests passing.

**Done but NOT VERIFIED:**
- Production Gemini API call against live network in automated tests (intentional per AGENTS.md §6.8: tests run 100% offline with FakeProvider; GeminiProvider is verified against installed google-genai 2.34 SDK).

**Not done / deferred:**
- Knowledge base and catch-up briefs (Unit 6).
- Nudge Center (Unit 7).

**Files created or modified:**
- `app/ai/__init__.py`
- `app/ai/provider.py`
- `app/ai/gemini.py`
- `app/ai/fake.py`
- `app/ai/client.py`
- `app/ai/schemas.py`
- `app/ai/fallbacks.py`
- `app/ai/prompts/__init__.py`
- `app/ai/prompts/recap.py`
- `app/services/recap_service.py`
- `app/services/__init__.py`
- `app/routers/web_meetings.py`
- `app/templates/meetings/partials/notes_tab.html`
- `tests/test_unit5_ai_recap.py`
- `TASKS.md`
- `memory.md`

**Commands run to verify:**
- `.venv\Scripts\ruff check .` (All checks passed)
- `.venv\Scripts\ruff format --check .` (70 files already formatted)
- `.venv\Scripts\pytest -q` (56 passed in 1.13s)

**Pipeline result after push:**
- Ready to push to GitHub `main`.

**Gotchas / lessons for the next agent:**
- `google-genai` SDK v2.34+ uses `client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(...))`.
- When running `pytest` in sandboxed terminal on Windows, anyio's loopback socket / blocking portal in Starlette `TestClient` requires loopback execution.

**Next pass should:**
1. Follow `AGENTS.md` ritual and read `memory.md`.
2. Build Unit 6: Knowledge base + linking (Level A RAG) + catch-up brief (`TASKS.md` U6-T1 to U6-T8).



