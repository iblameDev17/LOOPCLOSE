# TASKS.md — LoopClose Development Checklist

> Work is split into **units**. Build **one unit per pass** (see `AGENTS.md`). Tick `[x]` only when a task is fully done and verified. If a task is deferred, leave it unticked and add `(deferred: reason)`.
> Total budget: **~3.5 h (210 min)**. Unit time-boxes below are targets for an AI-assisted build, including human review. Unit 9 is optional and only started if time remains.

| Unit | Name | Target | Depends on |
|---|---|---|---|
| 0 | Human prerequisites | before start | — |
| 1 | Foundation: scaffold, config, DB, logging, base UI | 20 min | 0 |
| 2 | CI/CD pipeline + first deploy | 20 min | 1 |
| 3 | Core domain: people, meetings & handovers | 30 min | 1 |
| 4 | Action items, history, carry-forward | 30 min | 3 |
| 5 | AI foundation + recap | 35 min | 3, 4 |
| 6 | KB + linking (Level A) + catch-up brief | 30 min | 5 |
| 7 | Special feature: Nudge Center | 20 min | 4, 5 |
| 8 | Seed data, README, polish, final deploy | 20 min | all |
| 9 | *(Optional)* Vector RAG + "Ask Team Memory" | 30+ min | 6 |

**Recommended order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (→ 9 if time). Unit 2 comes early on purpose: get a deployed skeleton and green pipeline before building features, so every later push deploys automatically.

---

## Unit 0 — Human prerequisites (Dev does these; the AI cannot)

- [ ] Create a **public** GitHub repository (CodeQL code scanning is free only for public repos). Clone locally.
- [ ] Create the folder structure and paste the six docs (`AGENTS.md`, `TASKS.md`, `PRD.md`, `ARCHITECTURE.md`, `design.md`, `memory.md`) at the repo root.
- [ ] Create a **Render** account (no card needed for free tier). Do not create services manually yet if using the blueprint (Unit 2).
- [ ] Get a **Gemini API key** (Google AI Studio). Note the current free model name for `GEMINI_MODEL` and an embedding model name for `EMBEDDING_MODEL`.
- [ ] Locally: Python 3.12, Git, Docker (optional but useful), Node not needed.
- [ ] Put the key only in a local `.env` (never commit).
- [ ] Decide the repo name/Render service name (default `loopclose`).

---

## Unit 1 — Foundation (scaffold, config, DB, logging, base UI)

**Goal:** a running FastAPI app with config, DB connection, structured logging with request IDs, error handling skeleton, health endpoint and the base layout/CSS from `design.md`.

**Depends on:** Unit 0 · **Read:** `ARCHITECTURE.md` §3–6, §12–13; `design.md` §2–4, §9.

Tasks:
- [x] **U1-T1** Create folder structure per `ARCHITECTURE.md` §4 (empty packages with `__init__.py`).
- [x] **U1-T2** `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` (ruff + pytest config), `.gitignore`, `.dockerignore`, `.env.example`. Install deps, **pin exact versions**.
- [x] **U1-T3** `app/config.py`: `Settings` via pydantic-settings; normalise `DATABASE_URL` (`postgres://`/`postgresql://` → `postgresql+psycopg://`); never log secrets.
- [x] **U1-T4** `app/database.py`: engine, `SessionLocal`, `Base`, `get_db` dependency; SQLite connect args handled.
- [x] **U1-T5** `app/enums.py`: all enums from `ARCHITECTURE.md` §7–8.
- [x] **U1-T6** `app/logging_config.py`: JSON formatter, rotating file handler + stdout handler, `request_id` ContextVar + filter, redaction filter, `log_event()` helper.
- [x] **U1-T7** `app/middleware.py`: request-ID middleware (accept/generate, set header), `http.request` access log with duration.
- [x] **U1-T8** `app/errors.py`: custom exceptions + global handlers (HTML error page / HTMX toast / JSON error shape) including request ID display.
- [x] **U1-T9** `app/main.py`: app factory, static mount, template setup, router registration, startup (`create_all`, `app.startup` log event, optional seed hook behind `SEED_DEMO_DATA`).
- [x] **U1-T10** `app/routers/health.py`: `/health` per `ARCHITECTURE.md` §9.3 (including `commit` from `RENDER_GIT_COMMIT`/`GIT_SHA`).
- [x] **U1-T11** `templates/base.html` (nav, "Viewing as" placeholder, footer w/ request ID, SVG icon sprite, toast container), `static/css/app.css` implementing **all tokens and base components** (buttons, forms, cards, badges, tables, tabs, timeline, banners, skeleton, empty state), `static/js/app.js` (toasts, copy, tabs). Placeholder dashboard page.
- [x] **U1-T12** Tests: `/health` OK, request-ID header present and echoed, redaction filter masks secrets, config URL normalisation.

