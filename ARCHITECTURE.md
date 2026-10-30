# ARCHITECTURE.md — LoopClose

> **Audience:** any AI coding agent (or human) picking up this project mid-way.
> **Authority:** This file is the source of truth for *technology, structure, data model, APIs, AI design, logging and DevOps*. For product behaviour see `PRD.md`; for visuals see `design.md`; for rules see `AGENTS.md`; for progress see `TASKS.md` and `memory.md`.
> **Project codename:** LoopClose ("close the loop on every open item"). The name can be changed later; do not rename it in code without a human instruction.

---

## 1. Purpose and scope

LoopClose is a small AI-powered web app that:

1. Captures **meetings and work handovers** (agenda, participants, notes, decisions, action items).
2. Uses AI to convert **raw unstructured notes** into a structured recap (summary, decisions, action items, owners, due dates).
3. Tracks every **action item** (owner, due date, status, outcome) until closed, with a full **history**.
4. **Carries open items forward** to the next meeting / handover without losing history.
5. Generates a **catch-up brief** for anyone who missed a meeting or is taking over work.
6. Maintains a small **knowledge base (KB)** and links items to it using AI (**RAG**).
7. Ships with **structured logging** and a **CI/CD + security pipeline** (GitHub Actions, CodeQL, Gitleaks) that deploys to a single free host.
8. Has one **special feature**: the **Nudge Center** (stall detection + AI-drafted follow-ups).

Hard constraints: built in ~3.5 hours in "units" (see `TASKS.md`), deployed for free on **one platform** (frontend + backend + database together).

---

## 2. System overview

```
                      git push
  Developer ───────────────────────────►  GitHub repository
                                              │
                                              ▼
                              GitHub Actions workflow "CI-CD"
        ┌──────────────┬───────────────┬──────────────┬───────────────┐
        │ Gitleaks     │ CodeQL        │ Lint + Test  │ Docker build  │
        │ (secrets)    │ (SAST)        │ (ruff,pytest)│ (verify image)│
        └──────┬───────┴───────┬───────┴──────┬───────┴───────┬───────┘
               └───────────────┴──── all green (main only) ───┘
                                      │
                                      ▼
                         Deploy job: POST Render Deploy Hook
                                      │
                                      ▼
   ┌─────────────────────────  RENDER (single platform, free tier)  ─────────────────────────┐
   │                                                                                           │
   │   Web Service (Docker)                                   Render Postgres (free)           │
   │   ┌───────────────────────────────────────────┐          ┌───────────────────────┐       │
   │   │ FastAPI app (uvicorn, 1 worker)           │          │ people, meetings,     │       │
   │   │  ├─ Web routes: Jinja2 + HTMX (HTML)      │◄────────►│ action_items, events, │       │
   │   │  ├─ JSON API  /api/v1  (+ /docs)          │ SQLAlchemy│ kb_documents, chunks, │       │
   │   │  ├─ Services (business logic)             │          │ kb_links, briefs ...  │       │
   │   │  ├─ AI layer (provider, retry, fallback)  │          └───────────────────────┘       │
   │   │  ├─ KB / RAG layer (retrieval)            │                                           │
   │   │  └─ Logging (JSON → file + stdout)        │                                           │
   │   └───────────────┬───────────────────────────┘                                           │
   └───────────────────┼───────────────────────────────────────────────────────────────────────┘
                       │ HTTPS (outbound)
                       ▼
              Gemini API (LLM + embeddings)  — free tier, key in env var only
```

Key architectural decisions (and why):

| Decision | Reason |
|---|---|
| **Single deployable** (FastAPI serves HTML + JSON) | Requirement: whole app on one free platform. No CORS, no second deploy, fastest to build. |
| **Server-rendered UI (Jinja2 + HTMX)** | No JS build step; HTMX gives partial updates and "AI is thinking" states with almost no JS. |
| **Service layer between routes and DB** | Routes stay thin; same logic is used by HTML routes, JSON API, seed script and tests. |
| **AI behind one interface with retry + fallback** | Assessment demands reliability and graceful failure handling. |
| **Retrieval behind one function `find_related()`** | Lets us ship simple LLM-based linking first and upgrade to embeddings RAG without touching callers. |
| **Postgres in prod, SQLite locally** | Render free disks are ephemeral, so SQLite would lose data on redeploy. SQLAlchemy keeps code identical. |
| **`create_all()` on startup instead of Alembic** | Time-boxed project; documented as a known limitation. |

---

## 3. Technology stack and specifications

> Versions: use the **latest stable release available at install time**, then **pin exact versions in `requirements.txt`** and record them in `memory.md`. Do not guess version numbers from memory; run `pip index versions <pkg>` or install and `pip freeze`.

