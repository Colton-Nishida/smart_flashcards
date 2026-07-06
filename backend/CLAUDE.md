# backend/ — FastAPI service

Poetry-managed Python 3.12 project. JSON API under `/api`. See `docs/DESIGN.md` for the full
API surface and data model; root `CLAUDE.md` for working rules (worktrees, TDD, ruff).

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | App factory `create_app(settings?)`, router mounting, CORS for the Vite dev server. Settings + Storage live on `app.state` |
| `app/config.py` | `pydantic-settings` — `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `SESSION_SECRET` (warns if defaulted), `DATA_DIR` (resolved to absolute) |
| `app/deps.py` | Shared dependencies: `get_settings` / `get_storage` read from `request.app.state` |
| `app/auth/` | register / login / logout / me — bcrypt hashes, itsdangerous-signed session cookie. `app/auth/deps.py` has the `current_user` dependency |
| `app/decks/` | Deck + card CRUD routes + `POST /api/decks` (upload → generate → persist) |
| `app/generation/` | PDF → flashcards via the `anthropic` SDK. `deps.py` has `get_anthropic_client` (override in tests); `http.py` has the shared `llm_errors` HTTP mapping; `service.py` exports `pdf_document_block` / `is_truncated_json` for other LLM callers |
| `app/topics/` | Topic CRUD (`/api/topics`): PDF upload → extracted notes doc, 0-100 mastery score + memory, session history. `service.py` also holds the quiz-session state machine (`active_session` on the topic dict) |
| `app/quiz/` | The quiz agent: `agent.py` = one structured-output call per step (question / grade / dispute / score), `router.py` = `/api/topics/{id}/quiz/*` routes, `models.py` = structured-output schemas |
| `app/skills/*.md` | System prompts ("agent skills"): `flashcard_generation`, `topic_notes_extraction`, `quiz_question`, `quiz_grading`, `quiz_dispute`, `quiz_scoring`. Tune output quality HERE, not in code |
| `app/storage/` | File persistence: `data/users.json`, `data/decks/<user_id>/<deck_id>.json`, `data/topics/<user_id>/<topic_id>.{json,pdf}`. Atomic write-then-rename. ALL disk access goes through this module (it's the future DB seam) |
| `tests/` | pytest. Write tests BEFORE implementation. Fixtures in `conftest.py` build the app against a tmp data dir |

## Conventions

- Pydantic models for every request/response body; no untyped dicts across module boundaries.
- Routes are thin; logic lives in the module's service functions so it's testable without HTTP.
- Every deck access must check ownership (user id from session vs deck path) — enforce in one
  dependency, test per-user isolation explicitly.
- Generation calls: send the PDF as a base64 `document` content block (before the text block;
  build it with `generation.service.pdf_document_block`); use
  `client.messages.parse(..., output_format=Model)` for guaranteed-valid JSON. Model from
  settings. Requires `anthropic >= 0.116` — the original `^0.60` pin predates `messages.parse`
  (see `.claude/skills/anthropic-structured-outputs-sdk-version/`).
- **`max_tokens` ceiling: 21000.** The SDK's non-streaming guard raises `ValueError` at request
  time for `max_tokens > 21333` (assumed 128k tok/hr ⇒ >10-minute request). Mocked tests can't
  catch a violation — it only fails live. Going higher requires a streaming call.
- Quiz flow (`/api/topics/{id}/quiz/*`): `start` → `answer` → (`dispute`*) → `next` … →
  `finish` (scores + archives) or `DELETE` (abandon). State machine lives in
  `topics/service.py`; every step persists atomically. `start` 409s on an in-progress session
  unless `replace: true`; `answer`/`dispute` accept a `session_id`/`question_number` binding
  that 409s writes from stale tabs. Disputes can never lower a grade, and a "revised" verdict
  that doesn't raise the grade is reported as "upheld".
- Mock the Anthropic client in tests: override `app.dependency_overrides[get_anthropic_client]`
  with a `MagicMock` whose `messages.parse` returns
  `SimpleNamespace(stop_reason=..., parsed_output=FlashcardDeck(...))`. The suite never needs
  `ANTHROPIC_API_KEY`. Live smoke test only behind `RUN_LIVE_API_TESTS=1`
  (`tests/test_live_api.py`).
- Upload validation: PDF magic-byte check (`%PDF-`) → 400, ≤20 MB → 413.
- Generation error mapping (raised in `generation/service.py` + `quiz/agent.py`; mapped inline
  in `decks/router.py` and via `generation/http.py::llm_errors` in the topic/quiz routers):
  - `DocumentTooLargeError` → **413**. Two triggers: `stop_reason == "max_tokens"`, OR
    `messages.parse()` raising a `ValidationError` whose type is `json_invalid` (the response
    JSON was truncated mid-object because output overflowed the token cap — parse raises
    *before* we can read `stop_reason`, so this MUST be caught or it surfaces as a raw 500).
  - `MalformedGenerationError` → **502**: a non-truncation `ValidationError` (well-formed JSON
    that failed the schema — very rare with structured outputs).
  - `anthropic.APIError` → **502**. Missing/empty `ANTHROPIC_API_KEY` → **503** from
    `get_anthropic_client`.
- Logging: `create_app` calls `_configure_logging()` to attach an INFO stderr handler to the
  `app.*` logger tree (uvicorn doesn't route app loggers otherwise). Generation logs the
  request + card count; failures log with user/deck/pdf-size context.

## Commands (run from this directory)

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8000
poetry run pytest
poetry run ruff check . && poetry run ruff format .
```
