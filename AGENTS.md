# AGENTS.md — Rules for AI Agents working on LoopClose

> **Read this file completely at the start of every pass.** You may be a different AI than the one that worked before you. The project is designed so that any agent can continue seamlessly by following these rules and the handover files.
> Project: **LoopClose** — AI-powered meeting/handover & action-item tracker with a knowledge base (RAG), built for the SPIT/DigiPlus assessment (3.5-hour build, delivered in "units").

---

## 1. Start-of-pass ritual (mandatory, in this order)

1. Read `memory.md` **first** — especially *Current State Snapshot*, *Open Questions*, *Next Pass Considerations* and the **last 3 pass log entries**.
2. Read `AGENTS.md` (this file).
3. Read `TASKS.md` — find the unit you were asked to build and its checklist. **Only build that unit.**
4. Read the relevant parts of `PRD.md` (behaviour), `ARCHITECTURE.md` (tech/structure/data/AI/logging/DevOps) and `design.md` (UI) for that unit.
5. Inspect the actual repo (`git status`, `git log --oneline -10`, list files). **The code is the truth; `memory.md` can be stale** — if they disagree, trust the code and log the discrepancy.
6. Restate in 3–5 lines (in your own working notes) what you will build in this pass and which files you will touch.

## 2. End-of-pass ritual (mandatory)

1. Run `ruff format . && ruff check . && pytest -q` — all must pass. (If a tool isn't installed yet because the unit that adds it hasn't run, note that in `memory.md`.)
2. Run the app locally and exercise the unit's acceptance criteria manually (or with the browser tool if you have one).
3. Tick completed checkboxes in `TASKS.md` (only tasks that are truly done and verified). Never tick a task that is partial — split it and note what's left.
4. **Append a pass entry to `memory.md`** using the exact template there, and **update the Current State Snapshot and File Registry** sections.
5. Commit with conventional commit messages and push (see §8). Confirm the pipeline started; if you cannot observe it, say so in `memory.md`.
6. Final message to the human: what was done, how to run/verify, anything they must do manually (secrets, dashboard settings), and any open questions. Be concise and honest — never claim something works if you did not run it.

## 3. Scope discipline

- **One unit per pass** unless the human explicitly says otherwise. Do not start the next unit "to be helpful".
- Do **not** refactor or restyle code from earlier units unless the current unit requires it or it is a bug blocking you. If you must, log it.
- Do **not** add features, pages, routes or tables that are not in `PRD.md`/`ARCHITECTURE.md`. If you think something is missing, add it to `memory.md → Open Questions` instead of building it.
- Do **not** edit `PRD.md`, `ARCHITECTURE.md`, `design.md` or `AGENTS.md` unless the human tells you to. You **may** edit `memory.md` (required) and tick boxes in `TASKS.md`.
- If the three spec documents conflict, follow precedence: **PRD > ARCHITECTURE > design > TASKS**. Choose the most conservative interpretation, proceed, and log the conflict in `memory.md → Open Questions`.
- Time matters: this is a hard-deadline assessment. Prefer the simplest implementation that meets the acceptance criteria. Do not gold-plate.

## 4. Technology rules

- Use **only** the stack in `ARCHITECTURE.md` §3. Do not introduce new frameworks. Adding a small utility dependency is allowed only if clearly necessary: add it to `requirements.txt` (pinned), and record **name, version and reason** in `memory.md → Dependencies`.
- Python 3.12, FastAPI, SQLAlchemy 2.x (typed), Pydantic v2, Jinja2 + HTMX, Postgres in prod / SQLite locally. Sync SQLAlchemy sessions; sync route functions (`def`, not `async def`) for DB-touching routes.
- **Pin versions**: after installing, write exact versions to `requirements.txt` / `requirements-dev.txt`. Do not invent version numbers from memory — install and `pip freeze`.
- **Verify third-party APIs against current official docs** (especially the Gemini SDK and GitHub Action versions) rather than relying on memory. If you cannot verify, implement defensively, test, and log the uncertainty.
- Never commit `.env`, API keys, database files (`*.db`), `logs/`, virtualenvs, or `__pycache__`.

## 5. Code rules