| Layer | Technology | Specification / notes |
|---|---|---|
| Language | **Python 3.12** | Type hints everywhere. `from __future__ import annotations` allowed. |
| Web framework | **FastAPI** + **Uvicorn** | ASGI, 1 worker in prod (512 MB free instance). Auto docs at `/docs`. |
| Templating | **Jinja2** (via `Jinja2Templates`) | Autoescape ON (never disable). Partials in `templates/partials/`. |
| Frontend interactivity | **HTMX 2.x** | Pinned version from jsDelivr (or vendored in `static/vendor/`). No other JS framework. Small `app.js` only for toasts / tabs. |
| Styling | **Hand-written CSS** (`static/css/app.css`) | CSS variables from `design.md`. No Tailwind, no build tooling. |
| ORM | **SQLAlchemy 2.x** (typed, `Mapped[]` style, sync sessions) | Sync is fine and simpler; FastAPI runs sync routes in a threadpool. |
| DB (prod) | **PostgreSQL** (Render free managed DB) | Driver: **psycopg 3** (`psycopg[binary]`). URL scheme must be `postgresql+psycopg://`. |
| DB (local/tests) | **SQLite** file | `sqlite:///./local.db`; tests use a temp SQLite DB. |
| Validation | **Pydantic v2** + **pydantic-settings** | Request schemas, LLM-output schemas, settings from env. |
| Forms | **python-multipart** | Needed for HTML form posts. |
| HTTP client | **httpx** | Used by tests and (if no SDK) for LLM REST calls. |
| LLM provider (default) | **Google Gemini** via `google-genai` SDK | Free tier. Model name from env `GEMINI_MODEL` (verify the current free model name in Google AI Studio docs; do not hard-code). |
| Embeddings (Unit 9) | **Gemini embedding model** | Env `EMBEDDING_MODEL`. Called via same provider. |
| Fake provider | `LLM_PROVIDER=fake` | Deterministic canned outputs; used in tests/CI and when no API key is set. |
| Vector math (Unit 9) | **numpy** | Cosine similarity over embeddings stored as JSON arrays. No vector DB needed at this scale. |
| Logging | **stdlib `logging`** + custom JSON formatter | `contextvars` for request ID. `RotatingFileHandler`. No third-party logging lib required. |
| Testing | **pytest**, **httpx/TestClient** | AI is always mocked with the fake provider. |
| Lint/format | **ruff** (`ruff check`, `ruff format`) | Config in `pyproject.toml`. CI fails on violations. |
| Container | **Docker** (python:3.12-slim) | Non-root user, `$PORT` aware. |
| Hosting | **Render** (free web service + free Postgres), defined in `render.yaml` | One platform for app + DB. |
| CI/CD | **GitHub Actions** | Triggers on every push. See Section 14. |
| SAST | **CodeQL** (`github/codeql-action`) | Language: python. **Requires a public repo** (code scanning is free only for public repos on personal accounts). |
| Secret scanning | **Gitleaks** (`gitleaks/gitleaks-action`) | Scans full history on each run. Optional local pre-commit hook. |

**Explicitly NOT used (do not add without a human decision):** React/Vue/Next, Tailwind build, Celery/Redis, Kubernetes, Alembic, vector databases (pgvector/Chroma/FAISS), LangChain/LlamaIndex, authentication frameworks.

---

## 4. Repository structure

```
loopclose/
├── AGENTS.md            # rules for AI agents
├── TASKS.md             # unit-by-unit checklist
├── PRD.md               # product requirements
├── ARCHITECTURE.md      # this file
├── design.md            # UI/UX spec
├── memory.md            # agent handover log (append-only)
├── README.md            # deliverable README (written in Unit 8)
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .gitleaks.toml       # gitleaks allowlist (placeholders only)
├── .env.example         # variable NAMES + dummy values only
├── render.yaml          # Render blueprint (web service + Postgres)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml       # ruff + pytest config
├── .github/
│   └── workflows/
│       └── ci-cd.yml    # the pipeline
├── app/
│   ├── __init__.py
│   ├── main.py              # app factory, router registration, startup (create_all, optional seed)
│   ├── config.py            # Settings (pydantic-settings), DB URL normalisation
│   ├── database.py          # engine, SessionLocal, Base, get_db dependency
│   ├── logging_config.py    # JSON formatter, handlers, redaction filter, request_id contextvar
│   ├── middleware.py        # RequestContextMiddleware (request ID, access log)
│   ├── errors.py            # custom exceptions + global handlers (HTML + JSON)
│   ├── enums.py             # all enums (single place)
│   ├── models/              # SQLAlchemy models (one file per aggregate)
│   │   ├── person.py  meeting.py  action_item.py  decision.py
│   │   ├── kb.py (documents, chunks, links)  brief.py  nudge.py
│   ├── schemas/             # Pydantic request/response + AI output schemas
│   ├── services/            # business logic (NO FastAPI imports here)
│   │   ├── people_service.py
│   │   ├── meeting_service.py        # CRUD, lifecycle, participants, handover reassign
│   │   ├── action_item_service.py    # CRUD, transitions, reassign, close/outcome, events
│   │   ├── carry_forward_service.py
│   │   ├── recap_service.py          # AI recap + apply
│   │   ├── brief_service.py          # catch-up brief
│   │   ├── kb_service.py             # documents, summaries, linking orchestration
│   │   └── nudge_service.py          # special feature
│   ├── ai/
│   │   ├── provider.py       # LLMProvider protocol (generate_json, embed)
│   │   ├── gemini.py         # GeminiProvider
│   │   ├── fake.py           # FakeProvider
│   │   ├── client.py         # AIClient: timeout, retry, JSON validation, logging, error mapping
│   │   ├── fallbacks.py      # heuristic recap, template brief, keyword linker, template nudge
│   │   └── prompts/          # one module per operation (recap, brief, kb_summary, link, nudge, ask)
│   ├── kb/
│   │   ├── chunking.py       # Unit 9
│   │   ├── embeddings.py     # Unit 9
│   │   └── retrieval.py      # Retriever protocol + implementations + find_related()
│   ├── routers/
│   │   ├── web_dashboard.py  web_meetings.py  web_items.py  web_kb.py  web_nudges.py  web_people.py
│   │   ├── api_v1.py         # thin JSON wrappers over services
│   │   └── health.py
│   ├── templates/
│   │   ├── base.html  dashboard.html  error.html
│   │   ├── meetings/ (list, new, detail, _tabs ...)
│   │   ├── items/  kb/  nudges/  people/
│   │   └── partials/ (badges, toasts, item_row, ai_banner, empty_state ...)
│   └── static/
│       ├── css/app.css
│       └── js/app.js
├── scripts/
│   └── seed.py              # demo data (idempotent)
├── tests/
│   ├── conftest.py          # temp DB, TestClient, FakeProvider fixture
│   └── test_*.py
└── logs/                    # runtime log files (gitignored)
```