**Acceptance:** `uvicorn app.main:app` runs; `/` renders styled layout in light and dark; `/health` returns JSON with `db: ok`; each request yields a JSON log line in `logs/app.log` with `request_id`; a forced error shows the friendly error page with request ID; `ruff` + `pytest` pass.

---

## Unit 2 — CI/CD pipeline + first deploy (DevOps)

**Goal:** every `git push` triggers Gitleaks + CodeQL + lint/tests + Docker build; pushes to `main` deploy to Render and are smoke-tested.

**Depends on:** Unit 1 · **Read:** `ARCHITECTURE.md` §14.

Tasks:
- [ ] **U2-T1** `Dockerfile` + `.dockerignore` per §14.4 (non-root, `$PORT`, 1 worker, logs dir). Verify `docker build` + run locally if Docker available.
- [ ] **U2-T2** `.github/workflows/ci-cd.yml` per §14.2 (jobs: gitleaks, codeql, test, docker, deploy + smoke test; concurrency; least-privilege permissions). Verify action tags resolve; use latest majors if not.
- [ ] **U2-T3** `.gitleaks.toml` per §14.3.
- [ ] **U2-T4** `render.yaml` per §14.5 (web service + free Postgres, `autoDeploy: false`, health check).
- [ ] **U2-T5** Document in `memory.md → Environment & Deployment` the **manual steps for the human**: create Render blueprint from repo; set `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL` in Render; copy the service's **Deploy Hook URL** into GitHub secret `RENDER_DEPLOY_HOOK_URL`; add secret `APP_URL`; confirm repo is public for CodeQL; verify first workflow run.
- [ ] **U2-T6** (Human + AI) Push; confirm all jobs run; confirm deploy triggers and smoke test sees the new commit; record the live URL in `memory.md`.
- [ ] **U2-T7** Optional: `.pre-commit-config.yaml` with gitleaks (local guard); mention in README later.

**Acceptance:** a push shows the workflow starting within seconds; Gitleaks, CodeQL, test and docker jobs green; on `main` the deploy job triggers Render and the smoke test passes (`/health.commit == github.sha`); live URL shows the Unit 1 UI. A deliberately committed fake secret on a throwaway branch is caught by Gitleaks (demo evidence; then remove it from history or use an allowlisted dummy — do **not** leave real-looking secrets in the repo).

---

## Unit 3 — Core domain: people, meetings & handovers

**Goal:** create, view, manage meetings and handovers with agenda, participants, attendance, notes, decisions and lifecycle.

**Depends on:** Unit 1 · **Read:** `PRD.md` §5.1–5.2, §8; `ARCHITECTURE.md` §7–9; `design.md` §5.2–5.4, §5.9.

Tasks:
- [ ] **U3-T1** Models: `Person`, `Meeting`, `MeetingParticipant`, `Decision` (per §7), with relationships and indexes.
- [ ] **U3-T2** Schemas (Pydantic) with validation rules from `PRD.md` §8.
- [ ] **U3-T3** `people_service`, `meeting_service` (create incl. handover rules, update, list/filter, participants & attendance, status transitions per §8.1, notes save, decisions add/delete, handover reassign **stub** that Unit 4 completes). Emit `meeting.*` events.
- [ ] **U3-T4** Web routers + templates: people (list/create), meetings list (filters, open-item count placeholder), new meeting form (incl. handover fields), meeting detail with tabs (Overview, Notes & Recap [notes only], Items [placeholder], Brief [placeholder], Knowledge [placeholder], History [placeholder]), status change control, decisions add/delete, attendance updates.
- [ ] **U3-T5** "Viewing as" selector (cookie) wired into base template.
- [ ] **U3-T6** Inline validation errors on forms (HTMX 422 re-render); 404 handling for unknown IDs; read-only behaviour for closed/cancelled.
- [ ] **U3-T7** Tests: lifecycle valid/invalid transitions, handover validation (from≠to), participant uniqueness, notes length cap, form validation errors.

**Acceptance:** can create a meeting and a handover, add participants with attendance, move `planned → held → closed`, add/delete decisions, save notes; invalid actions show friendly inline errors; logs show `meeting.created`, `meeting.status_changed`, etc. with request IDs.