### 5.1 Structure and layering (see `ARCHITECTURE.md` §6)
- Routers → services → models/ai/kb. **No business logic in routers. No FastAPI/Jinja imports in services. No SQL in routers/templates.**
- All LLM access via `app/ai/client.py::AIClient`. All KB retrieval via `app/kb/retrieval.py::find_related`.
- All enums in `app/enums.py`. All settings via `app/config.py`. Never call `os.environ` elsewhere.
- Put state-machine rules in services (`InvalidTransitionError`), not in templates.

### 5.2 Style
- Type hints on all function signatures. Small functions (< ~40 lines). Descriptive names. Docstring (1–3 lines) on every service function and public class explaining *why/what*, not how.
- `ruff` is the single source for lint + format (config in `pyproject.toml`: line length 100, rules at least `E,F,I,B,UP,S` minus the few `S` rules that are noisy in tests). No `print()` — use the logger.
- No dead code, no commented-out blocks, no TODOs without an entry in `memory.md`.
- Dates/times: store **UTC**; use timezone-aware datetimes; `date` for due dates.
- Prefer explicit over clever. No metaprogramming, no global mutable state except the logging context var and settings singleton.

### 5.3 Database
- Models use SQLAlchemy 2.x `Mapped[]`/`mapped_column`. Enums as strings (`native_enum=False`).
- Every mutation happens inside a service function with one transaction (`session.commit()` at the end; rollback on exception).
- `Base.metadata.create_all()` on startup (no Alembic). If you change a model after data exists locally, tell the human to delete `local.db` (and note in `memory.md`).
- Never delete `action_item_events`. They are append-only.

### 5.4 Validation and errors
- Validate at the edge with Pydantic schemas **and** enforce business rules in services (see `PRD.md` §8).
- Raise the custom exceptions in `app/errors.py`; global handlers turn them into friendly HTML/JSON responses with the request ID. **Never let a raw traceback reach the user.**
- HTML form errors are re-rendered inline (HTTP 422); state errors 409; missing 404.

### 5.5 Templates and UI
- Follow `design.md` exactly: tokens, components, copy tone, accessibility checklist. Use CSS variables only; no hard-coded colours in templates.
- Keep templates dumb: formatting only. Use macros/partials for badges, avatars, item rows, banners.
- Jinja autoescape stays on. **Never use `|safe` on user/AI content.**
- AI-generated content always shows the **AI pill** until edited; AI actions use the **AI button** style and the skeleton loading state.

## 6. AI rules (critical for the assessment)

1. Every AI operation goes through `AIClient.run_structured(...)`, returns an `AIResult`, and **never raises for AI problems**.
2. Every operation has a **defined fallback** (`ARCHITECTURE.md` §10.3) implemented in `app/ai/fallbacks.py` and covered by a test.
3. LLM output is parsed and validated with Pydantic; invalid → one retry with a stricter reminder → fallback.
4. Prompts live in `app/ai/prompts/`, have a `PROMPT_VERSION`, wrap untrusted text in delimiters and say it is data not instructions.
5. AI results are **proposals**: recap → review → apply; link suggestions → accept/dismiss.
6. **Never** log prompts, notes, KB content or model output text; log lengths, counts, latency, outcome only.
7. **Never** hard-code a model name or API key. Read from settings. If no key is configured, the app must boot and behave via fallbacks (log a WARNING once).
8. Tests must use `FakeProvider`; **no test may hit the network or a real LLM.**

## 7. Logging rules (assessment-critical)

- Use `logging.getLogger("app.<area>")` (areas: `http`, `ai`, `meetings`, `items`, `kb`, `nudges`, `system`).
- Log **events** with stable names from `ARCHITECTURE.md` §12.3 via a helper (e.g. `log_event(logger, "item.closed", item_id=..., outcome_type=...)`) so output stays JSON-structured. Include IDs, not content.
- Every state change in a service emits its event. Every AI call emits `ai.call` with latency + outcome. Every handled fallback emits `ai.fallback` (WARNING). Unhandled errors → ERROR with `exc_info`.
- **Never log**: API keys, tokens, `.env` values, full request bodies, notes/KB text, emails. The redaction filter is a safety net, not permission.
- Correlation ID comes from the contextvar (set by middleware). Do not pass `request_id` manually; the filter adds it. Services running outside a request (seed, scripts) use `request_id="-"` or a generated job ID.