---

## 5. Configuration (environment variables)

All config is read via `app/config.py` (`Settings`). **Never read `os.environ` elsewhere.** `.env.example` lists names with dummy values; real values live only in the local `.env` (gitignored) and in Render/GitHub secret stores.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | `local` \| `test` \| `production` |
| `APP_NAME` | `LoopClose` | Display name |
| `DATABASE_URL` | `sqlite:///./local.db` | Render injects `postgres://...`; **normalise to `postgresql+psycopg://`** in `config.py` (handle both `postgres://` and `postgresql://`). |
| `LLM_PROVIDER` | `gemini` | `gemini` \| `fake`. If `gemini` and no key → log a WARNING and use `fake`-style fallbacks (app must still boot). |
| `GEMINI_API_KEY` | *(none)* | Secret. Never logged. |
| `GEMINI_MODEL` | *(set in .env)* | Chat/JSON model name. |
| `EMBEDDING_MODEL` | *(set in .env)* | Used in Unit 9. |
| `AI_TIMEOUT_SECONDS` | `25` | Per call timeout. |
| `AI_MAX_RETRIES` | `1` | Retries on timeout / 429 / 5xx / invalid JSON. |
| `AI_MAX_INPUT_CHARS` | `12000` | Truncate notes before prompting (log a WARNING when truncated). |
| `RETRIEVER` | `llm` | `llm` (Level A) \| `vector` (Level B, Unit 9). |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FILE` | `logs/app.log` | Rotating file (5 MB × 3 backups). |
| `SEED_DEMO_DATA` | `false` | If `true` and DB empty at startup → run seed. Set `true` on Render for the demo. |
| `PORT` | `8000` | Render sets this automatically. |
| `RENDER_GIT_COMMIT` / `GIT_SHA` | *(none)* | Reported by `/health` so the pipeline can verify the deployed commit. |

GitHub Actions **secrets** (Settings → Secrets and variables → Actions): `RENDER_DEPLOY_HOOK_URL`, `APP_URL` (e.g. `https://loopclose.onrender.com`). `GITHUB_TOKEN` is automatic.

---

## 6. Layering rules (must be respected)

```
routers (web/api)  →  services  →  models / ai / kb
      ↑ only HTTP concerns      ↑ business rules, transactions, event logging
```

1. **Routers** parse/validate input (Pydantic), call a service, render a template or return JSON. No business rules, no direct SQL.
2. **Services** own business rules, state-machine checks, transactions, history events and domain log events. They never import FastAPI or Jinja.
3. **AI code** is reachable only through `app/ai/client.py` (`AIClient`). Services call `AIClient`, never a vendor SDK directly.
4. **Retrieval** is reachable only through `app/kb/retrieval.py::find_related`.
5. **Models** contain no logic beyond simple properties (e.g. `is_overdue`).
6. Every service method that mutates state writes an `action_item_events` row (for items) and emits a structured log event.

---

## 7. Data model

All tables have `id` (integer PK, autoincrement) and `created_at` (UTC, default now) unless stated. `updated_at` on mutable aggregates. Use `Mapped[]` typed columns. Enums are stored as strings (`native_enum=False`) so SQLite and Postgres behave the same.

### 7.1 Tables

**people**
| column | type | notes |
|---|---|---|
| name | str(100) | required |
| email | str(200) | optional, unique if present |
| role_title | str(100) | optional |
| is_active | bool | default true (false = "on leave"/left; still shown on history) |

**meetings** (a *meeting* or a *work handover*; one table, `kind` distinguishes)
| column | type | notes |
|---|---|---|
| kind | enum `MeetingKind` | `meeting` \| `handover` |
| title | str(200) | required, ≥3 chars |
| status | enum `MeetingStatus` | default `planned` |
| scheduled_at | datetime | required |
| agenda | text | optional, ≤5,000 chars |
| raw_notes | text | optional, ≤50,000 chars |
| summary | text | optional (AI or manual) |
| ai_status | enum `AiStatus` | `none` \| `ok` \| `fallback` \| `failed` |
| ai_error | str(300) | short human-readable reason, never a stack trace |
| recap_json | JSON | last AI recap *proposal* (before apply) |
| previous_meeting_id | FK meetings.id | nullable; series link / carry-forward source |
| handover_from_id | FK people.id | nullable; required when `kind=handover` |
| handover_to_id | FK people.id | nullable; required when `kind=handover`, must differ from `from` |
| closed_at | datetime | nullable |

**meeting_participants** — `meeting_id` FK, `person_id` FK, `attendance` enum `Attendance` (`invited`, `attended`, `absent`, `no_response`, `declined`). Unique `(meeting_id, person_id)`.

**decisions** — `meeting_id` FK (cascade), `text` str(1000), `source` enum `ItemSource` (`manual`|`ai`).

**action_items**
| column | type | notes |
|---|---|---|
| title | str(200) | required, ≥3 chars |
| description | text | optional |
| origin_meeting_id | FK meetings.id | required; where it was first raised (never changes) |
| current_meeting_id | FK meetings.id | nullable; whose agenda it is on now (changes on carry-forward) |
| owner_id | FK people.id | nullable (unassigned allowed but flagged) |
| due_date | date | nullable |
| priority | enum `Priority` | `low`\|`medium`\|`high`, default `medium` |
| status | enum `ActionStatus` | `open`\|`in_progress`\|`blocked`\|`done`\|`dropped` |
| blocked_reason | str(300) | required when status=`blocked` |
| outcome_type | enum `OutcomeType` | nullable until closed |
| outcome_note | text | required (≥5 chars) when closed |
| source | enum `ItemSource` | `manual`\|`ai`\|`heuristic` |
| carried_count | int | default 0, incremented on each carry-forward |
| closed_at | datetime | nullable |