---

## Unit 4 — Action items, history, carry-forward

**Goal:** full action item lifecycle with owner/due/status/outcome, append-only history, handover reassignment, and carry-forward.

**Depends on:** Unit 3 · **Read:** `PRD.md` §5.3–5.4; `ARCHITECTURE.md` §7–8; `design.md` §4.4–4.7, §5.4–5.6.

Tasks:
- [ ] **U4-T1** Models: `ActionItem`, `ActionItemEvent` (append-only), computed `is_overdue`/`is_open`.
- [ ] **U4-T2** `action_item_service`: create, edit (due date change event), status transitions (blocked needs reason), reassign (event w/ from→to), **close with outcome** (status mapping per §8.2), reopen (preserve outcome in event note), list/filter/sort. Every mutation writes an event **and** a log event.
- [ ] **U4-T3** `carry_forward_service`: carry open/in_progress/blocked items from X to Y; increment `carried_count`; update `current_meeting_id`; write `carried_forward` events; return count. Support "create next meeting with `previous_meeting_id` + auto carry-forward".
- [ ] **U4-T4** Complete handover reassign: bulk reassign `from` person's open items to `to` person.
- [ ] **U4-T5** Routers + templates: Items tab on meeting detail (list + inline add form), global `/items` list with filters, item detail with side card, expanding **Close with outcome** panel, reassign, status controls, **history timeline**, "Carried over" section on meeting Overview, close-meeting carry-forward prompt.
- [ ] **U4-T6** Dashboard cards wired: My open items, Overdue, Needs owner, Upcoming meetings, Recent decisions.
- [ ] **U4-T7** Item row component with priority edge, status/overdue/unassigned/carried badges (per `design.md` §4.4–4.5), avatar.
- [ ] **U4-T8** Tests: close requires outcome; blocked requires reason; reassign writes event; carry-forward semantics (open items only, counts, events, origin unchanged); reopen; overdue computation; due-date-in-past rejected on create.

**Acceptance:** create items in a meeting; change status; reassign; close with outcome (and see validation if missing); close a meeting and carry open items to the next one with "Carried 1×" visible and `carried_forward` in the timeline; handover reassign works; logs show `item.created`, `item.reassigned`, `item.closed`, `item.carried_forward`, `meeting.carry_forward`.

---

## Unit 5 — AI foundation + recap

**Goal:** reliable AI layer (provider, client, retries, validation, fallbacks, logging) and the recap feature end to end.

**Depends on:** Units 3–4 · **Read:** `PRD.md` §5.5, §6; `ARCHITECTURE.md` §10, §12; `design.md` §4.8, §4.10, §5.4.

