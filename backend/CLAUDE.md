# backend/ — FastAPI service

Poetry-managed Python 3.12 project. JSON API under `/api`. See `docs/DESIGN.md` for the full
API surface and data model; root `CLAUDE.md` for working rules (worktrees, TDD, ruff).

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | App factory `create_app(settings?)`, router mounting, CORS for the Vite dev server, `GET /api/health`, and (when `STATIC_DIR` is set) SPA static serving. Settings + Storage live on `app.state` |
| `app/config.py` | `pydantic-settings` — `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `SESSION_SECRET` (warns if defaulted), `DATA_DIR` (resolved to absolute), plus prod knobs `INVITE_CODE`, `SESSION_COOKIE_SECURE`, `STATIC_DIR` (docs/DEPLOY.md) |
| `app/spa.py` | `SPAStaticFiles` — static files with index.html fallback for client-side routes; mounted at `/` after all API routers |
| `app/deps.py` | Shared dependencies: `get_settings` / `get_storage` read from `request.app.state` |
| `app/auth/` | register / login / logout / me — bcrypt hashes, itsdangerous-signed session cookie. `app/auth/deps.py` has the `current_user` dependency. Register is gated by `INVITE_CODE` when configured (→ 403); the cookie gets `Secure` when `SESSION_COOKIE_SECURE=true` |
| `app/decks/` | Deck + card CRUD routes + `POST /api/decks` (upload → generate → persist) |
| `app/generation/` | PDF → flashcards via the `anthropic` SDK. `deps.py` has `get_anthropic_client` (override in tests) |
| `app/skills/flashcard_generation.md` | The generation system prompt ("agent skill"). Tune card quality HERE, not in code |
| `app/storage/` | File persistence: `data/users.json`, `data/decks/<user_id>/<deck_id>.json`. Atomic write-then-rename. ALL disk access goes through this module (it's the future DB seam) |
| `tests/` | pytest. Write tests BEFORE implementation. Fixtures in `conftest.py` build the app against a tmp data dir |

## Conventions

- Pydantic models for every request/response body; no untyped dicts across module boundaries.
- Routes are thin; logic lives in the module's service functions so it's testable without HTTP.
- Every deck access must check ownership (user id from session vs deck path) — enforce in one
  dependency, test per-user isolation explicitly.
- Generation calls: send the PDF as a base64 `document` content block (before the text block);
  use `client.messages.parse(..., output_format=FlashcardDeck)` for guaranteed-valid JSON.
  `max_tokens=16000`, model from settings. Requires `anthropic >= 0.116` — the original `^0.60`
  pin predates `messages.parse` (see `.claude/skills/anthropic-structured-outputs-sdk-version/`).
- Mock the Anthropic client in tests: override `app.dependency_overrides[get_anthropic_client]`
  with a `MagicMock` whose `messages.parse` returns
  `SimpleNamespace(stop_reason=..., parsed_output=FlashcardDeck(...))`. The suite never needs
  `ANTHROPIC_API_KEY`. Live smoke test only behind `RUN_LIVE_API_TESTS=1`
  (`tests/test_live_api.py`).
- Upload validation: PDF magic-byte check (`%PDF-`) → 400, ≤20 MB → 413.
- Generation error mapping (all raised in `generation/service.py`, mapped in `decks/router.py`):
  - `DocumentTooLargeError` → **413**. Two triggers: `stop_reason == "max_tokens"`, OR
    `messages.parse()` raising a `ValidationError` whose type is `json_invalid` (the response
    JSON was truncated mid-object because output overflowed the 16k token cap — parse raises
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