**action_item_events** (append-only history; never updated or deleted)
| column | type | notes |
|---|---|---|
| action_item_id | FK | indexed |
| event_type | enum `EventType` | see 8.2 |
| actor | str(50) | `user` \| `ai` \| `system` (no auth in this app) |
| from_value / to_value | str(200) | e.g. owner names, statuses, meeting ids |
| meeting_id | FK | nullable context |
| note | text | optional |
| request_id | str(32) | correlation ID of the request that caused it |

**kb_documents** — `title` str(200), `source_type` enum `KBSource` (`note`, `document`, `chat`, `email`, `transcript`, `meeting`), `content` text (≤100,000 chars), `summary` text (AI or fallback), `tags` JSON list[str], `meeting_id` FK nullable (set for auto-indexed meeting docs; at most one doc per meeting), `index_status` enum `IndexStatus` (`pending`, `indexed`, `failed`, `not_applicable`), `updated_at`.

**kb_chunks** *(Unit 9)* — `document_id` FK (cascade), `chunk_index` int, `text` text, `embedding` JSON (list[float]) nullable, `embedding_model` str nullable. Unique `(document_id, chunk_index)`.

**kb_links** — `entity_type` enum `EntityType` (`action_item`|`decision`|`meeting`), `entity_id` int, `document_id` FK, `chunk_id` FK nullable, `score` float (0–1), `reason` str(300), `method` enum `LinkMethod` (`llm`|`vector`|`keyword`|`manual`). Unique `(entity_type, entity_id, document_id)`.

**catchup_briefs** — `meeting_id` FK, `person_id` FK, `content_json` JSON (schema in 10.4), `generated_by` enum `GeneratedBy` (`ai`|`fallback`).

**followup_drafts** *(special feature)* — `action_item_id` FK, `tone` enum `Tone` (`friendly`|`firm`), `body` text, `generated_by` enum `GeneratedBy`.

### 7.2 Indexes
`action_items(status, due_date)`, `action_items(owner_id)`, `action_items(current_meeting_id)`, `action_item_events(action_item_id, created_at)`, `meeting_participants(person_id)`, `kb_links(entity_type, entity_id)`.

### 7.3 Computed properties
- `ActionItem.is_overdue` = `due_date < today AND status in (open, in_progress, blocked)`
- `ActionItem.is_open` = status in (`open`, `in_progress`, `blocked`)
- Nudge **risk level** (rules, deterministic): see 12.

---

## 8. State machines and history events

### 8.1 Meeting status
```
planned ──► held ──► closed
   │          │
   └──► cancelled ◄┘      (cancelled and closed are terminal)
```
- `held → closed` allowed any time; open items are **not** auto-closed. The UI then prompts for carry-forward.
- Notes/agenda editable while `planned` or `held`; read-only when `closed`/`cancelled`.
- AI recap allowed when status in (`planned`, `held`) and `len(raw_notes) ≥ 20`.
- Invalid transition → `InvalidTransitionError` (HTTP 409 / inline error).

### 8.2 Action item status
```
open ⇄ in_progress ⇄ blocked          (blocked requires blocked_reason)
  └────────┬────────────┘
           ▼
  close(outcome_type, outcome_note)  ──►  done | dropped
  reopen: done | dropped ──► open
```
- `POST /items/{id}/close` is the **only** way to reach `done`/`dropped`; it requires `outcome_type` and `outcome_note` (≥5 chars). This satisfies "record the outcome of each item".
- `outcome_type → status` mapping (final): `completed` → `done`, `partially_completed` → `done`, `dropped` → `dropped`, `superseded` → `dropped`.
- On **reopen**, the item's `status` returns to `open` and `closed_at`, `outcome_type`, `outcome_note` are cleared on the row; the previous outcome is preserved in the `reopened` history event (`note` field) so history is never lost.

### 8.3 `EventType` values
`created`, `updated`, `reassigned`, `status_changed`, `due_date_changed`, `carried_forward`, `blocked`, `closed`, `reopened`, `outcome_recorded`, `kb_linked`, `nudged`.

Every one of these also emits a log event named `item.<event_type>` (see Section 12).

---

## 9. Routes

HTML routes return a **full page** normally, and a **partial** when the request has header `HX-Request: true` (HTMX). Routes live in `app/routers/web_*.py`. JSON equivalents (thin wrappers) live in `api_v1.py` under `/api/v1` and are *lower priority than the HTML UI*; implement them alongside each unit if time allows and log skipped ones in `memory.md`.