Tasks:
- [ ] **U5-T1** `app/ai/provider.py` protocol; `gemini.py` (**verify SDK usage against current docs**); `fake.py` (deterministic canned outputs, plus switchable failure modes: timeout, invalid JSON, empty).
- [ ] **U5-T2** `app/ai/client.py` `AIClient.run_structured`: truncate input (`AI_MAX_INPUT_CHARS`, log `ai.truncated_input`), timeout, fence stripping, JSON parse, Pydantic validation, retry policy, `AIResult`, `ai.call` log (latency, attempts, outcome, error_code, input/output chars), no content logged. Missing key → fallback path with a one-time WARNING.
- [ ] **U5-T3** `app/ai/prompts/recap.py` (`PROMPT_VERSION="recap.v1"`; schema in system prompt; delimiters; resolve relative dates using meeting date; participants list; "null if not stated").
- [ ] **U5-T4** `app/ai/fallbacks.py`: heuristic recap (prefix rules `Action:`/`TODO`/`- [ ]`/`AI:` → items; `Decision:` → decisions; first sentences → summary).
- [ ] **U5-T5** `recap_service`: generate (stores `recap_json`, sets `ai_status`/`ai_error`), owner resolution (exact → fuzzy 0.8 → none), apply selected rows (creates `Decision` and `ActionItem` with `source=ai`/`heuristic`, writes `created` events with actor `ai`), stores summary, discard.
- [ ] **U5-T6** UI: Notes & Recap tab — **Generate recap** AI button with skeleton; **review form** per `design.md` §5.4 (editable summary, checkbox rows, owner select preselected, due date, priority); **Apply selected**/**Discard**; AI pills; fallback banner + **Retry**.
- [ ] **U5-T7** Tests: valid JSON happy path; code-fenced JSON; invalid JSON → retry → success; invalid twice → heuristic fallback; timeout → fallback; owner resolution exact/fuzzy/none; relative date prompt contains meeting date; apply creates items + events; no network used.

**Acceptance:** with a key set, pasting messy notes and clicking Generate yields a sensible reviewable proposal; applying creates items with AI badges and `created` history events; with the key removed or `LLM_PROVIDER=fake` failure mode, the UI shows the fallback banner and heuristic output; logs show `ai.call` (latency/outcome) and `ai.fallback`.

---

## Unit 6 — Knowledge base + linking (Level A RAG) + catch-up brief

**Goal:** KB documents with AI summaries, auto-indexed past meetings, `find_related()` with LLM linking and keyword fallback, link management, and catch-up briefs.

**Depends on:** Unit 5 · **Read:** `PRD.md` §5.6–5.7; `ARCHITECTURE.md` §10–11; `design.md` §5.4, §5.5, §5.7.

Tasks:
- [ ] **U6-T1** Models: `KBDocument`, `KBLink` (and `KBChunk` table definition for Unit 9, unused for now), `CatchupBrief`.
- [ ] **U6-T2** `kb_service`: create doc (AI summary + tags via `kb_summarize`, fallback trimmed text), upload `.txt/.md` validation (≤1 MB, UTF-8), list/search, detail, "referenced by", reindex; **auto-index meetings** (type `meeting`) when a recap is applied or a meeting is closed; emit `kb.*` events.
- [ ] **U6-T3** `app/kb/retrieval.py`: `KBMatch`, `find_related()`, `LLMSummaryRetriever` (catalogue ≤50 docs, validate IDs, relevance ≥0.5, max 3), `KeywordRetriever` fallback, fallback chain driven by `RETRIEVER` setting; `kb.retrieval` log with retriever, matches, latency.
- [ ] **U6-T4** Link management: suggest-links endpoints for items/decisions/meetings (HTMX partial with accept/dismiss), manual add/remove, uniqueness; `kb_linked` item event on accept.
- [ ] **U6-T5** UI: `/kb` list, `/kb/new` (paste or upload), `/kb/{id}` detail; Knowledge tab on meetings; Linked knowledge on item detail; method pills (`design.md` §4.4).
- [ ] **U6-T6** `brief_service` + `app/ai/prompts/brief.py` (`brief.v1`): assemble structured context (meeting summary, decisions, the person's items, changes since — reassignments/carry-forwards/blocks, related KB with titles); generate; template fallback; persist `CatchupBrief`; default person logic (absent/no_response/handover `to`).
- [ ] **U6-T7** Brief tab UI: person selector, **Generate brief**, brief card with sections and source links, Copy button, fallback banner + Retry.
- [ ] **U6-T8** Tests: summary fallback; upload validation; `find_related` happy path (fake provider), invalid IDs discarded, fallback chain to keyword; uniqueness of links; brief fallback content; default brief person selection.

**Acceptance:** add a document and see an AI summary + tags; suggest related knowledge for an item and get ≤3 matches with reason/method that can be accepted; briefs for an absentee/handover successor are readable and cite related docs; failures degrade gracefully; logs show `kb.*` and `ai.*` events.

---

## Unit 7 — Special feature: Nudge Center

**Goal:** `/nudges` with transparent risk scoring, AI-drafted follow-ups (friendly/firm), copy and mark-sent.

**Depends on:** Units 4, 5 · **Read:** `PRD.md` §5.8; `design.md` §5.8; `ARCHITECTURE.md` §10.

Tasks:
- [ ] **U7-T1** Model `FollowupDraft`.
- [ ] **U7-T2** `nudge_service`: risk scoring per `PRD.md` §5.8 (pure function, unit-tested), listing grouped by owner, reasons as chips; "no update for 7+ days" uses last event time.
- [ ] **U7-T3** `app/ai/prompts/nudge.py` (`nudge.v1`) + template fallback; draft endpoint with tone; persist draft; include item context (due date, days open, carried count, latest related decision/KB link if any).
- [ ] **U7-T4** Mark-as-sent: writes `nudged` event; show "last nudged" on item detail and in Nudge Center.
- [ ] **U7-T5** UI per `design.md` §5.8: grouped list, risk badges, chips, tone toggle, AI button, draft card with Copy / Mark sent, empty state; nav count pill; dashboard widget.
- [ ] **U7-T6** Tests: scoring matrix (each rule + thresholds), ordering, fallback template, mark-sent event.

**Acceptance:** seeded overdue/blocked/carried items appear ranked with correct reasons; drafting works with AI and with fallback; mark-sent updates history and "last nudged"; logs show `item.nudged` and `ai.call` for `nudge`.

---

## Unit 8 — Seed data, README, polish, final deploy

**Goal:** high-quality demo data, deliverable README, UX/a11y polish, verified deployment.

**Depends on:** Units 1–7 · **Read:** `PRD.md` §10, §12–14; `design.md` §7–8.

Tasks:
- [ ] **U8-T1** `scripts/seed.py` per `PRD.md` §10 (idempotent, relative dates, realistic text, one messy raw-notes blob ready for recap demo, pre-built links/brief/history). `SEED_DEMO_DATA=true` seeds on empty DB at startup. Fast (< 3 s).
- [ ] **U8-T2** UX pass against `design.md`: all badge/empty/loading/error states, responsive check at 375/768/1280 px, dark mode check, focus rings, labels, `aria` attributes, reduced-motion.
- [ ] **U8-T3** Error-handling pass: every route has a friendly 404/422/409 path; AI failure paths demoed once each.
- [ ] **U8-T4** `README.md` with sections: Overview · Live URL · Features · Architecture & approach (short, with the diagram from `ARCHITECTURE.md` §2) · **AI configuration** (provider, model env vars, prompts location, validation/retry/fallbacks, privacy of logs) · **Data source** (synthetic seed + how to add real docs) · **Logging setup** (format, file path/rotation, request IDs, event catalogue, redaction; note file ephemerality on Render) · **Special feature** (Nudge Center and why it adds value) · **DevOps** (pipeline stages, secrets needed, how to read results) · Local setup & run · Testing · **Assumptions** (`PRD.md` §13) · **Known limitations** (`ARCHITECTURE.md` §17) · Demo script (`PRD.md` §14).
- [ ] **U8-T5** Final pipeline run on `main`: all jobs green, smoke test passes; verify live URL end-to-end using the demo script; wake-up note about free-tier cold start; ping with an uptime monitor shortly before the demo (human).
- [ ] **U8-T6** Capture evidence for the human: a sample of `logs/app.log` lines for one request ID; screenshot list suggestions (dashboard, recap, brief, nudges, Actions run, Security tab).

**Acceptance:** fresh clone → README steps run the app; live site demonstrates the full `PRD.md` §14 script; README covers every item the assessment requires.

---

## Unit 9 — (Optional) Vector RAG + "Ask Team Memory"

**Goal:** upgrade retrieval from LLM-summary linking to embeddings-based RAG without changing callers of `find_related()`.

**Depends on:** Unit 6 · **Read:** `ARCHITECTURE.md` §11.4; `PRD.md` FR-K6.

Tasks:
- [ ] **U9-T1** `kb/chunking.py` (~350 words, ~50 overlap; deterministic; unit-tested).
- [ ] **U9-T2** `kb/embeddings.py` + `AIClient.embed` (batching, timeout, retry, `ai.call` log with `operation=embed`); `kb_chunks` populated on create/reindex; `index_status` updated; failure → `failed` + fallback.
- [ ] **U9-T3** `VectorRetriever` (numpy cosine, top-k 4, `MIN_SCORE` configurable, group by document); chain `vector → llm → keyword`; set `RETRIEVER=vector` when embeddings exist.
- [ ] **U9-T4** Reindex-all admin action on `/kb` and automatic indexing for auto-indexed meeting docs.
- [ ] **U9-T5** `/ask` page: question → retrieve → `ask.v1` prompt → answer with citations; fallback = top passages; "no relevant info" handling.
- [ ] **U9-T6** Tests: chunking edge cases, cosine ranking with fake embeddings, fallback chain, ask fallback.

**Acceptance:** semantic queries return relevant chunks even without keyword overlap; links show method "Semantic"; `/ask` answers only from documents and cites them; everything still works with embeddings disabled.

---

## Cross-cutting checklist (verify at the end of every unit)

- [ ] Layering respected (no logic in routers; AI/retrieval only via their single entry points).
- [ ] Domain events logged; no secrets/content in logs.
- [ ] Validation + friendly errors on new forms/endpoints.
- [ ] UI uses tokens/components from `design.md`; keyboard and screen-reader basics OK.
- [ ] Tests added; `ruff` + `pytest` green; pipeline green after push.
- [ ] `memory.md` updated (pass log, snapshot, file registry, next-pass notes).