## 8. Git, CI/CD and security rules

- Work on `main` (acceptable for this project) **only if CI stays green**. Small, focused commits. Conventional commit prefixes: `feat:`, `fix:`, `chore:`, `ci:`, `docs:`, `test:`, `refactor:`.
- Before every push: `ruff format . && ruff check . && pytest -q`. Do not push failing code.
- **Every push triggers the GitHub Actions pipeline** (`.github/workflows/ci-cd.yml`): Gitleaks → CodeQL → lint/tests → Docker build → deploy to Render (main only) → smoke test. Never bypass or disable a job to make it pass; fix the cause. If a job fails for an infrastructure reason (e.g. missing secret, private-repo CodeQL limitation), report it clearly in `memory.md` and to the human instead of removing the job.
- **Secrets:** only in local `.env` (gitignored), Render dashboard, and GitHub Actions secrets. `.env.example` contains **names and dummy placeholders only**. If you ever write a real-looking key anywhere in the repo, stop and tell the human to rotate it.
- Do not use `--no-verify`, force-push `main`, or rewrite history unless the human asks.
- You cannot create GitHub/Render accounts or set secrets. List exactly what the human must do (e.g. "add `RENDER_DEPLOY_HOOK_URL` and `APP_URL` as Actions secrets").

## 9. Testing rules

- Add or update tests for every unit's logic (services, state machines, AI parsing/fallbacks, validation). UI is verified manually against the acceptance criteria.
- Tests are fast, isolated (temp DB), deterministic (fake provider, fixed dates via helper).
- A unit is not "done" if tests for its core rules are missing. See `ARCHITECTURE.md` §15 for the must-have list.

## 10. Data rules

- Seed data (`scripts/seed.py`) is idempotent, realistic, human-written and **relative to today** (`PRD.md` §10). Extend it as each unit adds entities; do not replace it wholesale.
- Don't use lorem ipsum anywhere visible.

## 11. Safety and environment

- Don't run destructive commands (`rm -rf` outside the project, dropping real databases, force pushes). Don't touch files outside the project directory.
- Don't exfiltrate or echo secrets into terminals/logs/commit messages.
- Prefer deterministic, reproducible commands. Document how to run things in `README.md` as you go (Unit 8 finalises it).

## 12. Quality bar — Definition of Done (per unit)

A unit is done only when **all** are true:
- [ ] Every task in the unit's `TASKS.md` checklist is complete or explicitly deferred with a reason logged.
- [ ] Acceptance criteria for the unit were exercised and pass.
- [ ] `ruff format --check`, `ruff check`, `pytest` pass locally.
- [ ] Domain events and AI calls from this unit appear correctly in `logs/app.log` (spot-check a real request).
- [ ] UI matches `design.md` for the pages touched (tokens, badges, states, responsive, a11y basics).
- [ ] Failure paths handled (validation errors, 404, AI failure → fallback).
- [ ] `memory.md` updated (pass entry, snapshot, file registry, next-pass notes).
- [ ] Changes committed and pushed; pipeline status noted.

## 13. Handover etiquette (you may be replaced mid-project)

- Leave the repo **runnable** at the end of every pass (`uvicorn app.main:app` starts; tests green). If you cannot, say so loudly at the top of your `memory.md` entry under **⚠ Broken/Unfinished**.
- Write `memory.md` as if the next agent has zero context: file purposes, decisions and *why*, gotchas, commands that worked, and exact next steps.
- Never delete previous `memory.md` pass entries. Only the *Current State Snapshot* and *File Registry* are rewritten in place.
- Be honest about uncertainty. "I did not verify X" is useful; silent assumptions are harmful.

## 14. Quick command reference (create/keep these working)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                                   # then fill values locally (never commit)
uvicorn app.main:app --reload                          # run locally, http://127.0.0.1:8000
python -m scripts.seed                                 # load demo data (idempotent)
ruff format . && ruff check . && pytest -q             # pre-push checks
docker build -t loopclose:local . && docker run --rm -p 8000:8000 --env-file .env loopclose:local
```