### 9.1 Web routes
| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Dashboard: my open items, overdue, upcoming meetings, recent decisions, nudge count |
| GET | `/people` · POST `/people` | List / create people |
| GET | `/meetings` | List with filters (kind, status) |
| GET | `/meetings/new` · POST `/meetings` | Create meeting / handover (+ participants, + optional carry-forward from previous) |
| GET | `/meetings/{id}` | Detail with tabs: Overview · Notes & Recap · Items · Brief · Knowledge · History |
| POST | `/meetings/{id}` | Update agenda/title/schedule |
| POST | `/meetings/{id}/status` | Lifecycle transition |
| POST | `/meetings/{id}/participants` | Add/update participant & attendance |
| POST | `/meetings/{id}/notes` | Save raw notes |
| POST | `/meetings/{id}/recap` | **AI**: generate recap proposal (HTMX partial) |
| POST | `/meetings/{id}/recap/apply` | Apply selected proposal rows → creates decisions + items |
| POST | `/meetings/{id}/decisions` · POST `/decisions/{id}/delete` | Manual decision CRUD |
| POST | `/meetings/{id}/carry-forward` | Carry open items to `to_meeting_id` |
| POST | `/meetings/{id}/handover/reassign` | Bulk reassign `from` person's open items to `to` person |
| GET/POST | `/meetings/{id}/brief` | View / **AI**: generate catch-up brief for `person_id` |
| POST | `/meetings/{id}/items` | Create action item |
| GET | `/items` | Filterable list (status, owner, overdue, meeting) |
| GET | `/items/{id}` | Detail + history timeline + linked knowledge |
| POST | `/items/{id}` | Edit title/description/due/priority |
| POST | `/items/{id}/status` | open / in_progress / blocked / reopen |
| POST | `/items/{id}/reassign` | Change owner (event `reassigned`) |
| POST | `/items/{id}/close` | Close with outcome |
| POST | `/items/{id}/suggest-links` | **AI/RAG**: find related KB (HTMX partial) |
| POST | `/links` · POST `/links/{id}/delete` | Manual KB link add/remove |
| GET | `/kb` · GET `/kb/new` · POST `/kb` | List / add document (AI summary + tags on create) |
| GET | `/kb/{id}` | Document + "referenced by" |
| POST | `/kb/{id}/reindex` | Re-summarise / re-embed |
| GET | `/nudges` | **Special feature**: Nudge Center |
| POST | `/nudges/{item_id}/draft` | **AI**: draft follow-up (`tone`) |
| POST | `/nudges/{item_id}/mark-sent` | Record `nudged` event |
| GET/POST | `/ask` | *(Unit 9, optional)* "Ask Team Memory" Q&A with citations |
| GET | `/health` | JSON health (no auth) |

### 9.2 JSON API (`/api/v1`)
`GET/POST /meetings`, `GET /meetings/{id}`, `POST /meetings/{id}/recap`, `GET/POST /action-items`, `GET /action-items/{id}`, `POST /action-items/{id}/close`, `POST /action-items/{id}/reassign`, `GET/POST /kb/documents`, `GET /kb/search?q=`, `POST /meetings/{id}/brief`. Error shape:
```json
{"error": {"code": "validation_error", "message": "Title must be at least 3 characters", "request_id": "a1b2c3...", "details": [{"field": "title", "issue": "too_short"}]}}
```

### 9.3 `/health` response
```json
{"status": "ok", "app": "LoopClose", "env": "production", "commit": "<sha or null>", "db": "ok", "ai": {"provider": "gemini", "configured": true}}
```
`db` is verified with `SELECT 1`. `status` = `degraded` if DB check fails (HTTP 503). AI being unconfigured does **not** fail health (the app degrades gracefully).

---

## 10. AI subsystem

### 10.1 Components
- `LLMProvider` (protocol): `generate_json(system, prompt, schema_hint, timeout) -> str` and `embed(texts) -> list[list[float]]`.
- `GeminiProvider`, `FakeProvider` implement it. Verify the `google-genai` SDK usage against **current official docs** before coding (APIs change).
- `AIClient` (the only thing services use) provides:
  `run_structured(operation: str, system: str, prompt: str, model_cls: type[BaseModel]) -> AIResult[T]`
  which: truncates input → calls provider with timeout → strips code fences → `json.loads` → validates with Pydantic → on failure retries up to `AI_MAX_RETRIES` (with a "return valid JSON only" reminder on JSON errors) → returns `AIResult(ok, data, error_code, latency_ms, attempts)`. **It never raises to the caller for AI problems**; callers inspect `ok` and use a fallback.
- `fallbacks.py`: deterministic degraded behaviour for each operation (see 10.3).

### 10.2 Operations
| Operation key | Input | Output model | Used by |
|---|---|---|---|
| `recap` | agenda + raw notes + participant names + meeting date | `RecapResult` | recap_service |
| `brief` | structured context (meeting summary, decisions, person's items, history deltas, related KB) | `BriefResult` | brief_service |
| `kb_summarize` | document text | `{summary, tags[]}` | kb_service |
| `link` | entity text + KB catalogue (id, title, summary) | `{matches:[{document_id, relevance, reason}]}` | retrieval (Level A) |
| `nudge` | item context + tone | `{subject?, message}` | nudge_service |
| `ask` *(U9)* | question + retrieved chunks | `{answer, citations:[{document_id, chunk_index}]}` | ask |
| `embed` *(U9)* | texts | vectors | kb/embeddings |

### 10.3 Failure handling per operation (mandatory)
| Operation | Fallback when AI fails or key missing | UI behaviour |
|---|---|---|
| `recap` | **Heuristic recap**: lines starting with `Action:`, `TODO`, `- [ ]`, `AI:` become items (no owner/due); lines starting with `Decision:` become decisions; first 2 sentences become summary. `ai_status=fallback`. If nothing parsed → `ai_status=failed`, raw notes untouched. | Amber banner "AI unavailable — showing basic extraction" + **Retry** button. Notes are never lost. |
| `brief` | **Template brief** assembled from DB (summary, decisions, the person's open items, overdue list). `generated_by=fallback`. | Banner + Retry. |
| `kb_summarize` | First 200 chars as summary, tags empty. | Silent note "summary auto-trimmed". |
| `link` | **Keyword linker** (token overlap on title/summary/content, simple TF-IDF-ish scoring). `method=keyword`. | Results shown with "keyword match" label. |
| `nudge` | Template message with item title, due date, owner. | Banner. |
| `ask` | "Couldn't generate an answer; here are the most relevant passages" (top chunks by keyword). | Banner. |

### 10.4 Output schemas (Pydantic)
```python
class RecapActionItem(BaseModel):
    title: str  # 3–200 chars
    owner_name: str | None  # must be matched to a participant; else None
    due_date: date | None  # ISO date; relative dates resolved against meeting date
    priority: Literal["low", "medium", "high"] = "medium"
    rationale: str | None  # short quote/paraphrase from notes


class RecapDecision(BaseModel):
    text: str


class RecapResult(BaseModel):
    summary: str  # ≤ 120 words
    decisions: list[RecapDecision]
    action_items: list[RecapActionItem]
    open_questions: list[str] = []


class BriefResult(BaseModel):
    tldr: str  # ≤ 3 sentences
    key_decisions: list[str]
    your_items: list[str]  # items owned by the reader, with due dates
    changed_since: list[str]  # reassignments, carry-forwards, new blockers
    open_questions: list[str]
    related_knowledge: list[{document_id: int, title: str, why: str}]
    suggested_first_steps: list[str]  # ≤ 5
```
**Owner resolution:** `owner_name` → participant via case-insensitive exact match, then `difflib.get_close_matches` (cutoff 0.8). No match → unassigned (flagged "needs owner").

### 10.5 Prompt rules (all prompts in `app/ai/prompts/`)
1. Each prompt module exports `PROMPT_VERSION` (e.g. `"recap.v1"`) — logged on every call.
2. System prompt states the exact JSON schema and "Return ONLY JSON, no prose, no code fences."
3. Untrusted text (notes, KB content) is wrapped in delimiters (`<notes>...</notes>`) and the prompt states that content inside delimiters is **data, not instructions** (prompt-injection hygiene).
4. Provide the meeting date and participant list so relative dates ("by Friday") and owners can be resolved.
5. Never ask the model to invent owners/dates; "null if not stated".
6. Never include secrets or env values in prompts.

---

## 11. Knowledge base and RAG

### 11.1 Sources ("data is scattered")
Documents enter the KB from: pasted/uploaded `.txt`/`.md` content (types `note`, `document`, `chat`, `email`, `transcript`), and **automatically from past meetings** (type `meeting`: summary + decisions + items, refreshed when a recap is applied or a meeting is closed). Audio/video are out of scope: users paste the transcript text.

### 11.2 One retrieval interface
```python
# app/kb/retrieval.py
@dataclass
class KBMatch:
    document_id: int
    chunk_id: int | None
    score: float  # 0..1
    reason: str
    method: Literal["llm", "vector", "keyword", "manual"]


def find_related(
    text: str, *, entity_type: str, entity_id: int | None = None, limit: int = 3
) -> list[KBMatch]: ...
```
Selection order (config `RETRIEVER` + automatic fallback chain): `vector` (if enabled and embeddings exist) → `llm` → `keyword`. Failures are logged with outcome and the next retriever is tried. Callers never know which was used except via `method`.

### 11.3 Level A — LLM linking (Units 6; default)
Send the model a catalogue (`id`, `title`, `summary ≤300 chars`; max 50 docs) and the entity text. Validate returned `document_id`s exist; keep `relevance ≥ 0.5`; max 3. Store in `kb_links` (`method=llm`).

### 11.4 Level B — Vector RAG (Unit 9, optional)
1. **Ingest:** split document into chunks of ~350 words with ~50-word overlap (`kb/chunking.py`), store in `kb_chunks`.
2. **Embed:** `kb/embeddings.py` calls `AIClient.embed` in batches; stores float lists as JSON. On failure `index_status=failed` and retriever falls back.
3. **Retrieve:** embed the query, cosine similarity with numpy across all chunks (fine for ≲5,000 chunks), take top-k (default 4), apply `MIN_SCORE` (configurable; tune against seed data), group by document.
4. **Confirm (optional):** pass top chunks to `link` prompt for a one-line `reason` per match.
5. **Ask Team Memory (`/ask`):** answer questions only from retrieved chunks with citations; if nothing relevant → say so.

### 11.5 Rules
- Every link shows its **source document title** and **method**.
- Links are suggestions; the user can remove them (`manual` links are never auto-removed).
- Re-linking an entity replaces its non-manual links only.

---

## 12. Logging and observability

### 12.1 Setup (`app/logging_config.py`)
- One JSON object per line (JSON Lines). Handlers: **rotating file** (`LOG_FILE`, 5 MB × 3) **and stdout** (Render's log viewer reads stdout; the file is ephemeral on Render, state this in README).
- Levels: `DEBUG` (dev detail), `INFO` (normal events), `WARNING` (degraded/fallback/validation rejects), `ERROR` (unhandled errors, AI hard failures), `CRITICAL` (startup cannot continue).
- **Correlation ID:** `RequestContextMiddleware` reads inbound `X-Request-ID` or generates `uuid4().hex[:16]`, stores it in a `contextvars.ContextVar`, adds it to every log record via a logging filter, and returns it in the `X-Request-ID` response header. Error pages display it.
- **Redaction filter:** masks values for keys matching `key|token|secret|password|authorization|api_key` and any string equal to a configured secret value. Prompts/notes content is **not** logged (log lengths and counts instead). No emails in logs (log person IDs).

### 12.2 Standard fields
`ts` (ISO-8601 UTC), `level`, `logger`, `event`, `request_id`, plus event-specific fields. Example lines:
```json
{"ts":"2026-10-30T09:15:02.113Z","level":"INFO","logger":"app.http","event":"http.request","request_id":"9f2c1a7d3b4e5f60","method":"POST","path":"/meetings/4/recap","status":200,"duration_ms":2341}
{"ts":"2026-10-30T09:15:02.101Z","level":"INFO","logger":"app.ai","event":"ai.call","request_id":"9f2c1a7d3b4e5f60","operation":"recap","provider":"gemini","model":"<model>","prompt_version":"recap.v1","latency_ms":2210,"attempts":1,"outcome":"success","input_chars":3120,"output_chars":1480}
{"ts":"2026-10-30T09:16:10.882Z","level":"INFO","logger":"app.items","event":"item.closed","request_id":"c01d...","item_id":12,"outcome_type":"completed","meeting_id":4}
{"ts":"2026-10-30T09:17:44.310Z","level":"WARNING","logger":"app.ai","event":"ai.fallback","request_id":"77ab...","operation":"brief","reason":"timeout","fallback":"template"}
```

### 12.3 Event catalogue (minimum)
| Group | Events |
|---|---|
| HTTP | `http.request` (method, path, status, duration_ms), `http.error` |
| Meetings | `meeting.created`, `meeting.updated`, `meeting.status_changed`, `meeting.participant_added`, `meeting.notes_saved`, `meeting.carry_forward` (count), `meeting.handover_reassign` (count) |
| Items | `item.created`, `item.updated`, `item.reassigned` (from_owner_id,to_owner_id), `item.status_changed`, `item.blocked`, `item.closed` (outcome_type), `item.reopened`, `item.carried_forward`, `item.nudged` |
| AI | `ai.call` (operation, provider, model, prompt_version, latency_ms, attempts, outcome=`success`\|`retry_success`\|`fallback`\|`error`, error_code, input_chars, output_chars), `ai.fallback`, `ai.truncated_input` |
| KB | `kb.document_created`, `kb.summarized`, `kb.indexed` (chunks), `kb.link_created`, `kb.retrieval` (retriever, matches, latency_ms) |
| System | `app.startup` (env, db_dialect, ai_provider configured yes/no — never the key), `app.seeded`, `app.error` (exception type, message, stack in `exc_info` at ERROR) |

### 12.4 Errors with context
Unhandled exceptions are logged at ERROR with `exc_info`, `request_id`, route, and relevant IDs, then rendered as a friendly error page/JSON with the request ID.

---

## 13. Validation, errors, security

**Validation (Pydantic + service rules)** — see `PRD.md` §8 for the full rule list. Key ones: title 3–200 chars; due date cannot be set in the past on creation; owner must exist and be active; handover requires distinct from/to people; outcome required to close; blocked requires reason; notes length caps; enum values validated; HTML form errors are returned inline per field (HTTP 422 for API, re-rendered form with messages for HTML).

**Exceptions** (`app/errors.py`): `NotFoundError` (404), `ValidationFailed` (422), `InvalidTransitionError` (409), `AIUnavailableError` (internal only; never surfaces as 500 — becomes fallback). Global handlers return HTML (error page, or HTMX toast partial) or JSON based on `Accept`/path.

**Security basics**
- No secrets in code, logs, templates, prompts, or git history (enforced by Gitleaks in CI).
- Jinja autoescape on; never mark user content `|safe`.
- SQLAlchemy parameterised queries only (no string-built SQL) — CodeQL checks this too.
- Container runs as non-root. Dependencies pinned.
- **No authentication** (assumption; see PRD). "actor" in events is `user`/`ai`/`system`. Listed under known limitations.

---

## 14. DevOps: CI/CD, security scanning, deployment

### 14.1 How the pipeline works (end to end)
1. Dev runs `git push` (any branch). GitHub fires the `push` event and starts workflow **CI-CD** (`.github/workflows/ci-cd.yml`) automatically. Pull requests into `main` also trigger it.
2. Jobs run in **parallel** where independent:
   - **gitleaks** — checks out *full history* (`fetch-depth: 0`) and scans for committed secrets (API keys, tokens). Any finding fails the job.
   - **codeql** — builds the CodeQL database for Python and runs the security queries; results appear under the repo's **Security → Code scanning** tab; failure of the job blocks deploy.
   - **test** — installs deps, `ruff check`, `ruff format --check`, `pytest` (AI mocked via `FakeProvider`, SQLite temp DB).
   - **docker** (after `test`) — builds the Docker image (no push) to prove the container builds.
3. **deploy** job runs **only** on pushes to `main` **and only if all four jobs succeeded** (`needs:`). It calls the **Render Deploy Hook** (a secret URL) → Render pulls the commit, builds the Docker image and rolls out.
4. **Smoke test** (same job) polls `GET $APP_URL/health` until the JSON `commit` equals the pushed `github.sha` (proves the *new* version is live, not the old one still serving) or times out after ~6 minutes → job fails loudly.
5. Concurrency control cancels superseded runs on the same ref.

```
push ─► [gitleaks] ┐
        [codeql  ] ├──► all green + branch==main ─► [deploy: hook ─► smoke test /health commit==sha]
        [test ──► docker] ┘
```

### 14.2 Reference workflow `.github/workflows/ci-cd.yml`
> Action major versions below were current when this was written. If a tag fails to resolve, use the latest available major and log it in `memory.md`.

```yaml
name: CI-CD

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  gitleaks:
    name: Secret scan (Gitleaks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  codeql:
    name: SAST (CodeQL)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
      actions: read
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v4
        with:
          languages: python
          queries: security-extended
      - uses: github/codeql-action/analyze@v4
        with:
          category: "/language:python"

  test:
    name: Lint and test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Ruff lint
        run: ruff check .
      - name: Ruff format check
        run: ruff format --check .
      - name: Pytest
        env:
          APP_ENV: test
          LLM_PROVIDER: fake
          DATABASE_URL: sqlite:///./test.db
        run: pytest -q

  docker:
    name: Docker build
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: loopclose:ci
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy to Render
    runs-on: ubuntu-latest
    needs: [gitleaks, codeql, test, docker]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - name: Trigger Render deploy hook
        env:
          RENDER_DEPLOY_HOOK_URL: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}
        run: |
          test -n "$RENDER_DEPLOY_HOOK_URL" || { echo "RENDER_DEPLOY_HOOK_URL secret missing"; exit 1; }
          curl --fail --silent --show-error -X POST "$RENDER_DEPLOY_HOOK_URL" > /dev/null
          echo "Deploy triggered for ${{ github.sha }}"
      - name: Smoke test (wait for new commit)
        env:
          APP_URL: ${{ secrets.APP_URL }}
        run: |
          for i in $(seq 1 36); do
            body=$(curl -s --max-time 30 "$APP_URL/health" || true)
            commit=$(echo "$body" | jq -r '.commit // empty' 2>/dev/null || true)
            echo "attempt $i: commit=${commit:-none}"
            if [ "$commit" = "${{ github.sha }}" ]; then echo "Deployed OK"; exit 0; fi
            sleep 10
          done
          echo "Deployment not confirmed in time"; exit 1
```
Notes: (a) Gitleaks action works free for personal-account repos; organisation repos need a `GITLEAKS_LICENSE` secret. (b) CodeQL needs a **public** repo (or GitHub Advanced Security). (c) The smoke test relies on `/health` returning `commit` from `RENDER_GIT_COMMIT` (Render sets it); if absent in the runtime, set `GIT_SHA` via the Dockerfile `ARG` and adjust the check, then record it in `memory.md`.

### 14.3 `.gitleaks.toml`
```toml
title = "LoopClose gitleaks config"
[extend]
useDefault = true
[allowlist]
description = "Placeholders only"
paths = ['''\.env\.example$''', '''tests/''']
```
Optional local guard: `pre-commit` hook running `gitleaks protect --staged` (documented in README; not required by CI).

### 14.4 Dockerfile (spec)
- Base `python:3.12-slim`; `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`.
- Install `requirements.txt` first (layer caching), then copy `app/`, `scripts/`.
- Create and switch to non-root user; `mkdir logs` owned by that user.
- `CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]` (1 worker).
- `HEALTHCHECK` hitting `/health` (optional).
- `.dockerignore`: `.git`, `.env`, `logs`, `*.db`, `__pycache__`, `tests` (optional), `.venv`.

### 14.5 `render.yaml` (blueprint spec)
```yaml
services:
  - type: web
    name: loopclose
    runtime: docker
    plan: free
    autoDeploy: false          # deploys are triggered by the GitHub Actions deploy hook, not by Render itself
    healthCheckPath: /health
    envVars:
      - key: APP_ENV
        value: production
      - key: DATABASE_URL
        fromDatabase:
          name: loopclose-db
          property: connectionString
      - key: LLM_PROVIDER
        value: gemini
      - key: GEMINI_API_KEY
        sync: false            # set manually in Render dashboard
      - key: GEMINI_MODEL
        sync: false
      - key: EMBEDDING_MODEL
        sync: false
      - key: SEED_DEMO_DATA
        value: "true"
databases:
  - name: loopclose-db
    plan: free
```
Free-tier realities (document in README): the web service **sleeps after ~15 min idle** (first request takes ~1 min); the free Postgres **expires after ~30 days**; filesystem is **ephemeral** (log file lost on redeploy; stdout logs remain in Render's log viewer). Verify current limits on Render's docs before submission.

### 14.6 Branching and commits
`main` = deployable. Work on `main` directly is acceptable for this time-boxed project, but **every push must keep CI green**. Conventional commits (`feat:`, `fix:`, `chore:`, `ci:`, `docs:`). One commit per task is ideal; always run `ruff format . && ruff check . && pytest -q` before pushing.

---

## 15. Testing strategy

- `tests/conftest.py`: temp SQLite DB per test session, `TestClient`, fixtures forcing `LLM_PROVIDER=fake`.
- **Must-have tests:** meeting lifecycle transitions (valid/invalid); action item close requires outcome; blocked requires reason; reassign writes event; carry-forward moves open items, increments `carried_count`, writes events, leaves history intact; recap parsing happy path + invalid-JSON retry + fallback heuristic; owner resolution (exact/fuzzy/none); `find_related` fallback chain; `/health`; request-ID header present; log redaction masks secrets.
- No test may call a real LLM or the network.

---

## 16. Free-tier and performance constraints

- 512 MB RAM / 0.1 CPU on Render free: **no local ML models**, 1 uvicorn worker, avoid loading large libs at import time.
- Keep AI timeouts ≤ 25 s; long AI actions return an HTMX "working…" state, not a blocking page.
- Keep prompts small (`AI_MAX_INPUT_CHARS`); catalogue capped at 50 docs.
- Cold start: seeding must be fast (< 3 s) and idempotent.

---

## 17. Known limitations (to repeat in README)

No authentication/authorisation; no email/calendar/chat integrations (data is entered manually/pasted); no audio transcription; no Alembic migrations; free-tier sleep and DB expiry; log file ephemeral on Render; AI quality depends on a free-tier model; single-tenant.

---

## 18. Source-of-truth precedence

If documents disagree: `PRD.md` (behaviour) > `ARCHITECTURE.md` (tech/structure) > `design.md` (visuals) > `TASKS.md` (planning). **Do not silently pick**: choose the most conservative option, proceed, and record the conflict under "Open Questions" in `memory.md` for the human.
